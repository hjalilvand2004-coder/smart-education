"""تست همگام‌سازی کاتالوگ پایه‌یار۳۶۰ — با قرارداد مستند راهنمای یکپارچه‌سازی v1.0.12.

mockها شکل واقعی پاسخ سرویس را بازمی‌سازند:
- GET /api/v1/services/masterdata/unique-courses → {ok, domain, count, generated_at, items[]}
- GET /api/v1/services/masterdata/split-courses → ۵۰۰ با باگ واقعی سرویس (NameError 'uc')
- GET /api/v1/services/masterdata/course-syllabi → سرفصل مصوب با topics (seq/hours)

پوشش: نرمال‌سازی شکل مستند + تطبیق عنوان سرفصل، تاب‌آوری در برابر خطای دامنه،
طبقه‌بندی خطای احراز هویت با راهنمای قابل‌اقدام، upsert idempotent، پیوند درس محلی
هم‌کد، قاعده طلایی «بدون بازنویسی بی‌صدا» و RBAC endpoint ها.
"""
import httpx
import pytest

from app.core.database import SessionLocal
from app.models.courses import Course
from app.models.identity import User
from app.services import payehyar_catalog
from app.services.payehyar_client import _HINTS, PayehyarClient, PayehyarError

PROBE_OK = {"openapi": "3.1.0", "info": {"title": "PayehYar360 — Shared Core & Master Data",
                                         "version": "1.0.12"}}

# شکل مستند راهنما — بخش ۷ (unique-courses)
UNIQUE_ITEMS = [
    {"set": "unique_courses", "code": "PYR101", "title": "ریاضیات گسسته مرجع",
     "parent_code": None,
     "attrs": {"section": "تخصصی", "unit_theory": 3, "unit_practice": 1,
               "capacity": 30, "prerequisite": "ریاضیات عمومی 1",
               "source": "darsyar360"},
     "status": "active", "updated_at": "2026-11-24T15:41:02.000000"},
    {"set": "unique_courses", "code": "PYR102", "title": "ساختمان داده مرجع",
     "parent_code": None,
     "attrs": {"section": "اصلی", "unit_theory": 4, "unit_practice": None,
               "capacity": 30, "prerequisite": None, "source": "darsyar360"},
     "status": "active", "updated_at": "2026-11-24T10:00:00.000000"},
]

SPLIT_500 = {"code": "INTERNAL_ERROR",
             "message": "خطای غیرمنتظره: NameError: name 'uc' is not defined",
             "correlation_id": "9bc70ca5-b7d5-47bd-a792-2ea40d3d6bd2"}

# شکل مستند — بخش ۷-۳ (course-syllabi)
SYLLABI_ITEMS = [
    {"source_set": "CE403", "source_file": "NP1400", "course_code": "CSE-999",
     "title_fa": "ریاضیات گسسته مرجع", "title_en": "Discrete Mathematics",
     "course_type": "نظری، تخصصی", "units": {"theory": 3, "practice": 1},
     "prerequisites": ["ریاضیات عمومی 1"], "corequisites": [],
     "general_goal": "آشنایی با منطق و اثبات", "evaluation": None,
     "references": ["کتاب روزن"], "has_text": True,
     "topics": [{"seq": 1, "title": "منطق گزاره‌ای", "hours": 4, "hours_practice": None},
                {"seq": 2, "title": "استقرای ریاضی", "hours": 6, "hours_practice": None}],
     "updated_at": "2026-11-24T16:00:00.000000"},
    {"source_set": "CE403", "source_file": "NP1500", "course_code": "CSE-106",
     "title_fa": "برنامه‌نویسی بی‌تطبیق", "title_en": "Advanced Programming",
     "units": {"theory": 3, "practice": None}, "has_text": True,
     "topics": [{"seq": 1, "title": "اشاره‌گرها", "hours": None, "hours_practice": None}],
     "updated_at": "2026-11-24T09:00:00.000000"},
]


