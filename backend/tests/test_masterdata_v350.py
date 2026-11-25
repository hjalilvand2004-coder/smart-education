"""تست صفحه‌های MDM پایه‌یار۳۶۰ + امتیاز اساتید (v3.5.0).

پوشش: همگام‌سازی تفکیکی سه دامنه (با کلاینت جعلی)، نمای کلی، لیست/جستجو،
سلسله‌مراتب یکتا→تفکیکی→سرفصل، تولید محتوا برای سرفصل درسی (با gateway جعلی)،
خروجی HTML با امتیاز خودکار و قاعدهٔ ضدتکرار، جدول برترین‌ها و RBAC.
"""
import pytest

from app.core.database import SessionLocal
from app.models.content import ContentDocument, ContentPlan, ContentVersion
from app.models.concepts import TopicConcept
from app.models.courses import Course
from app.models.exports import ExportArtifact, ExportJob
from app.models.journey import PayehyarRecord
from app.models.points import ContributionPoint
from app.models.syllabus import LearningObjective, SyllabusTopic, SyllabusVersion
from app.services import masterdata as md
from app.services.payehyar_client import PayehyarError

SAMPLES = {
    "unique-courses": [
        {"set": "unique_courses", "code": "1001", "title": "مباحث ویژه پایگاه داده",
         "parent_code": None,
         "attrs": {"section": "اصلی", "unit_theory": 2, "unit_practice": 1,
                   "capacity": 40, "prerequisite": "پایگاه داده"},
         "status": "active", "updated_at": "2026-11-24T10:00:00"},
        {"set": "unique_courses", "code": "1002", "title": "شبکه‌های کامپیوتری",
         "attrs": {"section": "اصلی", "unit_theory": 3, "unit_practice": 0},
         "status": "active", "updated_at": "2026-11-24T10:00:00"},
    ],
    "split-courses": [
        {"set": "split_courses", "title": "مباحث ویژه پایگاه داده",
         "unique_course_code": "1001",
         "attrs": {"year_label": "1404-1", "external_id": "sp-1",
                   "unit_theory": 2, "unit_practice": 1},
         "status": "active", "updated_at": "2026-11-24T10:05:00"},
    ],
    "course-syllabi": [
        {"source_set": "s1394", "source_file": "f01",
         "title_fa": "مباحث ویژه پایگاه داده",
         "topics": [{"seq": 1, "title": "مدل سازی داده", "hours": 4},
                    {"seq": 2, "title": "جستجو و بهینه پرس و جو", "hours": 6}],
         "updated_at": "2026-11-24T09:00:00"},
    ],
}

SYNC_PATH = "/api/v1/integration/payehyar/mdm/{d}/sync"


class StubClient:
    def __init__(self, **kw):
        pass

    def fetch_domain(self, domain, since=None):
        return {"ok": True, "domain": domain,
                "count": len(SAMPLES[domain]), "items": SAMPLES[domain]}


class ExplodingClient(StubClient):
    def fetch_domain(self, domain, since=None):
        raise PayehyarError("AUTH_FAILED", "کلید API نامعتبر است.",
                            hint="در پنل پایه‌یار کلید را بررسی کنید.")


class StubGateway:
    """جایگزین AIGateway در content_service — خروجی قطعی برای تست."""

    def __init__(self, db):
        pass

    def run(self, purpose, inputs, schema=None, created_by=None, job_id=None):
        if purpose == "content_plan":
            return schema(title="طرح درس", learning_objectives=["هدف ۱"],
                          prerequisites=[], sections_order=[], examples=[],
                          timing_summary="۹۰ دقیقه", assessment_method="پروژه")
        if purpose == "content_generation":
            from app.ai.schemas import AIBlock
            return schema(title="مدل سازی داده",
                          blocks=[AIBlock(type="text", title="مقدمه",
                                          body="متن آموزشی نمونه برای سرفصل مدل سازی داده"),
                                  AIBlock(type="summary", title="جمع‌بندی",
                                          body="خلاصهٔ مفاهیم کلیدی")])
        raise AssertionError(f"purpose ناشناخته: {purpose}")


