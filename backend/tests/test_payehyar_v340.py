"""تست یکپارچگی کامل پایه‌یار۳۶۰ (v3.4.0) — قرارداد کامل سند فنی اتصال.

پوشش: هدرهای X-Correlation-ID/Idempotency-Key، OAuth2 client_credentials با کش
توکن، retry نمایی روی 502/503/504، کش ETag و پاسخ 304، گزارش health/ready،
واکشی دامنه‌های گسترش‌یافته با fallback مدیریتی، مخزن عمومی رکوردها (یکتا و
تفکیکی)، پردازش idempotent رویدادها (upsert/delete/duplicate) و endpoint ها.
"""
import httpx
import pytest

from app.core.database import SessionLocal
from app.models.courses import Course
from app.models.journey import PayehyarEventInbox, PayehyarRecord
from app.services import payehyar_events, payehyar_records
from app.services.payehyar_client import PayehyarClient, PayehyarError

OPENAPI = {"openapi": "3.1.0",
           "info": {"title": "PayehYar360 — Shared Core & Master Data", "version": "1.0.12"}}

PROF_ITEMS = [
    {"code": "PRF-1", "full_name": "دکتر تست‌الف", "degree": "استاد تمام"},
    {"code": "PRF-2", "full_name": "دکتر تست‌ب", "degree": "دانشیار"},
]

UNIQUE_ITEM = {"set": "unique_courses", "code": "PYR101", "title": "درس تست مرجع",
               "attrs": {"section": "اصلی", "unit_theory": 3, "unit_practice": 1,
                         "source": "darsyar360"},
               "status": "active", "updated_at": "2026-11-24T10:00:00"}


def _mk_handler(*, bearer_ok: bool = False, seen: list | None = None,
                fail_professors_services: bool = False):
    """سرور mock با ثبت همه درخواست‌ها در seen برای ادعاهای هدری."""
    state = {"token_requests": 0, "services_502": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        path = request.url.path
        if path == "/openapi.json":
            return httpx.Response(200, json=OPENAPI)
        if path == "/oauth/token":
            state["token_requests"] += 1
            return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
        if path in ("/api/v1/health", "/api/v1/ready"):
            return httpx.Response(404, json={"code": "NOT_FOUND", "message": "یافت نشد."})
        auth = request.headers.get("authorization")
        has_cred = ("x-api-key" in request.headers
                    or (bearer_ok and auth == "Bearer tok-1")
                    or "x-dev-user" in request.headers)
        if path.startswith("/api/v1/services/masterdata/"):
            if not has_cred:
                return httpx.Response(401, json={
                    "code": "UNAUTHENTICATED", "message": "کلید API ارسال نشده است؛ "
                    "هدر X-API-Key را تنظیم کنید.", "correlation_id": "c-1"})
            domain = path.rsplit("/", 1)[-1]
            if domain == "professors":
                if fail_professors_services:
                    return httpx.Response(404, json={
                        "code": "NOT_FOUND", "message": "یافت نشد.", "correlation_id": "c-2"})
                if request.headers.get("if-none-match") == 'W/"prof-v1"':
                    return httpx.Response(304, headers={"ETag": 'W/"prof-v1"'})
                return httpx.Response(200, json={
                    "ok": True, "domain": domain, "count": len(PROF_ITEMS),
                    "items": PROF_ITEMS}, headers={"ETag": 'W/"prof-v1"'})
            if domain == "unique-courses":
                if state["services_502"] < 1:
                    state["services_502"] += 1
                    return httpx.Response(502, json={"code": "BAD_GATEWAY",
                                                     "message": "bad gw"})
                return httpx.Response(200, json={"ok": True, "domain": domain, "count": 1,
                                                 "items": [UNIQUE_ITEM]})
            return httpx.Response(200, json={"ok": True, "domain": domain, "count": 0,
                                             "items": []})
        if path == "/api/v1/masterdata/instructors":
            if request.headers.get("x-dev-user") != "dev-prof":
                return httpx.Response(403, json={
                    "code": "INSUFFICIENT_ROLE", "message": "نقش لازم را ندارید.",
                    "correlation_id": "c-3",
                    "details": {"required_roles": ["steward"]}})
            return httpx.Response(200, json=PROF_ITEMS)
        if path == "/api/v1/sync/changes":
            return httpx.Response(200, json={"changes": [], "cursor_next": 7,
                                             "has_more": False})
        if path == "/api/v1/sync/checkpoints":
            return httpx.Response(201, json={"ok": True})
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "یافت نشد."})

    return handler, state


