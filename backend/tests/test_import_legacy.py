"""تست مهاجرت داده‌های سامانه قبلی آموزش هوشمند (فایل پیوست smart-education)."""
import importlib.util
import sqlite3
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_legacy_education.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("import_legacy_education", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def schema():
    """ساخت schema دیتابیس تست (بدون fixture client)."""
    import app.models  # noqa: F401
    from app.core.database import Base, engine

    Base.metadata.create_all(engine)


@pytest.fixture()
def legacy_db(tmp_path):
    """یک نسخه مینیاتوری از education.db پیوست با همان شِما."""
    db = tmp_path / "education.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT, description TEXT, is_active INTEGER);
    CREATE TABLE course_topics (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT,
        description TEXT, session_minute INTEGER, sort_order INTEGER, is_active INTEGER);
    CREATE TABLE educational_contents (id INTEGER PRIMARY KEY, topic_id INTEGER,
        title TEXT, body TEXT, source TEXT, created_at TEXT);
    CREATE TABLE ai_service_usage (id INTEGER PRIMARY KEY, provider TEXT, model TEXT,
        request_type TEXT, tokens_used INTEGER, success INTEGER, error_message TEXT,
        request_duration_ms INTEGER);
    """)
    con.execute("INSERT INTO courses VALUES (9001, 'درس 9001', 'توضیح تست', 1)")
    for i in range(1, 4):
        con.execute("INSERT INTO course_topics VALUES (?, 9001, ?, ?, 50, ?, 1)",
                    (900100 + i, "فصل تست", f"نکته جلسه {i}", i))
    con.execute("INSERT INTO educational_contents VALUES (7001, 900101, 'محتوای تست', "
                "'پاراگراف اول.\n- نکته یک\n- نکته دو\nپاراگراف دوم.', 'manual', '2026-07-17')")
    con.execute("INSERT INTO ai_service_usage VALUES (8001, 'openai_compatible', 'gpt-5.2', "
                "'content_generation', 1814, 1, NULL, 35603)")
    con.execute("INSERT INTO ai_service_usage VALUES (8002, 'openai_compatible', 'gpt-5.6', "
                "'content_generation', 0, 0, 'سرویس هوش مصنوعی خطا برگرداند: 403', NULL)")
    con.commit()
    con.close()
    return str(db)


def test_import_creates_course_chapters_topics(legacy_db, schema):
    mod = _load_module()
    stats = mod.import_legacy(legacy_db)
    assert stats["courses"] == 1 and stats["chapters"] == 1 and stats["topics"] == 3
    assert stats["contents"] == 1 and stats["ai_runs"] == 2

    from app.core.database import SessionLocal
    from app.models.content import ContentDocument, ContentVersion
    from app.models.courses import Course
    from app.models.ops import AIRun
    from app.models.syllabus import SyllabusTopic, SyllabusVersion

    db = SessionLocal()
    try:
        course = db.query(Course).filter(Course.code == "LEG-9001").one()
        assert course.title  # نام fallback از داده legacy
        sv = db.query(SyllabusVersion).filter(SyllabusVersion.course_id == course.id).one()
        assert sv.status == "APPROVED"
        chapter = db.query(SyllabusTopic).filter(
            SyllabusTopic.syllabus_version_id == sv.id,
            SyllabusTopic.kind == "CHAPTER").one()
        topics = db.query(SyllabusTopic).filter(
            SyllabusTopic.syllabus_version_id == sv.id,
            SyllabusTopic.kind == "TOPIC").order_by(SyllabusTopic.order_index).all()
        assert len(topics) == 3
        assert all(t.parent_id == chapter.id for t in topics)
        assert topics[0].suggested_hours == pytest.approx(0.83)
        assert topics[0].title == "نکته جلسه 1"

        doc = db.query(ContentDocument).filter(ContentDocument.course_id == course.id).one()
        assert str(topics[0].id) in doc.scope["topic_ids"]
        version = db.query(ContentVersion).filter(
            ContentVersion.document_id == doc.id).one()
        assert version.status == "PUBLISHED"
        blocks = version.structured_content["blocks"]
        assert blocks[0] == {"type": "text", "body": "پاراگراف اول."}
        assert blocks[1]["type"] == "text" and blocks[1]["items"] == ["نکته یک", "نکته دو"]
        assert blocks[2] == {"type": "text", "body": "پاراگراف دوم."}

        runs = db.query(AIRun).filter(AIRun.provider == "openai_compatible").all()
        assert {r.status for r in runs} == {"SUCCEEDED", "FAILED"}
        ok = next(r for r in runs if r.status == "SUCCEEDED")
        assert ok.latency_ms == 35603 and ok.tokens_out == 1814
        failed = next(r for r in runs if r.status == "FAILED")
        assert "403" in (failed.error or "")
    finally:
        db.close()


def test_import_is_idempotent(legacy_db, schema, tmp_path):
    mod = _load_module()
    # DB تست در سطح session مشترک است؛ نسخه مستقل با درس دیگر می‌سازیم
    other = tmp_path / "education-other.db"
    src = sqlite3.connect(legacy_db)
    dst = sqlite3.connect(other)
    dst.executescript("""
    CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT, description TEXT, is_active INTEGER);
    CREATE TABLE course_topics (id INTEGER PRIMARY KEY, course_id INTEGER, title TEXT,
        description TEXT, session_minute INTEGER, sort_order INTEGER, is_active INTEGER);
    CREATE TABLE educational_contents (id INTEGER PRIMARY KEY, topic_id INTEGER,
        title TEXT, body TEXT, source TEXT, created_at TEXT);
    CREATE TABLE ai_service_usage (id INTEGER PRIMARY KEY, provider TEXT, model TEXT,
        request_type TEXT, tokens_used INTEGER, success INTEGER, error_message TEXT,
        request_duration_ms INTEGER);
    """)
    dst.execute("INSERT INTO courses VALUES (9100, 'درس 9100', 'توضیح تست دوم', 1)")
    for i in range(1, 3):
        dst.execute("INSERT INTO course_topics VALUES (?, 9100, 'فصل دوم', ?, 45, ?, 1)",
                    (910000 + i, f"نکته دوم {i}", i))
    dst.commit()
    src.close()
    dst.close()

    first = mod.import_legacy(str(other))
    second = mod.import_legacy(str(other))
    assert first["courses"] == 1 and first["topics"] == 2
    assert second["courses"] == 0 and second["skipped"] == ["LEG-9100"]

    from app.core.database import SessionLocal
    from app.models.courses import Course
    db = SessionLocal()
    try:
        assert db.query(Course).filter(Course.code == "LEG-9001").count() == 1
    finally:
        db.close()


def test_ollama_provider_selected():
    """مطابق پیوست: پشتیبانی provider ollama."""
    from app.ai.providers import OllamaProvider, get_provider

    p = OllamaProvider()
    assert p.base_url.startswith("http://localhost:11434")
    assert p.model
