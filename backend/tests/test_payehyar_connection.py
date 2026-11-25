"""تست تنظیمات و تست اتصال پایه‌یار۳۶۰ (v3.4.2).

پوشش: ذخیره/ماسک کلید در دیتابیس، اولویت منابع (دیتابیس > متغیر محیطی)،
تزریق تنظیمات به کلاینت در مسیرهای همگام‌سازی، تست اتصال گام‌به‌گام با
transport جعلی (موفق/بی‌کلید/کلید نادرست/دسترس‌ناپذیر) و RBAC endpoint ها.
"""
import httpx
import pytest

from app.core.database import SessionLocal
from app.services import payehyar_connection

PROBE_OK = {"openapi": "3.1.0", "info": {"title": "PayehYar360 — Shared Core & Master Data",
                                         "version": "1.0.14"}}
KEY = "pyk_OAY8abcdefghijklmnopqrstuvwxyzXGY"


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/openapi.json":
        return httpx.Response(200, json=PROBE_OK)
    if request.url.path == "/api/v1/services/masterdata/unique-courses":
        if request.headers.get("x-api-key") != "good-key":
            return httpx.Response(401, json={"message": "کلید API نامعتبر است."})
        return httpx.Response(200, json={"items": [{"code": "1001"}], "count": 1})
    return httpx.Response(404, json={"message": "یافت نشد."})


def _mock_open_http(monkeypatch, handler=_handler):
    monkeypatch.setattr(payehyar_connection, "_open_http",
                        lambda transport, timeout: httpx.Client(
                            transport=httpx.MockTransport(handler), timeout=timeout))


def _db():
    return SessionLocal()


def _clear_row():
    db = _db()
    row = payehyar_connection._row(db)
    if row is not None:
        db.delete(row)
        db.commit()
    db.close()


@pytest.fixture(autouse=True)
def _no_stale_row():
    _clear_row()
    yield
    _clear_row()


# ---------- ذخیره و ماسک ----------

def test_save_and_mask_roundtrip(client, prof_headers):
    r = client.put("/api/v1/integration/payehyar/connection", headers=prof_headers,
                   json={"base_url": "http://188.212.96.235:8094", "api_key": KEY})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_key"] is True
    assert body["key_source"] == "DB"
    assert body["api_key_masked"].startswith("pyk_OAY8")
    assert body["api_key_masked"].endswith(KEY[-4:])
    assert KEY not in body["api_key_masked"]

    r2 = client.get("/api/v1/integration/payehyar/connection", headers=prof_headers)
    assert r2.status_code == 200
    assert r2.json()["base_url"] == "http://188.212.96.235:8094"


def test_save_invalid_url_rejected(client, prof_headers):
    r = client.put("/api/v1/integration/payehyar/connection", headers=prof_headers,
                   json={"base_url": "ftp://bad"})
    assert r.status_code == 422
    assert "http" in r.json()["error"]["message"]


def test_clear_key(client, prof_headers):
    client.put("/api/v1/integration/payehyar/connection", headers=prof_headers,
               json={"api_key": KEY})
    r = client.put("/api/v1/integration/payehyar/connection", headers=prof_headers,
                   json={"api_key": ""})
    assert r.json()["has_key"] is False


def test_connection_rbac(client, st_headers):
    assert client.get("/api/v1/integration/payehyar/connection",
                      headers=st_headers).status_code == 403
    assert client.post("/api/v1/integration/payehyar/test-connection",
                       headers=st_headers, json={}).status_code == 403


# ---------- اولویت منابع و تزریق به کلاینت ----------

class _StubSettings:
    payehyar_base_url = "http://from-env:8094"
    payehyar_api_key = "env-key"


def test_precedence_db_over_env(monkeypatch):
    monkeypatch.setattr(payehyar_connection, "get_settings", _StubSettings)
    db = _db()
    payehyar_connection.save_connection(db, base_url="http://from-db:8094",
                                        api_key="db-key")
    eff = payehyar_connection.effective_connection(db)
    assert (eff["base_url"], eff["api_key"]) == ("http://from-db:8094", "db-key")
    assert eff["key_source"] == "DB"
    _clear_row()
    eff2 = payehyar_connection.effective_connection(db)
    assert eff2["key_source"] == "ENV" and eff2["api_key"] == "env-key"
    db.close()