def _client(seen=None, **kw) -> tuple[PayehyarClient, dict]:
    handler, state = _mk_handler(seen=seen, **{k: v for k, v in kw.items()
                                               if k in ("bearer_ok",
                                                        "fail_professors_services")})
    client_kw = {k: v for k, v in kw.items()
                 if k in ("api_key", "dev_user", "client_secret", "token_endpoint",
                          "retry_max_attempts", "etag_cache")}
    c = PayehyarClient(base_url="http://mock", timeout=2,
                       transport=httpx.MockTransport(handler),
                       retry_backoff=kw.get("retry_backoff", 0), **client_kw)
    return c, state


# ---------- قرارداد هدرها (سند فنی) ----------

def test_correlation_id_unique_and_idempotency_on_post():
    seen: list = []
    c, _ = _client(api_key="good-key", seen=seen)
    c.send_checkpoint("1")
    c.send_checkpoint("2")
    posts = [r for r in seen if r.url.path == "/api/v1/sync/checkpoints"]
    assert len(posts) == 2
    assert len({r.headers["x-correlation-id"] for r in posts}) == 2  # UUID یکتا
    assert len({r.headers["idempotency-key"] for r in posts}) == 2   # کلید idempotent
    c.fetch_changes()
    gets = [r for r in seen if r.url.path == "/api/v1/sync/changes"]
    assert gets and "idempotency-key" not in gets[-1].headers


def test_oauth2_client_credentials_and_token_cache():
    seen: list = []
    c, state = _client(client_secret="sec-1", token_endpoint="/oauth/token",
                       bearer_ok=True, seen=seen)
    assert c.auth_mode == "OAUTH2"
    c.fetch_catalog()
    c.fetch_catalog()
    token_calls = [r for r in seen if r.url.path == "/oauth/token"]
    assert len(token_calls) == 1  # توکن کش شد — واکشی دوم توکن جدید نگرفت
    data_reqs = [r for r in seen if r.url.path.endswith("unique-courses")]
    assert data_reqs and data_reqs[0].headers["authorization"] == "Bearer tok-1"


def test_retry_on_502_then_success():
    c, _ = _client(api_key="good-key", retry_max_attempts=5)
    body = c.fetch_domain("unique-courses")
    assert body.get("ok") is True  # تلاش اول 502، تلاش دوم موفق


def test_retry_exhausted_raises_last_status():
    calls = {"n": 0}

    def always_503(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"code": "UNAVAILABLE", "message": "x"})

    c = PayehyarClient(base_url="http://mock", timeout=2,
                       transport=httpx.MockTransport(always_503),
                       retry_max_attempts=3, retry_backoff=0, api_key="k")
    with pytest.raises(PayehyarError) as exc:
        c.fetch_domain("unique-courses")
    assert exc.value.http_status == 503
    assert calls["n"] == 3  # هر ۳ تلاش انجام شد


def test_etag_cache_304_not_modified():
    seen: list = []
    c, _ = _client(api_key="good-key", etag_cache=True, seen=seen)
    first = c.fetch_extended_domain("professors")
    assert first["items"] and first["source"] == "services"
    second = c.fetch_extended_domain("professors")
    assert second.get("not_modified") is True and second["items"] == []
    prof_reqs = [r for r in seen if r.url.path.endswith("services/masterdata/professors")]
    assert "if-none-match" in prof_reqs[-1].headers  # کش ETag استفاده شد


def test_probe_reports_health_and_ready():
    c, _ = _client(api_key="good-key")
    info = c.probe()
    assert info["status"] == "OK"
    assert info["health"] == {"available": False, "http_status": 404}
    assert info["ready"] == {"available": False, "http_status": 404}


def test_fetch_extended_domain_admin_fallback():
    # بدون کلید API، با کاربر توسعه → مستقیم مسیر مدیریتی
    c, _ = _client(dev_user="dev-prof")
    out = c.fetch_extended_domain("professors")
    assert out["source"] == "admin" and len(out["items"]) == 2
    # با کلید API اما دامنه services موجود نیست → fallback مدیریتی
    c2, _ = _client(api_key="good-key", dev_user="dev-prof",
                    fail_professors_services=True)
    out2 = c2.fetch_extended_domain("professors")
    assert out2["source"] == "admin"
    assert any("services/professors" in w for w in out2["warnings"])


# ---------- مخزن عمومی رکوردها ----------

