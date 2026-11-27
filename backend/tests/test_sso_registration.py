"""تست ثبت رسمی سامانه در پرتال ورود یکپارچه (v3.14.0).

مطابق فرم «افزودن / ویرایش سامانه» پرتال SSO:
  کلید tahsilyar / نام تحصیل‌یار۳۶۰ / Client ID tahsilyar360 /
  آدرس ورود http://192.168.100.4:8093/ / آیکون ⏰ / ترتیب 5 / فعال
به‌علاوه: کلاینت بدون Secret فقط-PKCE است و client_secret خالی ارسال نمی‌شود.
"""
import httpx

from app.core.config import get_settings
from app.services import sso_client


def test_sso_registration_defaults(client):
    cfg = client.get("/api/v1/auth/sso/config").json()
    assert cfg["enabled"] is True
    app = cfg["app"]
    assert app["key"] == "tahsilyar"
    assert app["name"] == "تحصیل‌یار۳۶۰"
    assert app["description"] == "مشاوه تحصیلی، انتخاب رشت"
    assert app["icon"] == "⏰"
    assert app["order"] == 5
    assert app["client_id"] == "tahsilyar360"
    assert cfg["entry_url"] == "http://192.168.100.4:8093"
    assert cfg["redirect_uri"] == "http://192.168.100.4:8093/api/v1/auth/sso/callback"
    assert "تحصیل‌یار۳۶۰" in cfg["message"]


def test_exchange_code_public_client_omits_empty_secret(monkeypatch):
    """بدون Secret: کلید client_secret در بدنهٔ توکن نباید باشد."""
    captured: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"access_token": "at", "id_token": "fake.jwt.token"}

    class _Client:
        def __init__(self, **kw):
            pass

        def post(self, url, data=None):
            captured["data"] = data
            return _Resp()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(sso_client.httpx, "Client", _Client)
    discovery = {"token_endpoint": "http://sso.test/token"}

    sso_client.exchange_code(discovery, "tahsilyar360", "", "http://x/cb", "code-1", "ver-1")
    assert "client_secret" not in captured["data"]
    assert captured["data"]["client_id"] == "tahsilyar360"
    assert captured["data"]["code_verifier"] == "ver-1"

    sso_client.exchange_code(discovery, "tahsilyar360", "sec-x", "http://x/cb", "code-2", "ver-2")
    assert captured["data"]["client_secret"] == "sec-x"


def test_settings_expose_official_address():
    s = get_settings()
    assert s.sso_frontend_base == "http://192.168.100.4:8093"
    assert s.sso_redirect_uri.startswith("http://192.168.100.4:8093/")