@pytest.fixture(autouse=True)
def _clean_db():
    """پاک‌سازی جراحیِ فقط داده‌های این فایل — بدون دست‌زدن به سید سراسری ctx.

    جدول‌های مشترک (سرفصل/محتوا/مفاهیم سید ctx) پاک نمی‌شوند؛ فقط رکوردهای
    وابسته به درس‌های آزمایشی کد 1001/1002 و رکوردهای سه دامنهٔ MDM حذف می‌شوند
    تا هم تعامل با فایل‌های تست دیگر از بین برود و هم اجرای مکرر فایل idempotent بماند."""
    db = SessionLocal()
    my_courses = [c.id for c in db.query(Course.id).filter(
        Course.code.in_(["1001", "1002"])).all()]
    sv_ids = [s.id for s in db.query(SyllabusVersion.id).filter(
        SyllabusVersion.course_id.in_(my_courses)).all()] if my_courses else []
    topic_ids = [t.id for t in db.query(SyllabusTopic.id).filter(
        SyllabusTopic.syllabus_version_id.in_(sv_ids)).all()] if sv_ids else []
    doc_ids = [d.id for d in db.query(ContentDocument.id).filter(
        ContentDocument.syllabus_version_id.in_(sv_ids)).all()] if sv_ids else []
    ver_ids = [v.id for v in db.query(ContentVersion.id).filter(
        ContentVersion.document_id.in_(doc_ids)).all()] if doc_ids else []
    if ver_ids:
        job_ids = [j.id for j in db.query(ExportJob.id).filter(
            ExportJob.content_version_id.in_(ver_ids)).all()]
        if job_ids:
            db.query(ExportArtifact).filter(
                ExportArtifact.export_job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(ExportJob).filter(
            ExportJob.content_version_id.in_(ver_ids)).delete(synchronize_session=False)
    db.query(ContributionPoint).delete(synchronize_session=False)
    if ver_ids:
        db.query(ContentVersion).filter(
            ContentVersion.id.in_(ver_ids)).delete(synchronize_session=False)
    if doc_ids:
        plan_ids = [p.id for p in db.query(ContentPlan.id).filter(
            ContentPlan.document_id.in_(doc_ids)).all()]
        if plan_ids:
            db.query(ContentPlan).filter(
                ContentPlan.id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(ContentDocument).filter(
            ContentDocument.id.in_(doc_ids)).delete(synchronize_session=False)
    if sv_ids:
        db.query(LearningObjective).filter(
            LearningObjective.syllabus_version_id.in_(sv_ids)).delete(synchronize_session=False)
    if topic_ids:
        db.query(TopicConcept).filter(
            TopicConcept.topic_id.in_(topic_ids)).delete(synchronize_session=False)
        db.query(SyllabusTopic).filter(
            SyllabusTopic.id.in_(topic_ids)).delete(synchronize_session=False)
    if sv_ids:
        db.query(SyllabusVersion).filter(
            SyllabusVersion.id.in_(sv_ids)).delete(synchronize_session=False)
    if my_courses:
        db.query(Course).filter(Course.id.in_(my_courses)).delete(synchronize_session=False)
    db.query(PayehyarRecord).filter(PayehyarRecord.domain.in_(
        ["unique-courses", "split-courses", "course-syllabi"])).delete(
        synchronize_session=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    yield


def _patch_client(monkeypatch, cls=StubClient):
    monkeypatch.setattr(md.payehyar_connection, "client_for",
                        lambda db, **kw: cls())
    monkeypatch.setattr("app.services.content_service.AIGateway", StubGateway)


# ---------- همگام‌سازی سه دامنه ----------

def test_sync_three_domains_and_overview(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch)
    for d, created in (("unique-courses", 2), ("split-courses", 1),
                       ("course-syllabi", 1)):
        r = client.post(SYNC_PATH.format(d=d), headers=prof_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True and body["created"] == created
        assert "انجام شد" in body["message"]
    # همگام‌سازی مجدد → بدون تغییر واقعی
    r = client.post(SYNC_PATH.format(d="unique-courses"), headers=prof_headers)
    assert r.json()["up_to_date"] == 2 and r.json()["created"] == 0

    ov = client.get("/api/v1/integration/payehyar/mdm/overview", headers=prof_headers).json()
    assert ov["domains"]["unique-courses"]["count"] == 2
    assert ov["domains"]["split-courses"]["count"] == 1
    assert ov["domains"]["course-syllabi"]["count"] == 1
    assert ov["topic_total"] == 2


def test_sync_remote_error_shows_hint(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch, ExplodingClient)
    r = client.post(SYNC_PATH.format(d="unique-courses"), headers=prof_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AUTH_FAILED"
    assert "پنل پایه‌یار" in body["error"]["hint"]


def test_invalid_domain_rejected(client, prof_headers):
    assert client.post(SYNC_PATH.format(d="professors"),
                       headers=prof_headers).status_code == 422
    assert client.get("/api/v1/integration/payehyar/mdm/professors",
                      headers=prof_headers).status_code == 422


# ---------- لیست، جستجو و سلسله‌مراتب ----------

def test_list_search_and_units(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch)
    for d in SAMPLES:
        client.post(SYNC_PATH.format(d=d), headers=prof_headers)
    r = client.get("/api/v1/integration/payehyar/mdm/unique-courses?q=پایگاه",
                   headers=prof_headers)
    items = r.json()["items"]
    assert r.json()["total"] == 1
    assert items[0]["code"] == "1001"
    assert items[0]["units"] == 3  # ۲ نظری + ۱ عملی
    assert items[0]["prerequisite"] == "پایگاه داده"


def test_hierarchy_unique_split_syllabus(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch)
    for d in SAMPLES:
        client.post(SYNC_PATH.format(d=d), headers=prof_headers)
    r = client.get("/api/v1/integration/payehyar/hierarchy/1001", headers=prof_headers)
    body = r.json()
    assert body["unique"]["code"] == "1001"
    assert len(body["split_courses"]) == 1
    assert body["split_courses"][0]["year_label"] == "1404-1"
    assert len(body["syllabi"]) == 1
    assert len(body["syllabi"][0]["topics"]) == 2


# ---------- تولید محتوا + خروجی + امتیاز ----------

def _make_course():
    db = SessionLocal()
    db.add(Course(code="1001", title="مباحث ویژه پایگاه داده"))
    db.commit()
    db.close()


def test_generate_content_awards_points(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch)
    for d in SAMPLES:
        client.post(SYNC_PATH.format(d=d), headers=prof_headers)
    _make_course()
    rec = client.get("/api/v1/integration/payehyar/mdm/course-syllabi",
                     headers=prof_headers).json()["items"][0]

    r = client.post(f"/api/v1/integration/payehyar/syllabus-records/{rec['id']}/generate",
                    headers=prof_headers, json={"topic_seq": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["points_awarded"] == 25
    assert body["qc_blocks"] == 2
    assert body["version_status"] == "GENERATED"

    me = client.get("/api/v1/points/me", headers=prof_headers).json()
    assert me["total"] == 25
    assert me["by_action"]["CONTENT_GENERATE"] == 25

    # تولید نسخهٔ دوم همان سرفصل → امتیاز جدید (هر نسخه یک‌بار)
    r2 = client.post(f"/api/v1/integration/payehyar/syllabus-records/{rec['id']}/generate",
                     headers=prof_headers, json={"topic_seq": 1})
    assert r2.json()["version_number"] == 2
    me2 = client.get("/api/v1/points/me", headers=prof_headers).json()
    assert me2["total"] == 50


def test_export_html_awards_points_once(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch)
    for d in SAMPLES:
        client.post(SYNC_PATH.format(d=d), headers=prof_headers)
    _make_course()
    rec = client.get("/api/v1/integration/payehyar/mdm/course-syllabi",
                     headers=prof_headers).json()["items"][0]
    vid = client.post(f"/api/v1/integration/payehyar/syllabus-records/{rec['id']}/generate",
                      headers=prof_headers, json={"topic_seq": 1}).json()["version_id"]

    r = client.get(f"/api/v1/integration/payehyar/content-versions/{vid}/export/HTML",
                   headers=prof_headers)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "مدل سازی داده" in r.text  # عنوان سرفصل در خروجی

    me = client.get("/api/v1/points/me", headers=prof_headers).json()
    assert me["total"] == 30  # ۲۵ تولید + ۵ خروجی
    # خروجی تکراری همان قالب → امتیاز اضافه نمی‌گیرد (قاعدهٔ ضدتکرار)
    client.get(f"/api/v1/integration/payehyar/content-versions/{vid}/export/HTML",
               headers=prof_headers)
    me2 = client.get("/api/v1/points/me", headers=prof_headers).json()
    assert me2["total"] == 30

    board = client.get("/api/v1/points/leaderboard", headers=prof_headers).json()
    assert board["items"] and board["items"][0]["total"] == 30


def test_export_invalid_format_rejected(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch)
    assert client.get("/api/v1/integration/payehyar/content-versions/xyz/export/CSV",
                      headers=prof_headers).status_code == 404  # نسخهٔ ناموجود
    for d in SAMPLES:
        client.post(SYNC_PATH.format(d=d), headers=prof_headers)
    _make_course()
    rec = client.get("/api/v1/integration/payehyar/mdm/course-syllabi",
                     headers=prof_headers).json()["items"][0]
    vid = client.post(f"/api/v1/integration/payehyar/syllabus-records/{rec['id']}/generate",
                      headers=prof_headers, json={"topic_seq": 2}).json()["version_id"]
    assert client.get(f"/api/v1/integration/payehyar/content-versions/{vid}/export/CSV",
                      headers=prof_headers).status_code == 422


def test_record_detail_links_course_and_points(client, prof_headers, monkeypatch):
    _patch_client(monkeypatch)
    for d in SAMPLES:
        client.post(SYNC_PATH.format(d=d), headers=prof_headers)
    _make_course()
    rec = client.get("/api/v1/integration/payehyar/mdm/course-syllabi",
                     headers=prof_headers).json()["items"][0]
    client.post(f"/api/v1/integration/payehyar/syllabus-records/{rec['id']}/generate",
                headers=prof_headers, json={"topic_seq": 2})
    d = client.get(f"/api/v1/integration/payehyar/syllabus-records/{rec['id']}",
                   headers=prof_headers).json()
    assert d["course"]["code"] == "1001"
    topics = {t["seq"]: t for t in d["topics"]}
    assert topics[2]["version_id"] and topics[2]["points"] == 25
    assert topics[1]["version_id"] is None


# ---------- RBAC ----------

def test_mdm_rbac_for_student(client, st_headers):
    assert client.get("/api/v1/integration/payehyar/mdm/unique-courses",
                      headers=st_headers).status_code == 403
    assert client.post(SYNC_PATH.format(d="unique-courses"),
                       headers=st_headers).status_code == 403
    assert client.get("/api/v1/integration/payehyar/mdm/overview",
                      headers=st_headers).status_code == 403
    assert client.get("/api/v1/points/me", headers=st_headers).status_code == 403
    assert client.get("/api/v1/points/leaderboard", headers=st_headers).status_code == 403