def _domain_body(domain: str, items: list) -> dict:
    return {"ok": True, "domain": domain, "title": "دامنه آزمون", "count": len(items),
            "generated_at": "2026-11-24T04:17:59+00:00",
            "generated_at_jalali": "۱۴۰۵/۰۹/۰۳", "items": items}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    headers = request.headers
    if path == "/openapi.json":
        return httpx.Response(200, json=PROBE_OK)
    if path.startswith("/api/v1/services/masterdata/"):
        domain = path.rsplit("/", 1)[-1]
        if "x-api-key" not in headers:
            return httpx.Response(401, json={"code": "UNAUTHENTICATED",
                                             "message": "کلید API ارسال نشده است؛ هدر X-API-Key را تنظیم کنید.",
                                             "correlation_id": "c-1"})
        if headers["x-api-key"] != "good-key":
            return httpx.Response(401, json={"code": "UNAUTHENTICATED",
                                             "message": "کلید API نامعتبر یا قطع‌شده است.",
                                             "correlation_id": "c-2"})
        if domain == "unique-courses":
            return httpx.Response(200, json=_domain_body(domain, UNIQUE_ITEMS))
        if domain == "split-courses":
            return httpx.Response(500, json=SPLIT_500)  # باگ واقعی سرویس
        if domain == "course-syllabi":
            return httpx.Response(200, json=_domain_body(domain, SYLLABI_ITEMS))
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "یافت نشد."})
    if path == "/api/v1/masterdata/instructors":
        if headers.get("x-dev-user") != "dev-prof":
            return httpx.Response(403, json={"code": "INSUFFICIENT_ROLE",
                                             "message": "برای این عملیات نقش لازم را ندارید.",
                                             "correlation_id": "c-4",
                                             "details": {"required_roles": ["steward", "tenant_admin"]}})
        return httpx.Response(200, json=[])
    if path == "/api/v1/sync/changes":
        return httpx.Response(200, json={"changes": [], "cursor_next": 42, "has_more": False})
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


# ---------- نرمال‌سازی شکل مستند ----------

def test_normalize_documented_course():
    c, warn = payehyar_catalog.normalize_documented_course(UNIQUE_ITEMS[0])
    assert warn is None
    assert c["reference_id"] == "py:PYR101"
    assert c["code"] == "PYR101"
    assert c["credits"] == 4          # ۳ نظری + ۱ عملی
    assert c["degree_level"] == "تخصصی"
    assert c["description"] == "پیش‌نیاز: ریاضیات عمومی 1"
    assert c["reference_version"].startswith("2026-11-24T15:41:02")
    # رکورد تفکیکی (split)
    split = {"set": "split_courses", "code": None, "title": "ریاضیات گسسته",
             "unique_course_code": "PYR101", "parent_code": "PYR101",
             "attrs": {"year_label": "1403", "cohort_set": "پایه‌یازدهم",
                       "unit_theory": 3, "external_id": "12", "source": "darsyar360"},
             "status": "active", "updated_at": "2026-11-24T15:41:02.000000"}
    c2, warn2 = payehyar_catalog.normalize_documented_course(split)
    assert warn2 is None
    assert c2["reference_id"] == "py-split:PYR101:1403"
    assert c2["code"] == "PYR101-1403"
    assert c2["title"] == "ریاضیات گسسته (1403)"
    assert c2["degree_level"] == "پایه‌یازدهم"


def test_normalize_catalog_defensive():
    norm = payehyar_catalog.normalize_catalog({"courses": UNIQUE_ITEMS + [{"bad": "record"}]})
    assert len(norm["courses"]) == 2
    assert norm["warnings"], "رکوردهای نگاشت‌نشدنی باید هشدار بدهند"


def test_normalize_catalog_with_syllabi_merge():
    raw = {"courses": UNIQUE_ITEMS, "syllabi": SYLLABI_ITEMS,
           "warnings": ["split-courses: REMOTE_ERROR — NameError"]}
    norm = payehyar_catalog.normalize_catalog(raw)
    assert len(norm["courses"]) == 2
    c1 = norm["courses"][0]
    # سرفصل مصوب با تطبیق عنوان به درس یکتا چسبیده است
    assert c1["chapters"], "سرفصل تطبیق‌یافته باید وصل شود"
    topics = c1["chapters"][0]["topics"]
    assert [t["reference_id"] for t in topics] == ["CE403:NP1400:1", "CE403:NP1400:2"]
    assert topics[0]["suggested_hours"] == 4
    # نسخه مرجع با updated_at سرفصل به‌روز می‌شود (تغییر سرفصل → بررسی استاد)
    assert c1["reference_version"].startswith("2026-11-24T16:00:00")
    joined = " ".join(norm["warnings"])
    assert "split-courses" in joined and "بدون تطبیق" in joined


def test_normalize_catalog_shapes_legacy():
    # شکل عمومی قدیمی هم پذیرفته می‌شود (سازگاری رو به عقب)
    legacy = [{"reference_id": "x1", "code": "L1", "title": "درس قدیمی",
               "chapters": [{"title": "فصل ۱", "topics": ["موضوع الف"]}]}]
    norm = payehyar_catalog.normalize_catalog(legacy)
    assert len(norm["courses"]) == 1
    assert norm["courses"][0]["chapters"][0]["topics"][0]["title"] == "موضوع الف"
    assert payehyar_catalog.normalize_catalog({"items": UNIQUE_ITEMS})["courses"]
    assert payehyar_catalog.normalize_catalog([])["courses"] == []
    assert payehyar_catalog.normalize_catalog(None)["courses"] == []


