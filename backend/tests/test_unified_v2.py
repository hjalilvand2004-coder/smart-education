"""تست‌های یکپارچه v2: ثبت‌نام/تایید، SSO/OIDC، گزارش چهارفرمتی و سرویس‌دهی خارجی."""
import re
import uuid
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import get_settings
from app.services import sso_client


# ---------- ثبت‌نام و گردش‌کار تایید ----------

def test_register_student_auto_active(client):
    uname = f"st_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/auth/register", json={
        "username": uname, "password": "Pass1234!", "full_name": "دانشجوی جدید",
        "role": "STUDENT"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "ACTIVE"
    login = client.post("/api/v1/auth/login", json={"username": uname, "password": "Pass1234!"})
    assert login.status_code == 200
    assert login.json()["user"]["approval_status"] == "ACTIVE"


def test_register_professor_pending_then_approve(client, admin_headers):
    uname = f"pr_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/auth/register", json={
        "username": uname, "password": "Pass1234!", "full_name": "استاد جدید",
        "role": "PROFESSOR"})
    assert r.status_code == 201
    assert r.json()["status"] == "PENDING"
    # ورود قبل از تایید ممنوع است
    early = client.post("/api/v1/auth/login", json={"username": uname, "password": "Pass1234!"})
    assert early.status_code == 401
    assert "تایید" in early.json()["error"]["message"]

    cnt = client.get("/api/v1/users/pending-count", headers=admin_headers).json()
    assert cnt["pending"] >= 1
    users = client.get("/api/v1/users", headers=admin_headers,
                       params={"approval": "PENDING", "search": uname}).json()
    assert users["total"] == 1
    target = users["items"][0]["id"]
    ok = client.post(f"/api/v1/users/{target}/approve", headers=admin_headers)
    assert ok.status_code == 200
    login = client.post("/api/v1/auth/login", json={"username": uname, "password": "Pass1234!"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "PROFESSOR"


def test_register_rejects_admin_role_and_duplicate(client):
    r = client.post("/api/v1/auth/register", json={
        "username": "x_admin_try", "password": "Pass1234!", "full_name": "تلاش مدیر",
        "role": "EDUCATION_ADMIN"})
    assert r.status_code in (400, 422)
    body = {"username": "dup_uniq_1", "password": "Pass1234!", "full_name": "اولی", "role": "STUDENT"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code in (400, 422)


def test_users_management_forbidden_for_students(client, st_headers):
    assert client.get("/api/v1/users", headers=st_headers).status_code == 403


def test_role_change_and_reset(client, admin_headers):
    uname = f"rc_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/auth/register", json={
        "username": uname, "password": "Pass1234!", "full_name": "کاربر نقش", "role": "STUDENT"})
    uid = client.get("/api/v1/users", headers=admin_headers, params={"search": uname}).json()["items"][0]["id"]
    r = client.put(f"/api/v1/users/{uid}/role", headers=admin_headers, json={"role": "ASSISTANT"})
    assert r.status_code == 200 and r.json()["role"] == "ASSISTANT"
    r2 = client.post(f"/api/v1/users/{uid}/reset-password", headers=admin_headers,
                     json={"new_password": "NewPass123!"})
    assert r2.status_code == 200
    login = client.post("/api/v1/auth/login", json={"username": uname, "password": "NewPass123!"})
    assert login.status_code == 200


# ---------- SSO / OIDC ----------

DISCOVERY = {
    "issuer": "http://sso.test",
    "authorization_endpoint": "http://sso.test/protocol/openid-connect/auth",
    "token_endpoint": "http://sso.test/protocol/openid-connect/token",
    "userinfo_endpoint": "http://sso.test/protocol/openid-connect/userinfo",
    "jwks_uri": "http://sso.test/protocol/openid-connect/certs",
}


@pytest.fixture()
def sso_on(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "sso_client_id", "learning360-client")
    monkeypatch.setattr(settings, "sso_client_secret", "secret-x")
    monkeypatch.setattr(settings, "sso_redirect_uri", "http://app.test/api/v1/auth/sso/callback")
    monkeypatch.setattr(sso_client, "get_discovery", lambda base: DISCOVERY)
    monkeypatch.setattr(sso_client, "exchange_code",
                        lambda *a, **k: {"access_token": "at", "id_token": "fake.jwt.token"})
    monkeypatch.setattr(sso_client, "verify_id_token",
                        lambda *a, **k: {"sub": "sub-42", "preferred_username": "sso.ali",
                                         "name": "علی از طریق SSO"})
    monkeypatch.setattr(sso_client, "fetch_userinfo", lambda *a, **k: {
        "sub": "sub-42", "preferred_username": "sso.ali", "name": "علی از طریق SSO",
        "email": "ali@uni.ir"})


def test_sso_config_disabled_by_default(client):
    cfg = client.get("/api/v1/auth/sso/config").json()
    assert isinstance(cfg["enabled"], bool) and "message" in cfg


def test_sso_full_flow_provisions_user(client, sso_on):
    cfg = client.get("/api/v1/auth/sso/config").json()
    assert cfg["enabled"] is True
    # شروع جریان
    start = client.get("/api/v1/auth/sso/login", follow_redirects=False)
    assert start.status_code == 302
    url = start.headers["location"]
    assert "learning360-client" in url and "code_challenge" in url
    state = parse_qs(urlparse(url).query)["state"][0]
    # callback
    cb = client.get(f"/api/v1/auth/sso/callback?code=abc&state={state}", follow_redirects=False)
    assert cb.status_code == 302
    loc = cb.headers["location"]
    assert "/sso/callback?ticket=" in loc
    ticket = loc.split("ticket=")[1]
    # تبادل بلیت
    ex = client.post("/api/v1/auth/sso/exchange", json={"ticket": ticket})
    assert ex.status_code == 200, ex.text
    user = ex.json()["user"]
    assert user["username"] == "sso.ali" and user["role"] == "STUDENT"
    assert user["sso_linked"] is True
    # ورود دوم همان هویت: provision تکراری انجام نمی‌شود
    start2 = client.get("/api/v1/auth/sso/login", follow_redirects=False)
    state2 = parse_qs(urlparse(start2.headers["location"]).query)["state"][0]
    cb2 = client.get(f"/api/v1/auth/sso/callback?code=abc&state={state2}", follow_redirects=False)
    ticket2 = cb2.headers["location"].split("ticket=")[1]
    ex2 = client.post("/api/v1/auth/sso/exchange", json={"ticket": ticket2}).json()
    assert ex2["user"]["id"] == user["id"]
    # بلیت یک‌بارمصرف است
    assert client.post("/api/v1/auth/sso/exchange", json={"ticket": ticket}).status_code == 401


def test_sso_bad_state_rejected(client, sso_on):
    cb = client.get("/api/v1/auth/sso/callback?code=abc&state=wrong",
                    follow_redirects=False)
    assert cb.status_code == 302 and "error=state" in cb.headers["location"]


# ---------- گزارش جامع ----------

def test_report_summary_and_four_formats(client, prof_headers, st_headers):
    r = client.get("/api/v1/reports/summary", headers=prof_headers)
    assert r.status_code == 200, r.text
    s = r.json()
    assert set(s) >= {"users", "courses", "content", "ai", "syllabus"}
    assert client.get("/api/v1/reports/summary", headers=st_headers).status_code == 403
    expect = {
        "pdf": (b"%PDF", "application/pdf"),
        "docx": (b"PK", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "pptx": (b"PK", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        "html": (b"<!DOCTYPE", "text/html"),
    }
    for fmt, (magic, media) in expect.items():
        resp = client.get(f"/api/v1/reports/export/{fmt}", headers=prof_headers)
        assert resp.status_code == 200 and resp.headers["content-type"].startswith(media), fmt
        assert resp.content[:len(magic)].startswith(magic) and len(resp.content) > 1000, fmt


def test_report_bad_format(client, prof_headers):
    assert client.get("/api/v1/reports/export/csv", headers=prof_headers).status_code in (400, 422)


# ---------- سرویس‌دهی به سایر سامانه‌ها ----------

def test_services_open_without_token(client, ctx):
    h = client.get("/api/v1/services/health").json()
    assert h["status"] == "ok" and h["courses"] >= 1
    topics = client.get("/api/v1/services/topics", params={"course_code": "TST101"}).json()
    assert topics["total"] >= 2
    t0 = topics["items"][0]
    detail = client.get(f"/api/v1/services/topics/{t0['topic_id']}").json()
    assert detail["course_code"] == "TST101" and isinstance(detail["objectives"], list)
    bundle = client.get("/api/v1/services/export/topics").json()
    assert bundle["courses"] and bundle["topics"] and bundle["objectives"]


def test_services_token_enforced(client, ctx, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "service_token", "svc-secret-1")
    assert client.get("/api/v1/services/courses").status_code == 403
    ok = client.get("/api/v1/services/courses", headers={"X-Service-Token": "svc-secret-1"})
    assert ok.status_code == 200 and ok.json()["total"] >= 1


def test_ai_stats_summary(client, prof_headers, st_headers):
    r = client.get("/api/v1/ai-stats/summary", headers=prof_headers)
    assert r.status_code == 200
    data = r.json()
    assert "jobs_by_kind" in data and "questions" in data
    assert client.get("/api/v1/ai-stats/summary", headers=st_headers).status_code == 403
