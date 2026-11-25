"""تست یکپارچگی اساتید (v3.7.0): واکشی از پایه‌یار۳۶۰ (رونوشت)، مطلوبیات از
درس‌یار۳۶۰ (حالت live/demo با کش)، درس‌های متناسب و درج انبوه بلوک محتوای استاد.

شبکهٔ واقعی در تست مصرف نمی‌شود: _fetch_live با monkeypatch جایگزین می‌شود تا
هم مسیر demo و هم مسیر live قطعی و سریع باشد."""
from uuid import uuid4

import pytest

from app.core.database import SessionLocal
from app.models.content import ContentDocument, ContentVersion
from app.models.courses import Course
from app.models.identity import CourseRole, User
from app.models.journey import PayehyarRecord
from app.models.syllabus import SyllabusVersion
from app.services import darsyar_service

_SHARED: dict = {"stage": 0}
EXT_ID = "PRF-201"


def _setup() -> dict:
    """استاد نمونهٔ پایه‌یار + درس متناسب + سند/نسخهٔ محتوای DRAFT برای بلوک انبوه."""
    if _SHARED["stage"] >= 1:
        return _SHARED
    db = SessionLocal()
    try:
        prof = db.query(User).filter(User.username == "prof_test").first()
        rec = db.query(PayehyarRecord).filter(
            PayehyarRecord.domain == "professors",
            PayehyarRecord.external_id == EXT_ID).first()
        if rec is None:
            rec = PayehyarRecord(
                domain="professors", external_id=EXT_ID,
                title="دکتر مریم رضایی",
                code="PRF201",
                payload={"full_name": "دکتر مریم رضایی", "code": "PRF201",
                         "department": "مهندسی کامپیوتر", "degree": "استادیار",
                         "email": "m.rezaei@uni.ac.ir"})
            db.add(rec)
        course = db.query(Course).filter(Course.code == "DAR301").first()
        if course is None:
            course = Course(code="DAR301", title="هوش مصنوعی کاربردی",
                            department="مهندسی کامپیوتر", created_by=prof.id)
            db.add(course)
            db.flush()
            db.add(CourseRole(course_id=course.id, user_id=prof.id, role="PROFESSOR"))
        sv = SyllabusVersion(course_id=course.id, version_number=1,
                             title="سرفصل درس اساتید", status="APPROVED",
                             source_kind="MANUAL")
        db.add(sv)
        db.flush()
        doc = ContentDocument(course_id=course.id, syllabus_version_id=sv.id,
                              title="سند تست اساتید", goal="CONCEPT_TEACHING")
        db.add(doc)
        db.flush()
        ver = ContentVersion(document_id=doc.id, syllabus_version_id=sv.id,
                             version_number=1, status="DRAFT", revision=1,
                             structured_content={"blocks": [
                                 {"id": "blk-seed", "type": "heading", "title": "فصل ۱"}]},
                             created_by=prof.id)
        db.add(ver)
        db.commit()
        _SHARED.update(stage=1, ext_id=EXT_ID, course_id=str(course.id),
                       version_id=str(ver.id))
    finally:
        db.close()
    return _SHARED


def _staff_headers(client):
    """یک ورود برای کل ماژول — جلوگیری از فعال‌شدن محدودیت نرخ ورود (۴۲۹)."""
    if _SHARED.get("token"):
        return {"Authorization": f"Bearer {_SHARED['token']}"}
    r = client.post("/api/v1/auth/login",
                    json={"username": "prof_test", "password": "Pass1234!"})
    assert r.status_code == 200, r.text
    _SHARED["token"] = r.json()["access_token"]
    return {"Authorization": f"Bearer {_SHARED['token']}"}


def test_professors_list_after_seed(client, ctx):
    _setup()
    h = _staff_headers(client)
    r = client.get("/api/v1/integration/professors", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["source_system"] == "پایه‌یار۳۶۰"
    ids = [i["ext_id"] for i in body["items"]]
    assert EXT_ID in ids


def test_professors_sync_without_key_fails_actionable(client, ctx):
    h = _staff_headers(client)
    r = client.post("/api/v1/integration/professors/sync", headers=h)
    # بدون کلید پایه‌یار، خطای قابل‌اقدام (نه 500) برمی‌گردد
    assert r.status_code in (400, 422), r.text
    assert "پایه‌یار" in r.json()["error"]["message"]


def test_preferences_demo_with_cache(client, ctx, monkeypatch):
    _setup()
    h = _staff_headers(client)
    monkeypatch.setattr(darsyar_service, "_fetch_live", lambda professor: None)
    r1 = client.get(f"/api/v1/integration/professors/{EXT_ID}/preferences", headers=h)
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["ok"] is True and body["source"] == "demo"
    assert body["subjects"] and body["time_slots"] and body["constraints"]
    # کش دومین فراخوانی: cached=True و همان داده
    r2 = client.get(f"/api/v1/integration/professors/{EXT_ID}/preferences", headers=h)
    assert r2.status_code == 200 and r2.json()["cached"] is True
    assert r2.json()["subjects"] == body["subjects"]


def test_preferences_live_source(client, ctx, monkeypatch):
    h = _staff_headers(client)
    live = {"subjects": [{"title": "هوش مصنوعی کاربردی", "course_code": "DAR301",
                          "weekly_hours": 4, "level": "تخصصی"}],
            "time_slots": [{"day": "شنبه", "start": "۸:۰۰", "end": "۱۰:۰۰",
                            "preference": "preferred", "preference_label": "مطلوب"}],
            "constraints": ["فقط ترم اول"]}
    monkeypatch.setattr(darsyar_service, "_fetch_live", lambda professor: dict(live))
    r = client.get(
        f"/api/v1/integration/professors/{EXT_ID}/preferences?refresh=true", headers=h)
    assert r.status_code == 200 and r.json()["source"] == "live"
    assert r.json()["subjects"][0]["course_code"] == "DAR301"


def test_matching_courses_links_studio(client, ctx, monkeypatch):
    data = _setup()
    h = _staff_headers(client)
    monkeypatch.setattr(darsyar_service, "_fetch_live", lambda professor: None)
    r = client.get(f"/api/v1/integration/professors/{EXT_ID}/matching-courses", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, "دست‌کم یک درس متناسب باید یافت شود"
    top = items[0]
    assert top["has_course"] is True and top["studio_url"] == f"/studio/{data['course_id']}"


def test_bulk_blocks_paste_flow(client, ctx):
    data = _setup()
    h = _staff_headers(client)
    vid = data["version_id"]
    payload = {"blocks": [
        {"type": "heading", "title": "بخش چسبانده‌شده"},
        {"type": "text", "body": "این متن توسط استاد چسبانده شده است."},
        {"type": "note", "title": "نکته", "body": "نکتهٔ مهم درس"},
    ]}
    r = client.post(f"/api/v1/content-versions/{vid}/blocks/bulk",
                    json=payload, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    blocks = body["blocks"]
    assert len(blocks) == 4  # ۱ بذری + ۳ جدید
    assert blocks[-1]["origin"] == "human" and blocks[-1]["type"] == "note"
    assert body["revision"] == 2
    # بلوک نامعتبر رد می‌شود
    r2 = client.post(f"/api/v1/content-versions/{vid}/blocks/bulk",
                     json={"blocks": [{"type": "evil"}]}, headers=h)
    assert r2.status_code in (400, 422)