def test_upsert_domain_records_idempotent_and_unique(client):
    db = SessionLocal()
    try:
        items = [{"code": "CR-1", "title": "کلاس ۱۰۱"},
                 {"code": "CR-1", "title": "کلاس ۱۰۱"}]
        r1 = payehyar_records.upsert_domain_records(db, "classrooms", items)
        assert r1 == {"created": 1, "updated": 0, "up_to_date": 0, "skipped": 1}
        r2 = payehyar_records.upsert_domain_records(db, "classrooms", items[:1])
        assert r2["up_to_date"] == 1  # بدون تغییر واقعی
        r3 = payehyar_records.upsert_domain_records(
            db, "classrooms", [{"code": "CR-1", "title": "کلاس ۱۰۱ (نوسازی)"}])
        assert r3["updated"] == 1
        rec = db.query(PayehyarRecord).filter_by(domain="classrooms",
                                                 external_id="CR-1").first()
        assert rec is not None and rec.title == "کلاس ۱۰۱ (نوسازی)"
        db.rollback()
    finally:
        db.close()


def test_event_upsert_duplicate_and_delete(client):
    db = SessionLocal()
    try:
        ev = {"event_id": "E-1", "event": "created", "domain": "classrooms",
              "payload": {"code": "CR-9", "name": "کلاس ۹"}}
        assert payehyar_events.handle_event_payload(db, ev) == "PROCESSED"
        assert db.query(PayehyarRecord).filter_by(domain="classrooms",
                                                  external_id="CR-9").first() is not None
        assert payehyar_events.handle_event_payload(db, ev) == "DUPLICATE"
        assert db.get(PayehyarEventInbox, "E-1").status == "PROCESSED"
        # حذف → تورنگاشت
        ev_del = {"event_id": "E-2", "event": "deleted", "domain": "classrooms",
                  "payload": {"code": "CR-9"}}
        payehyar_events.handle_event_payload(db, ev_del)
        assert db.query(PayehyarRecord).filter_by(
            domain="classrooms", external_id="CR-9").first().is_deleted is True
        db.rollback()
    finally:
        db.close()


def test_event_native_course_domain(client, ctx):
    db = SessionLocal()
    try:
        ev = {"event_id": "E-3", "event": "updated", "domain": "unique-courses",
              "payload": dict(UNIQUE_ITEM, code="EVT101", title="درس رویداد مرجع")}
        assert payehyar_events.handle_event_payload(db, ev) == "PROCESSED"
        course = db.query(Course).filter_by(reference_id="py:EVT101").first()
        assert course is not None and course.credits == 4  # ۳ نظری + ۱ عملی
        db.rollback()
    finally:
        db.close()


def test_routing_key_resolution():
    d, op = payehyar_events._resolve_domain_op(
        {}, "payehyar.masterdata.unique-course.updated.v1")
    assert (d, op) == ("unique-courses", "upsert")
    d2, op2 = payehyar_events._resolve_domain_op(
        {}, "payehyar.masterdata.classroom.deleted.v1")
    assert (d2, op2) == ("classrooms", "delete")


# ---------- endpoint ها ----------

def test_sync_extended_endpoint(tech_headers, client, monkeypatch):
    from app.services import payehyar_records as pr

    class StubClient:
        def __init__(self, **kw):
            pass

        def fetch_extended_domain(self, domain, since=None):
            return {"items": [{"code": f"X-{domain}", "name": "نمونه"}],
                    "source": "services", "warnings": []}

    monkeypatch.setattr(pr, "PayehyarClient", StubClient)
    r = client.post("/api/v1/integration/payehyar/sync-extended",
                    headers=tech_headers, json={"domains": ["professors"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["courses_created"] == 1
    assert body["domains"][0]["domain"] == "professors"


def test_records_endpoint_and_rbac(tech_headers, st_headers, client):
    r = client.get("/api/v1/integration/payehyar/records/professors",
                   headers=tech_headers)
    assert r.status_code == 200, r.text
    assert set(r.json().keys()) == {"domain", "total", "items"}
    # دانشجو اجازه ندارد
    r2 = client.get("/api/v1/integration/payehyar/records/professors",
                    headers=st_headers)
    assert r2.status_code == 403


def test_system_status_endpoint(tech_headers, st_headers, client):
    r = client.get("/api/v1/integration/payehyar/system-status", headers=tech_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"scheduler", "events", "records_counts", "extended_domains"} <= set(body.keys())
    assert body["scheduler"]["enabled"] is False  # پیش‌فرض خاموش تا فعال‌سازی صریح
    assert body["events"]["enabled"] is False
    r2 = client.get("/api/v1/integration/payehyar/system-status", headers=st_headers)
    assert r2.status_code == 403
