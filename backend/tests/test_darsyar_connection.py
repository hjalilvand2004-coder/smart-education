"""تست‌های درس‌یار۳۶۰ (darsyar360.ir) — تنظیمات اتصال، تست گام‌به‌گام،
همگام‌سازی گروهی مطلوبیات و جدول رونوشت‌ها (v3.9.0).

الگوی test_payehyar_connection.py: transport جعلی httpx.MockTransport، بدون شبکهٔ
واقعی؛ اولویت منابع تنظیمات (دیتابیس > متغیر محیطی > پیش‌فرض) و RBAC."""
import httpx
import pytest

from app.core.database import SessionLocal
from app.services import darsyar_connection, darsyar_service

BASE = "https://darsyar360.ir"
KEY = "dyk_testkey_1234567890abcdef"

EXT_ID = "PRF-DAR-1"


def _db():
    return SessionLocal()


def _clear_row():
    db = _db()
    row = darsyar_connection._row(db)
    if row is not None:
        db.delete(row)
        db.commit()
    db.close()


def _clear_professor_and_prefs():
    from app.models.journey import DarsyarPreference, PayehyarRecord
    db = _db()
    db.query(DarsyarPreference).filter(
        DarsyarPreference.professor_ext_id == EXT_ID).delete()
    db.query(PayehyarRecord).filter(
        PayehyarRecord.domain == "professors",
        PayehyarRecord.external_id == EXT_ID).delete()
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def _clean_state():
    _clear_row()
    _clear_professor_and_prefs()
    yield
    _clear_row()
    _clear_professor_and_prefs()


def _seed_professor(name: str = "دکتر درس‌یار تست") -> None:
    from app.models.journey import PayehyarRecord
    db = _db()
    db.add(PayehyarRecord(domain="professors", external_id=EXT_ID, title=name,
                          payload={"full_name": name, "department": "گروه تست"}))
    db.commit()
    db.close()


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/":
        return httpx.Response(200, html="<html>درس‌یار۳۶۰</html>")
    if request.url.path.startswith("/api/v1/services/instructor-preferences/"):
        if request.headers.get("x-api-key") != "good-key":
            return httpx.Response(401, json={"message": "کلید نامعتبر است."})
        return httpx.Response(200, json={"item": {"subjects": [
            {"title": "موضوع مطلوب", "weekly_hours": 4}], "time_slots": [], "constraints": []}})
    return httpx.Response(404, json={"message": "یافت نشد."})


def _mock_open_http(monkeypatch, handler=_handler):
    monkeypatch.setattr(darsyar_connection, "_open_http",
                        lambda transport, timeout: httpx.Client(
                            transport=httpx.MockTransport(handler), timeout=timeout))


# ---------- تنظیمات اتصال: ذخیره/ماسک/RBAC ----------

