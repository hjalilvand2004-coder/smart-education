"""مهاجرت داده‌های سامانه قبلی «آموزش هوشمند» (education.db) به سامانه یکپارچه.

منبع: فایل پیوست smart-education — درس‌ها، سرفصل‌های جلسه‌ای (course_topics با
مدت جلسه)، محتوای تولیدشده به ازای هر سرفصل (educational_contents) و لاگ مصرف
سرویس‌های هوش مصنوعی (ai_service_usage).

نگاشت:
    courses            → Course (+ SyllabusVersion نسخه ۱ تصویب‌شده)
    course_topics      → SyllabusTopic: عنوان خانواده = فصل (CHAPTER) و هر نکته
                         جلسه = موضوع (TOPIC) زیر آن؛ session_minute → suggested_hours
    educational_contents → ContentDocument + ContentVersion منتشرشده با بلوک‌های
                         ساختاریافته (پاراگراف/فهرست)
    ai_service_usage   → AIRun (purpose=CONTENT_GENERATION، provider/model/latency)
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal, utcnow  # noqa: E402
from app.models.content import ContentDocument, ContentVersion  # noqa: E402
from app.models.courses import Course  # noqa: E402
from app.models.identity import CourseRole, User  # noqa: E402
from app.models.ops import AIRun  # noqa: E402
from app.models.syllabus import SyllabusTopic, SyllabusVersion  # noqa: E402

# نام‌گذاری درس‌ها بر اساس خانواده سرفصل‌های واقعی فایل پیوست
COURSE_MAP = {
    "1036": {"code": "SE-360", "title": "مهندسی نرم‌افزار و ابزارهای توسعه",
             "department": "مهندسی نرم‌افزار", "credits": 2},
    "1038": {"code": "DM-360", "title": "داده‌کاوی",
             "department": "علوم داده و یادگیری ماشین", "credits": 3},
}

BULLET_PREFIXES = ("-", "•", "*", "–", "—")


def text_to_blocks(body: str) -> list[dict]:
    """تبدیل متن ساده legacy به بلوک‌های ساختاریافته سامانه یکپارچه."""
    blocks: list[dict] = []
    bullets: list[str] = []
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            if bullets:
                blocks.append({"type": "text", "items": bullets})
                bullets = []
            continue
        if line.startswith(BULLET_PREFIXES) or (len(line) > 2 and line[0].isdigit() and line[1:3] in (". ", ") ")):
            bullets.append(line.lstrip("".join(BULLET_PREFIXES)) .strip(" .") or line)
        else:
            if bullets:
                blocks.append({"type": "text", "items": bullets})
                bullets = []
            blocks.append({"type": "text", "body": line})
    if bullets:
        blocks.append({"type": "text", "items": bullets})
    return blocks or [{"type": "text", "body": (body or "").strip() or "—"}]


def import_legacy(db_path: str, session=None) -> dict:
    """واردات کامل فایل legacy؛ idempotent (درس موجود با همان کد نادیده گرفته می‌شود)."""
    own = session is None
    db = session or SessionLocal()
    src = sqlite3.connect(db_path)
    src.row_factory = sqlite3.Row
    # استاد نمونه محیط دمو به درس‌های وارداتی دسترسی استادی می‌گیرد تا استودیو/محتوا قابل مرور باشد
    demo_prof = db.query(User).filter(User.username == "prof.rezaei").first()
    stats = {"courses": 0, "chapters": 0, "topics": 0, "contents": 0, "ai_runs": 0, "skipped": []}
    try:
        for legacy_course in src.execute("SELECT * FROM courses ORDER BY id"):
            cid = str(legacy_course["id"])
            meta = COURSE_MAP.get(cid) or {
                "code": f"LEG-{cid}", "title": legacy_course["title"] or f"درس {cid}",
                "department": None, "credits": None}
            if db.query(Course).filter(Course.code == meta["code"]).first() is not None:
                stats["skipped"].append(meta["code"])
                continue
            chapter_rows = list(src.execute(
                "SELECT title, MIN(sort_order) AS first_order FROM course_topics "
                "WHERE course_id = ? GROUP BY title ORDER BY first_order", (legacy_course["id"],)))
            description = (legacy_course["description"] or "").strip()
            if chapter_rows:
                description = (description + " | " if description else "") + \
                    "فصل‌ها: " + "، ".join(r["title"] for r in chapter_rows)
            course = Course(code=meta["code"], title=meta["title"],
                            department=meta.get("department"), credits=meta.get("credits"),
                            description=description or None)
            db.add(course)
            db.flush()
            if demo_prof is not None and db.query(CourseRole).filter(
                    CourseRole.user_id == demo_prof.id,
                    CourseRole.course_id == course.id).first() is None:
                db.add(CourseRole(course_id=course.id, user_id=demo_prof.id, role="PROFESSOR"))

            sv = SyllabusVersion(
                course_id=course.id, version_number=1,
                title="سرفصل جلسه‌ای منتقل‌شده از سامانه قبلی آموزش هوشمند",
                status="APPROVED", source_kind="MANUAL",
                approved_at=utcnow(), notes="مهاجرت از فایل پیوست smart-education (education.db)")
            db.add(sv)
            db.flush()

            # فصل‌ها
            chapter_ids: dict[str, object] = {}
            for i, ch in enumerate(chapter_rows, start=1):
                topic = SyllabusTopic(
                    syllabus_version_id=sv.id, kind="CHAPTER", title=ch["title"],
                    description=None, order_index=i)
                db.add(topic)
                chapter_ids[ch["title"]] = topic
                stats["chapters"] += 1
            db.flush()

            # نکته‌های جلسه‌ای زیر هر فصل
            legacy_topic_ids: dict[int, object] = {}
            for row in src.execute(
                    "SELECT * FROM course_topics WHERE course_id = ? ORDER BY sort_order",
                    (legacy_course["id"],)):
                parent = chapter_ids.get(row["title"])
                point = SyllabusTopic(
                    syllabus_version_id=sv.id, kind="TOPIC", parent_id=parent.id if parent else None,
                    title=row["description"] or row["title"],
                    description=f"جلسه از فصل «{row['title']}»",
                    order_index=row["sort_order"],
                    suggested_hours=round((row["session_minute"] or 0) / 60.0, 2))
                db.add(point)
                legacy_topic_ids[row["id"]] = point
                stats["topics"] += 1
            db.flush()

            # محتوای تولیدشده به ازای سرفصل‌ها
            for c in src.execute(
                    "SELECT * FROM educational_contents WHERE topic_id IN "
                    "(SELECT id FROM course_topics WHERE course_id = ?)", (legacy_course["id"],)):
                target = legacy_topic_ids.get(c["topic_id"])
                if target is None:
                    continue
                doc = ContentDocument(
                    course_id=course.id, syllabus_version_id=sv.id,
                    title=c["title"] or target.title, goal="CONCEPT_TEACHING",
                    scope={"topic_ids": [str(target.id)]},
                    style="ACADEMIC", language="FA")
                db.add(doc)
                db.flush()
                version = ContentVersion(
                    document_id=doc.id, version_number=1, syllabus_version_id=sv.id,
                    structured_content={"blocks": text_to_blocks(c["body"])},
                    status="PUBLISHED", published_at=utcnow(), approved_at=utcnow())
                db.add(version)
                stats["contents"] += 1
            stats["courses"] += 1

        # لاگ مصرف هوش مصنوعی (مستقل از درس)
        for u in src.execute("SELECT * FROM ai_service_usage"):
            db.add(AIRun(
                purpose="CONTENT_GENERATION", provider=u["provider"] or "legacy",
                model=u["model"] or "-", prompt_version="legacy-1",
                status="SUCCEEDED" if u["success"] else "FAILED",
                latency_ms=u["request_duration_ms"] if "request_duration_ms" in u.keys() else None,
                tokens_out=u["tokens_used"] or 0,
                error=u["error_message"] if not u["success"] else None))
            stats["ai_runs"] += 1

        db.commit()
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        src.close()
        if own:
            db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="واردات داده‌های سامانه قبلی آموزش هوشمند")
    parser.add_argument("--db", default="legacy/education.db",
                        help="مسیر فایل education.db سامانه قبلی")
    args = parser.parse_args()
    if not Path(args.db).exists():
        print(f"فایل یافت نشد: {args.db}")
        sys.exit(1)
    stats = import_legacy(args.db)
    print("✅ مهاجرت کامل شد:", stats)


if __name__ == "__main__":
    main()
