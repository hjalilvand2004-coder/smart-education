"""تست همگام‌سازی کاتالوگ پایه‌یار۳۶۰ (دروس + سرفصل‌ها) — با سرور mock، بدون شبکه.

پوشش: نرمال‌سازی دفاعی چند شکل پاسخ، طبقه‌بندی خطای احراز هویت با راهنمای
قابل‌اقدام، upsert idempotent، پیوند درس محلی هم‌کد، قاعده طلایی «بدون
بازنویسی بی‌صدا» (تغییر نسخه مرجع → پیش‌نویس + REVIEW_REQUIRED) و RBAC endpoint ها.
"""
import httpx
import pytest

from app.core.database import SessionLocal
from app.models.courses import Course
from app.models.identity import User
from app.services import payehyar_catalog
from app.services.payehyar_client import _HINTS, PayehyarClient, PayehyarError

PROBE_OK = {"openapi": "3.1.0", "info": {"title": "PayehYar360 — Shared Core & Master Data",
                                         "version": "1.0.8"}}

CATALOG = {
    "version": "catalog-2026-11",
    "courses": [
        {"reference_id": "11111111-1111-1111-1111-111111111111", "code": "PYR101",
         "title": "ریاضیات گسسته مرجع", "credits": 3, "term": "ترم اول",
         "department": "ریاضی", "degree_level": "کارشناسی", "field_of_study": "علوم کامپیوتر",
         "description": "درس نمونه مرجع یک",
         "reference_version": "v1",
         "chapters": [
             {"title": "منطق و اثبات",
              "topics": [{"reference_id": "t-pyr-1", "title": "منطق گزاره‌ای",
                          "suggested_hours": 4},
                         {"reference_id": "t-pyr-2", "title": "استقرای ریاضی",
                          "suggested_hours": 6}]},
             {"title": "نظریه مجموعه‌ها", "topics": [{"id": "t-pyr-3", "name": "مجموعه‌های متناهی"}]},
         ]},
        {"id": "22222222-2222-2222-2222-222222222222", "course_code": "PYR102",
         "course_name": "ساختمان داده مرجع", "units": "4",
         "syllabus_version": "v3",
         "syllabus": [{"chapter_title": "درخت‌ها", "topics": ["پیمایش", "درخت BST"]}]},
        {"bad": "record", "no_title_here": True},
        [1, 2, 3],
    ],
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    headers = request.headers
    if path == "/openapi.json":
        return httpx.Response(200, json=PROBE_OK)
    if path == "/api/v1/services/masterdata/catalog":
        if "x-api-key" not in headers:
            return httpx.Response(401, json={"code": "UNAUTHENTICATED",
                                             "message": "کلید API ارسال نشده است؛ هدر X-API-Key را تنظیم کنید.",
                                             "correlation_id": "c-1"})
        if headers["x-api-key"] != "good-key":
            return httpx.Response(401, json={"code": "UNAUTHENTICATED",
                                             "message": "کلید API نامعتبر یا قطع‌شده است.",
                                             "correlation_id": "c-2"})
        return httpx.Response(200, json=CATALOG)
    if path == "/api/v1/masterdata/instructors":
        if headers.get("x-dev-user") != "dev-prof":
            return httpx.Response(403, json={"code": "INSUFFICIENT_ROLE",
                                             "message": "برای این عملیات نقش لازم را ندارید.",
                                             "correlation_id": "c-4",
                                             "details": {"required_roles": ["steward", "tenant_admin"]}})
        return httpx.Response(200, json=[])
    if path == "/api/v1/masterdata/catalog":
        if headers.get("x-dev-user") != "dev-prof":
            return httpx.Response(403, json={"code": "INSUFFICIENT_ROLE",
                                             "message": "برای این عملیات نقش لازم را ندارید.",
                                             "correlation_id": "c-3",
                                             "details": {"required_roles": ["steward", "tenant_admin"]}})
        return httpx.Response(200, json=CATALOG)
    if path == "/api/v1/sync/changes":
        return httpx.Response(200, json={"changes": [], "cursor": 42})
    return httpx.Response(404, json={"code": "NOT_FOUND", "message": "یافت نشد."})


def _client(**kw) -> PayehyarClient:
    base = dict(base_url="http://mock", timeout=2, transport=httpx.MockTransport(_handler))
    base.update(kw)
    return PayehyarClient(**base)


@pytest.fixture()
def mock_client(monkeypatch):
    """کلاینت واقعی در ماژول کاتالوگ با transport mock و کلید معتبر جایگزین می‌شود."""
    monkeypatch.setattr(payehyar_catalog, "PayehyarClient",
                        lambda **kw: _client(api_key="good-key", **kw))


# ---------- نرمال‌سازی ----------

def test_normalize_catalog_defensive():
    norm = payehyar_catalog.normalize_catalog(CATALOG)
    assert len(norm["courses"]) == 2
    assert norm["warnings"], "رکوردهای نگاشت‌نشدنی باید هشدار بدهند"
    c1, c2 = norm["courses"]
    assert c1["code"] == "PYR101" and c1["credits"] == 3
    assert c1["chapters"][0]["topics"][0]["reference_id"] == "t-pyr-1"
    # رکورد دوم با کلیدهای جایگزین (course_code/course_name/units/سرفصل متنی)
    assert c2["code"] == "PYR102" and c2["credits"] == 4 and c2["reference_version"] == "v3"
    assert c2["chapters"][0]["topics"][0]["title"] == "پیمایش"


def test_normalize_catalog_shapes():
    assert len(payehyar_catalog.normalize_catalog(CATALOG["courses"])["courses"]) == 2
    assert len(payehyar_catalog.normalize_catalog({"items": CATALOG["courses"]})["courses"]) == 2
    assert payehyar_catalog.normalize_catalog([])["courses"] == []
    assert payehyar_catalog.normalize_catalog(None)["courses"] == []


# ---------- probe و خطای احراز هویت ----------

def test_probe_without_credentials():
    p = _client().probe()
    assert p["reachable"] is True
    assert p["service_version"] == "1.0.8"
    assert p["status"] == "NEEDS_API_KEY"
    assert "S360_PAYEHYAR_API_KEY" in p["hint"]


def test_probe_invalid_key():
    p = _client(api_key="wrong").probe()
    assert p["status"] == "INVALID_API_KEY"


def test_probe_dev_user_role_error():
    p = _client(dev_user="no-role").probe()
    assert p["status"] == "NEEDS_ROLE"
    assert p["required_roles"] == ["steward", "tenant_admin"]
    assert "steward" in p["hint"]


def test_fetch_catalog_fallback_to_dev_user():
    data = _client(dev_user="dev-prof").fetch_catalog()
    assert "courses" in data and len(data["courses"]) == 4


def test_fetch_catalog_without_any_credential_raises():
    with pytest.raises(PayehyarError) as ei:
        _client().fetch_catalog()
    assert ei.value.code == "NEEDS_API_KEY"
    assert ei.value.hint


# ---------- sync کاتالوگ ----------

def test_sync_full_creates_courses_and_drafts(client, prof_headers, mock_client):
    r = client.post("/api/v1/integration/payehyar/sync", headers=prof_headers,
                    json={"mode": "FULL"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "OK", data
    assert data["courses_created"] == 2
    assert data["syllabus_drafts_created"] == 2
    assert data["probe_status"] == "OK"

    db = SessionLocal()
    try:
        c1 = db.query(Course).filter(Course.code == "PYR101").first()
        assert c1 is not None
        assert c1.reference_system == "baseyar360"
        assert c1.reference_id == "11111111-1111-1111-1111-111111111111"
        assert c1.owner_system == "پایه‌یار۳۶۰"
        assert c1.sync_state == "VALID"
        assert c1.last_synced_at is not None
        # نسخه پیش‌نویس REFERENCE_SYNC با موضوع‌های نگاشت‌شده
        from app.models.syllabus import SyllabusTopic, SyllabusVersion
        sv = db.query(SyllabusVersion).filter(SyllabusVersion.course_id == c1.id).first()
        assert sv is not None and sv.source_kind == "REFERENCE_SYNC"
        assert sv.status == "DRAFT" and sv.reference_version == "v1"
        topics = db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == sv.id,
                                                SyllabusTopic.kind == "TOPIC").all()
        assert {t.reference_id for t in topics} == {"t-pyr-1", "t-pyr-2", "t-pyr-3"}
    finally:
        db.close()


def test_sync_full_idempotent(client, prof_headers, mock_client):
    client.post("/api/v1/integration/payehyar/sync", headers=prof_headers, json={"mode": "FULL"})
    r = client.post("/api/v1/integration/payehyar/sync", headers=prof_headers, json={"mode": "FULL"})
    data = r.json()
    assert data["courses_created"] == 0
    assert data["courses_updated"] == 0
    assert data["up_to_date"] == 2
    assert data["syllabus_drafts_created"] == 0


def test_sync_links_existing_local_course(client, ctx, prof_headers, monkeypatch):
    """درس محلی هم‌کد به مرجع پیوند داده می‌شود؛ رکورد تکراری ساخته نمی‌شود."""
    # کاتالوگ اختصاصی با کد متفاوت از تست‌های دیگر (کد درس یکتاست در کل سشن)
    link_catalog = {
        "version": "catalog-link",
        "courses": [{"reference_id": "33333333-3333-3333-3333-333333333333",
                     "code": "PYR201", "title": "شبیه‌سازی مرجع", "credits": 3,
                     "reference_version": "v1",
                     "chapters": [{"title": "روش مونت‌کارلو",
                                   "topics": [{"reference_id": "t-pyr-201",
                                               "title": "نمونه‌گیری تصادفی"}]}]}],
    }

    def _handler3(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=PROBE_OK)
        if request.url.path == "/api/v1/services/masterdata/catalog":
            assert request.headers["x-api-key"] == "link-key"
            return httpx.Response(200, json=link_catalog)
        return httpx.Response(404)

    class CLink(PayehyarClient):
        def __init__(self, **kw):
            super().__init__(base_url="http://mock", timeout=2, api_key="link-key",
                             transport=httpx.MockTransport(_handler3), **kw)

    monkeypatch.setattr(payehyar_catalog, "PayehyarClient", CLink)

    db = SessionLocal()
    try:
        prof = db.query(User).filter(User.username == "prof_test").first()
        db.add(Course(code="PYR201", title="شبیه‌سازی محلی", credits=2,
                      created_by=prof.id))
        db.commit()
    finally:
        db.close()

    r = client.post("/api/v1/integration/payehyar/sync", headers=prof_headers,
                    json={"mode": "FULL"})
    data = r.json()
    assert data["courses_created"] == 0, data
    assert data["courses_updated"] == 1, data  # پیوند + به‌روزرسانی اطلاعات
    db = SessionLocal()
    try:
        assert db.query(Course).filter(Course.code == "PYR201").count() == 1
        c = db.query(Course).filter(Course.code == "PYR201").first()
        assert c.reference_id == "33333333-3333-3333-3333-333333333333"
        assert c.reference_system == "baseyar360"
    finally:
        db.close()


def test_sync_version_change_needs_review(client, prof_headers, mock_client, monkeypatch):
    """تغییر نسخه مرجع → پیش‌نویس جدید + REVIEW_REQUIRED؛ نسخه قبلی دست‌نخورده."""
    client.post("/api/v1/integration/payehyar/sync", headers=prof_headers, json={"mode": "FULL"})
    db = SessionLocal()
    try:
        old_sv_status = {}
        from app.models.syllabus import SyllabusVersion
        for sv in db.query(SyllabusVersion).filter(
                SyllabusVersion.source_kind == "REFERENCE_SYNC").all():
            old_sv_status[str(sv.id)] = sv.status
    finally:
        db.close()

    changed = {
        "version": "catalog-2026-12",
        "courses": [{
            "reference_id": "11111111-1111-1111-1111-111111111111", "code": "PYR101",
            "title": "ریاضیات گسسته مرجع", "reference_version": "v2",
            "chapters": [{"title": "منطق و اثبات",
                          "topics": [{"reference_id": "t-pyr-1", "title": "منطق گزاره‌ای (بازنویسی)",
                                      "suggested_hours": 4},
                                     {"reference_id": "t-pyr-9", "title": "موضوع تازه"}]}],
        }],
    }

    def _handler2(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=PROBE_OK)
        if request.url.path == "/api/v1/services/masterdata/catalog":
            assert request.headers["x-api-key"] == "good-key"
            return httpx.Response(200, json=changed)
        return httpx.Response(404)

    class C2(PayehyarClient):
        def __init__(self, **kw):
            super().__init__(base_url="http://mock", timeout=2, api_key="good-key",
                             transport=httpx.MockTransport(_handler2), **kw)

    monkeypatch.setattr(payehyar_catalog, "PayehyarClient", C2)
    r = client.post("/api/v1/integration/payehyar/sync", headers=prof_headers,
                    json={"mode": "FULL"})
    data = r.json()
    assert data["status"] == "PARTIAL" and data["review_required"] == 1, data
    # مشخصات درس تغییر نکرده (فقط نسخه مرجع) → به‌روزرسانی حساب نمی‌شود
    assert data["courses_created"] == 0 and data["courses_updated"] == 0 \
        and data["up_to_date"] == 1

    db = SessionLocal()
    try:
        from app.models.syllabus import SyllabusVersion
        c = db.query(Course).filter(Course.code == "PYR101").first()
        assert c.sync_state == "REVIEW_REQUIRED"
        drafts = db.query(SyllabusVersion).filter(
            SyllabusVersion.course_id == c.id,
            SyllabusVersion.reference_version == "v2").all()
        assert len(drafts) == 1
        # نسخه‌های قبلی دست‌نخورده ماندند (قاعده طلایی)
        for sv_id, st in old_sv_status.items():
            assert db.get(SyllabusVersion, sv_id).status == st
    finally:
        db.close()


def test_sync_auth_failure_logged_with_hint(client, prof_headers, mock_client, monkeypatch):
    """بدون کلید: اجرا FAILED با کد و راهنمای دقیق — نه کرش، نه داده ساختگی."""
    class CNoKey(PayehyarClient):
        def __init__(self, **kw):
            super().__init__(base_url="http://mock", timeout=2,
                             transport=httpx.MockTransport(_handler), **kw)

    def _probe_fail(self):
        # همان متن راهنمای واقعی کلاینت (بدون کلید، endpoint سرویس‌ها 401 می‌دهد)
        return {"base_url": "http://mock", "reachable": True, "status": "NEEDS_API_KEY",
                "hint": _HINTS["NEEDS_API_KEY"], "required_roles": []}

    monkeypatch.setattr(CNoKey, "probe", _probe_fail)
    monkeypatch.setattr(payehyar_catalog, "PayehyarClient", CNoKey)
    r = client.post("/api/v1/integration/payehyar/sync", headers=prof_headers,
                    json={"mode": "FULL"})
    data = r.json()
    assert data["status"] == "FAILED"
    assert data["probe_status"] == "NEEDS_API_KEY"
    assert "S360_PAYEHYAR_API_KEY" in (data["error_message"] or "")


def test_status_endpoint(client, prof_headers, mock_client):
    r = client.get("/api/v1/integration/payehyar/status", headers=prof_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["probe"]["service_title"].startswith("PayehYar360")
    assert d["config"]["base_url"] == "http://mock"
    assert "reference_courses" in d["counts"]


def test_rbac_students_forbidden(client, st_headers):
    r = client.get("/api/v1/integration/payehyar/status", headers=st_headers)
    assert r.status_code == 403
    r = client.post("/api/v1/integration/payehyar/sync", headers=st_headers, json={})
    assert r.status_code == 403