def test_connection_view_default(client, prof_headers):
    r = client.get("/api/v1/integration/darsyar/connection", headers=prof_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["base_url"] == BASE  # پیش‌فرض کد
    assert body["has_key"] is False
    assert body["key_source"] in ("ENV", "NONE")
    assert body["data_owner"].startswith("درس‌یار۳۶۰")


def test_save_and_mask_roundtrip(client, prof_headers):
    r = client.put("/api/v1/integration/darsyar/connection", headers=prof_headers,
                   json={"base_url": BASE, "api_key": KEY, "timeout_seconds": 15})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["base_url_source"] == "DB"
    assert body["key_source"] == "DB"
    assert body["timeout_source"] == "DB" and body["timeout_seconds"] == 15
    assert KEY not in (body["api_key_masked"] or "")
    # دیتابیس بر متغیر محیطی/پیش‌فرض اولویت دارد
    from app.core.config import get_settings
    assert darsyar_connection.effective_connection(_db())["api_key"] == KEY
    assert get_settings() is not None  # smoke


def test_save_invalid_url_rejected(client, prof_headers):
    r = client.put("/api/v1/integration/darsyar/connection", headers=prof_headers,
                   json={"base_url": "darsyar360.ir"})
    assert r.status_code == 422
    r2 = client.put("/api/v1/integration/darsyar/connection", headers=prof_headers,
                    json={"timeout_seconds": 999})
    assert r2.status_code == 422


def test_connection_requires_staff(client, st_headers):
    assert client.get("/api/v1/integration/darsyar/connection",
                      headers=st_headers).status_code == 403
    assert client.put("/api/v1/integration/darsyar/connection",
                      headers=st_headers, json={}).status_code == 403
    assert client.post("/api/v1/integration/darsyar/sync",
                       headers=st_headers, json={}).status_code == 403


# ---------- تست اتصال گام‌به‌گام ----------

def test_test_connection_ok_with_probe_404(client, prof_headers, monkeypatch):
    """سرویس بالا + کلید ذخیره‌شده؛ probe مسیر مطلوبیات ۴۰۴ → قابل‌قبول با هشدار."""
    client.put("/api/v1/integration/darsyar/connection", headers=prof_headers,
               json={"base_url": BASE, "api_key": "good-key"})
    _mock_open_http(monkeypatch)
    r = client.post("/api/v1/integration/darsyar/test-connection",
                    headers=prof_headers, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    names = [s["name"] for s in body["steps"]]
    assert "دسترسی به سرویس" in names


def test_test_connection_bad_key(client, prof_headers, monkeypatch):
    _mock_open_http(monkeypatch)
    r = client.post("/api/v1/integration/darsyar/test-connection", headers=prof_headers,
                    json={"base_url": BASE, "api_key": "wrong-key"})
    body = r.json()
    assert body["ok"] is False
    steps = {s["name"]: s for s in body["steps"]}
    assert steps["دسترسی به سرویس"]["ok"] is True
    assert steps["احراز هویت کلید API"]["ok"] is False
    assert "401" in steps["احراز هویت کلید API"]["detail"]


def test_test_connection_no_key_hint(client, prof_headers, monkeypatch):
    _mock_open_http(monkeypatch)
    r = client.post("/api/v1/integration/darsyar/test-connection", headers=prof_headers,
                    json={"base_url": BASE, "api_key": ""})
    body = r.json()
    assert body["ok"] is False
    assert "کلید" in body["summary"]


def test_test_connection_unreachable(client, prof_headers, monkeypatch):
    def dead_open(transport, timeout):
        def _raise(request):
            raise httpx.ConnectError("connection refused")
        return httpx.Client(transport=httpx.MockTransport(_raise), timeout=timeout)

    monkeypatch.setattr(darsyar_connection, "_open_http", dead_open)
    r = client.post("/api/v1/integration/darsyar/test-connection", headers=prof_headers,
                    json={"base_url": "http://127.0.0.1:1"})
    body = r.json()
    assert body["ok"] is False
    assert body["steps"][0]["ok"] is False


# ---------- همگام‌سازی گروهی مطلوبیات ----------

def test_sync_without_professors_actionable(client, prof_headers):
    r = client.post("/api/v1/integration/darsyar/sync", headers=prof_headers, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert "پایه‌یار" in body["message"]  # راهنمای actionable


def test_sync_all_live_and_overview(client, prof_headers, monkeypatch):
    _seed_professor()
    live = {
        "subjects": [{"title": "مهندسی نرم‌افزار", "course_code": "SW401",
                      "weekly_hours": 6, "level": "تخصصی"}],
        "time_slots": [{"day": "شنبه", "start": "۸:۰۰", "end": "۱۰:۰۰",
                        "preference": "preferred", "preference_label": "مطلوب"}],
        "constraints": ["حداکثر ۲ روز حضوری"],
    }
    monkeypatch.setattr(darsyar_service, "_fetch_live", lambda professor, **kw: dict(live))
    r = client.post("/api/v1/integration/darsyar/sync", headers=prof_headers,
                    json={"refresh": True, "limit": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["live"] == 1 and body["total"] == 1
    item = body["items"][0]
    assert item["ext_id"] == EXT_ID and item["source"] == "live"
    assert item["subjects_count"] == 1 and item["time_slots_count"] == 1
    # جدول رونوشت‌ها
    r2 = client.get("/api/v1/integration/darsyar/preferences", headers=prof_headers)
    assert r2.status_code == 200
    ov = r2.json()
    assert ov["total"] == 1
    row = ov["items"][0]
    assert row["ext_id"] == EXT_ID and row["subjects"][0]["title"] == "مهندسی نرم‌افزار"
    assert row["constraints_count"] == 1


def test_sync_demo_source_when_service_down(client, prof_headers, monkeypatch):
    _seed_professor("دکتر نمونه")
    monkeypatch.setattr(darsyar_service, "_fetch_live", lambda professor, **kw: None)
    r = client.post("/api/v1/integration/darsyar/sync", headers=prof_headers, json={})
    body = r.json()
    assert body["ok"] is True and body["demo"] == 1 and body["live"] == 0
    assert "نمونهٔ قطعی" in body["message"]


def test_sync_partial_failure_is_reported(client, prof_headers, monkeypatch):
    """شکست یک استاد فقط در همان ردیف گزارش می‌شود؛ بقیه ادامه می‌یابند."""
    _seed_professor()

    def boom(professor, **kw):
        raise RuntimeError("network dead")

    monkeypatch.setattr(darsyar_service, "_fetch_live", boom)
    # get_preferences به _fetch_live می‌رسد؛ خطای RuntimeError باید isolated شود
    r = client.post("/api/v1/integration/darsyar/sync", headers=prof_headers, json={})
    body = r.json()
    assert body["ok"] is True
    assert body["items"][0]["source"] in ("error", "demo")