# ---------- probe و خطای احراز هویت ----------

def test_probe_without_credentials():
    p = _client().probe()
    assert p["reachable"] is True
    assert p["service_version"] == "1.0.12"
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


def test_probe_ok_with_valid_key():
    p = _client(api_key="good-key").probe()
    assert p["status"] == "OK"
    assert p["auth_mode"] == "API_KEY"


def test_fetch_catalog_resilient_to_domain_error():
    """باگ دامنه split-courses نباید واکشی کل کاتالوگ را متوقف کند."""
    data = _client(api_key="good-key").fetch_catalog()
    assert len(data["courses"]) == 2
    assert len(data["syllabi"]) == 2
    assert any("split-courses" in w for w in data["warnings"])
    assert data["meta"]["domains"]["unique-courses"]["count"] == 2


def test_fetch_catalog_without_key_raises():
    with pytest.raises(PayehyarError) as ei:
        _client(dev_user="dev-prof").fetch_catalog()
    assert ei.value.code == "NEEDS_API_KEY"


# ---------- sync کاتالوگ ----------

def test_sync_full_creates_courses_and_draft(client, prof_headers, mock_client):
    r = client.post("/api/v1/integration/payehyar/sync", headers=prof_headers,
                    json={"mode": "FULL"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "OK", data
    assert data["courses_created"] == 2
    assert data["syllabus_drafts_created"] == 1  # فقط سرفصل تطبیق‌یافته
    assert data["probe_status"] == "OK"
    assert data["warnings"], "خطای split و سرفصل بی‌تطبیق باید در warnings باشد"

    db = SessionLocal()
    try:
        c1 = db.query(Course).filter(Course.code == "PYR101").first()
        assert c1 is not None
        assert c1.reference_system == "baseyar360"
        assert c1.reference_id == "py:PYR101"
        assert c1.owner_system == "پایه‌یار۳۶۰"
        assert c1.sync_state == "VALID"
        assert c1.last_synced_at is not None
        from app.models.syllabus import SyllabusTopic, SyllabusVersion
        sv = db.query(SyllabusVersion).filter(SyllabusVersion.course_id == c1.id).first()
        assert sv is not None and sv.source_kind == "REFERENCE_SYNC"
        assert sv.status == "DRAFT"
        topics = db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == sv.id,
                                                SyllabusTopic.kind == "TOPIC").all()
        assert {t.reference_id for t in topics} == {"CE403:NP1400:1", "CE403:NP1400:2"}
        c2 = db.query(Course).filter(Course.code == "PYR102").first()
        assert c2.reference_id == "py:PYR102"
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
    link_unique = [{"set": "unique_courses", "code": "PYR201", "title": "شبیه‌سازی مرجع",
                    "attrs": {"section": "تخصصی", "unit_theory": 3, "unit_practice": None},
                    "status": "active", "updated_at": "2026-11-24T12:00:00.000000"}]

    def _handler3(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/openapi.json":
            return httpx.Response(200, json=PROBE_OK)
        if path == "/api/v1/services/masterdata/unique-courses":
            assert request.headers["x-api-key"] == "link-key"
            return httpx.Response(200, json=_domain_body("unique-courses", link_unique))
        if path == "/api/v1/services/masterdata/split-courses":
            return httpx.Response(500, json=SPLIT_500)
        if path == "/api/v1/services/masterdata/course-syllabi":
            return httpx.Response(200, json=_domain_body("course-syllabi", []))
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
        assert c.reference_id == "py:PYR201"
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

    changed_unique = [dict(UNIQUE_ITEMS[0], updated_at="2026-12-01T00:00:00.000000")]
    changed_syllabi = [dict(SYLLABI_ITEMS[0],
                            topics=[{"seq": 1, "title": "منطق گزاره‌ای (بازنویسی)",
                                     "hours": 4, "hours_practice": None},
                                    {"seq": 9, "title": "موضوع تازه", "hours": None,
                                     "hours_practice": None}],
                            updated_at="2026-12-01T00:00:00.000000")]

    def _handler2(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/openapi.json":
            return httpx.Response(200, json=PROBE_OK)
        if path == "/api/v1/services/masterdata/unique-courses":
            assert request.headers["x-api-key"] == "good-key"
            return httpx.Response(200, json=_domain_body("unique-courses", changed_unique))
        if path == "/api/v1/services/masterdata/split-courses":
            return httpx.Response(500, json=SPLIT_500)
        if path == "/api/v1/services/masterdata/course-syllabi":
            return httpx.Response(200, json=_domain_body("course-syllabi", changed_syllabi))
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
            SyllabusVersion.reference_version == "2026-12-01T00:00:00.000000").all()
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