class _SpyClient:
    calls: list = []

    def __init__(self, **kw):
        _SpyClient.calls.append(kw)


def test_client_for_injects_db_overrides(monkeypatch):
    monkeypatch.setattr(payehyar_connection, "PayehyarClient", _SpyClient)
    db = _db()
    payehyar_connection.save_connection(db, base_url="http://from-db:8094",
                                        api_key="db-key")
    payehyar_connection.client_for(db)
    assert _SpyClient.calls[-1]["base_url"] == "http://from-db:8094"
    assert _SpyClient.calls[-1]["api_key"] == "db-key"
    _clear_row()
    payehyar_connection.client_for(db)
    # بدون ردیف دیتابیس → بدون kwarg یعنی fallback خود کلاینت به متغیر محیطی
    assert "base_url" not in _SpyClient.calls[-1]
    assert "api_key" not in _SpyClient.calls[-1]
    db.close()


def test_catalog_uses_connection_settings(client, prof_headers, monkeypatch):
    """همگام‌سازی باید از تنظیمات ذخیره‌شده کلید بگیرد — نه فقط از env."""
    from app.services import payehyar_connection as pc
    saved = client.put("/api/v1/integration/payehyar/connection",
                       headers=prof_headers,
                       json={"base_url": "http://mock", "api_key": "good-key"}).json()
    assert saved["has_key"] is True
    seen_kw: list = []

    class _RealProbe:
        def __init__(self, **kw):
            seen_kw.append(kw)
            self.base_url = kw.get("base_url") or "http://mock"
            self.api_key = kw.get("api_key") or ""

        def probe(self):
            return {"service_version": "1.0.14", "status": "OK"}

    monkeypatch.setattr(pc, "PayehyarClient", _RealProbe)
    r = client.get("/api/v1/integration/payehyar/status", headers=prof_headers)
    assert r.status_code == 200, r.text
    assert seen_kw and seen_kw[-1].get("api_key") == "good-key"


# ---------- تست اتصال گام‌به‌گام ----------

def test_test_connection_success(client, prof_headers, monkeypatch):
    _mock_open_http(monkeypatch)
    r = client.post("/api/v1/integration/payehyar/test-connection",
                    headers=prof_headers,
                    json={"base_url": "http://mock", "api_key": "good-key"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert [s["ok"] for s in body["steps"]] == [True, True, True]
    assert "1.0.14" in body["summary"]
    assert body["steps"][1]["detail"].startswith("کلید")


def test_test_connection_unreachable(client, prof_headers, monkeypatch):
    def boom(request):
        raise httpx.ConnectError("connection refused")

    _mock_open_http(monkeypatch, boom)
    r = client.post("/api/v1/integration/payehyar/test-connection",
                    headers=prof_headers, json={"base_url": "http://mock"})
    body = r.json()
    assert body["ok"] is False
    assert body["steps"][0]["ok"] is False
    assert "فایروال" in body["steps"][0]["hint"]
    assert len(body["steps"]) == 1  # گام‌های بعدی بی‌معنا هستند


def test_test_connection_missing_key(client, prof_headers, monkeypatch):
    _mock_open_http(monkeypatch)
    r = client.post("/api/v1/integration/payehyar/test-connection",
                    headers=prof_headers, json={"base_url": "http://mock"})
    body = r.json()
    assert body["ok"] is False
    assert body["steps"][0]["ok"] is True   # دسترسی برقرار
    assert body["steps"][1]["ok"] is False  # کلید نیست
    assert "سامانه‌های مصرف‌کننده" in body["steps"][1]["hint"]


def test_test_connection_bad_key(client, prof_headers, monkeypatch):
    _mock_open_http(monkeypatch)
    r = client.post("/api/v1/integration/payehyar/test-connection",
                    headers=prof_headers,
                    json={"base_url": "http://mock", "api_key": "wrong"})
    body = r.json()
    assert body["ok"] is False
    assert body["steps"][1]["ok"] is False
    assert "پنل پایه‌یار" in body["steps"][1]["hint"]
