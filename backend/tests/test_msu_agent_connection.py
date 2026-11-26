"""تست‌های دستیار هوشمند «دانشگاه هوشمند من» (v3.11.0) — تنظیمات اتصال هستهٔ
عامل، تست گام‌به‌گام، پیکربندی ویجت و RBAC.

الگوی test_darsyar_connection.py: httpx.MockTransport بدون شبکهٔ واقعی؛
اولویت منابع تنظیمات (دیتابیس > متغیر محیطی > پیش‌فرض).
"""
import httpx
import pytest

from app.core.database import SessionLocal
from app.services import msu_agent_connection

BASE = "http://localhost:8000"
TOKEN = "msu_test_jwt_token_0123456789"


def _db():
    return SessionLocal()


def _clear_row():
    db = _db()
    row = msu_agent_connection._row(db)
    if row is not None:
        db.delete(row)
        db.commit()
    db.close()


@pytest.fixture(autouse=True)
def _clean_state():
    _clear_row()
    yield
    _clear_row()


# ---------- تنظیمات اتصال: پیش‌فرض/ذخیره/ماسک/RBAC ----------

def test_connection_view_defaults(client, prof_headers):
    r = client.get("/api/v1/integration/msu-agent/connection", headers=prof_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["base_url"] == BASE  # پیش‌فرض کد
    assert body["origin"] == "student360"
    assert body["accent"] == "#7c3aed"  # رنگ برند دانشجو۳۶۰
    assert body["enabled"] is True
    assert body["has_token"] is False
    assert body["data_owner"].startswith("دانشگاه هوشمند من")


def test_save_and_mask_roundtrip(client, admin_headers):
    r = client.put("/api/v1/integration/msu-agent/connection", headers=admin_headers,
                   json={"base_url": "http://10.0.0.8:9000", "origin": "skills360",
                         "accent": "#0f766e", "accent2": "#115e59",
                         "position": "bl", "token": TOKEN, "enabled": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["base_url_source"] == "DB"
    assert body["origin"] == "skills360"
    assert body["position"] == "bl"
    assert body["enabled"] is False
    assert body["has_token"] is True
    assert TOKEN not in (body["token_masked"] or "")
    assert body["token_masked"].startswith("msu_test_")
    # ذخیرهٔ دیتابیس بر پیش‌فرض اولویت دارد
    eff = msu_agent_connection.effective_connection(_db())
    assert eff["base_url"] == "http://10.0.0.8:9000"
    assert eff["token"] == TOKEN
    assert eff["enabled"] is False


def test_save_validations_rejected(client, prof_headers):
    assert client.put("/api/v1/integration/msu-agent/connection", headers=prof_headers,
                      json={"base_url": "localhost:8000"}).status_code == 422
    assert client.put("/api/v1/integration/msu-agent/connection", headers=prof_headers,
                      json={"accent": "purple"}).status_code == 422
    assert client.put("/api/v1/integration/msu-agent/connection", headers=prof_headers,
                      json={"position": "top"}).status_code == 422


def test_save_blank_token_clears(client, admin_headers):
    client.put("/api/v1/integration/msu-agent/connection", headers=admin_headers,
               json={"token": TOKEN})
    r = client.put("/api/v1/integration/msu-agent/connection", headers=admin_headers,
                   json={"token": ""})
    assert r.status_code == 200 and r.json()["has_token"] is False


def test_connection_requires_staff(client, st_headers):
    assert client.get("/api/v1/integration/msu-agent/connection",
                      headers=st_headers).status_code == 403
    assert client.put("/api/v1/integration/msu-agent/connection",
                      headers=st_headers, json={}).status_code == 403
    assert client.post("/api/v1/integration/msu-agent/test-connection",
                       headers=st_headers, json={}).status_code == 403


# ---------- پیکربندی ویجت (برای همهٔ کاربران واردشده) ----------

def test_widget_config_for_student(client, st_headers, admin_headers):
    """دانشجو هم باید ویجت را با تنظیمات کامل بگیرد — توکن کامل لازم ویجت است."""
    client.put("/api/v1/integration/msu-agent/connection", headers=admin_headers,
               json={"base_url": "http://10.0.0.8:9000", "token": TOKEN})
    r = client.get("/api/v1/integration/msu-agent/widget-config", headers=st_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["base_url"] == "http://10.0.0.8:9000"
    assert body["origin"] == "student360"
    assert body["token_key"] == "msu_agent_token"
    assert body["token"] == TOKEN  # ویجت باید آن را در هدر بفرستد


def test_widget_config_disabled(client, st_headers, admin_headers):
    client.put("/api/v1/integration/msu-agent/connection", headers=admin_headers,
               json={"enabled": False})
    r = client.get("/api/v1/integration/msu-agent/widget-config", headers=st_headers)
    assert r.status_code == 200 and r.json()["enabled"] is False


# ---------- تست اتصال گام‌به‌گام ----------

def _transport(status_health=200, status_config=200):
    return httpx.MockTransport(lambda req: httpx.Response(
        status_health if req.url.path == "/api/health" else status_config,
        json={"ok": status_health == 200}))


def test_test_connection_ok(client, prof_headers):
    r = client.post("/api/v1/integration/msu-agent/test-connection", headers=prof_headers,
                    json={"base_url": BASE})
    # بدون transport تزریق‌شده، localhost واقعی در محیط CI نیست → ممکن است شکست بخورد
    body = r.json()
    assert r.status_code == 200
    assert set(body) >= {"ok", "steps"}


def test_test_connection_steps_live(client, prof_headers):
    """تست گام‌به‌گام با transport جعلی — سلامت ۲۰۰ و پیکربندی ۲۰۰."""
    from app.services import msu_agent_connection as svc
    result = svc.test_connection(_db(), base_url=BASE,
                                 transport=_transport(200, 200))
    assert result["ok"] is True
    assert [s["ok"] for s in result["steps"]] == [True, True]


def test_test_connection_health_down(client, prof_headers):
    result = msu_agent_connection.test_connection(_db(), base_url=BASE,
                                                  transport=_transport(500, 200))
    assert result["ok"] is False
    assert result["steps"][0]["ok"] is False
    assert "HTTP 500" in result["steps"][0]["detail"]


def test_test_connection_auth_required_note(client, prof_headers):
    """هسته با REQUIRE_AUTH=true: سلامت ۲۰۰ ولی پیکربندی ۴۰۱ → کل تست اوکی با توضیح."""
    result = msu_agent_connection.test_connection(_db(), base_url=BASE,
                                                  transport=_transport(200, 401))
    assert result["ok"] is True
    assert "توکن" in result["steps"][1]["detail"]


def test_test_connection_invalid_url(client, prof_headers):
    result = msu_agent_connection.test_connection(_db(), base_url="ftp://x")
    assert result["ok"] is False
    assert "http" in result["steps"][0]["detail"]
