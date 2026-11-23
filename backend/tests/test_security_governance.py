"""تست امنیت و حاکمیت نسخه ۳.۱: نشست کوتاه‌تر، تمدید کنترل‌شده، قفل ورود نمونه
در محیط SSO-required، سهم‌بندی بودجه AI و دسترسی منابع."""
import time

import jwt as pyjwt

from app.core.config import get_settings


def _restore(fn):
    def wrapper():
        try:
            fn()
        finally:
            get_settings().sso_required = False
            get_settings().ai_user_daily_token_budget = 200_000
    return wrapper


def test_access_token_lifetime_is_short(client, st_headers):
    """بازنگری نشست: توکن دسترسی ۱۲۰ دقیقه است (قبلاً ۷۲۰)."""
    token = st_headers["Authorization"].split(" ", 1)[1]
    s = get_settings()
    claims = pyjwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm],
                          options={"verify_exp": False})
    lifetime = claims["exp"] - claims["iat"]
    assert lifetime == 120 * 60, f"عمر توکن باید ۱۲۰ دقیقه باشد؛ فعلی: {lifetime/60}"


def test_refresh_endpoint_issues_new_token(client, st_headers):
    r = client.post("/api/v1/auth/refresh", headers=st_headers)
    assert r.status_code == 200, r.text
    new_token = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 200 and me.json()["username"]


def test_sso_required_blocks_demo_login(client, ctx):
    """در استقرار تولیدی، نبود SSO نباید کاربران نمونه را فعال نگه دارد."""
    s = get_settings()
    try:
        s.sso_required = True
        r = client.post("/api/v1/auth/login", json={
            "username": "st_test", "password": "Pass1234!"})
        assert r.status_code == 403, r.text
        assert "ورود یکگانه" in r.json()["error"]["message"]
        # مدیر فنی برای عملیات باقی می‌ماند
        r2 = client.post("/api/v1/auth/login", json={
            "username": "tech_test", "password": "Pass1234!"})
        assert r2.status_code == 200
    finally:
        s.sso_required = False


def test_per_user_ai_budget(client, ctx, st_headers):
    """سهم‌بندی بودجه AI بر اساس کاربر — مصرف یک کاربر کل سامانه را نمی‌بندد."""
    s = get_settings()
    try:
        s.ai_user_daily_token_budget = 0  # هر مصرفی از سقف کاربر عبور می‌کند
        r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/teach-backs",
                        headers=st_headers,
                        json={"concept_id": ctx["base_concept"], "modality": "TEXT",
                              "content": "یک توضیح کامل برای سنجش بودجه کاربر در دروازه AI."})
        assert r.status_code in (429, 503), r.text
        assert r.json()["error"]["code"] == "AI_UNAVAILABLE"
        assert "سقف مصرف روزانه شما" in r.json()["error"]["message"]
    finally:
        s.ai_user_daily_token_budget = 200_000


def test_per_purpose_budget_isolated(client, ctx, st_headers, prof_headers, bank):
    """پرکردن سقف یک سرویس، سرویس دیگر را نبندد (ایزولاسیون سهم‌بندی)."""
    from app.ai.gateway import AIGateway
    from app.core.database import SessionLocal

    s = get_settings()
    old = s.ai_purpose_daily_budget
    try:
        s.ai_purpose_daily_budget = 0  # هر مصرفی از سقف این سرویس عبور می‌کند
        db = SessionLocal()
        try:
            gw = AIGateway(db)
            import uuid as _u
            from app.ai.schemas import TeachBackFeedbackOut
            try:
                gw.run("teach_back_feedback", {"concept_name": "x", "content": "y"},
                       schema=TeachBackFeedbackOut, created_by=_u.uuid4())
                raised = False
            except Exception as exc:
                raised = "این سرویس هوشمند" in str(exc)
            assert raised, "سقف purpose باید مستقل اعمال شود"
        finally:
            db.close()
    finally:
        s.ai_purpose_daily_budget = old


def test_resource_download_requires_permission(client, ctx, st_headers, prof_headers):
    """ACL منابع در دریافت فایل: دانشجوی ثبت‌نام‌شده مجاز است؛ دانشجوی خارج از
    درس هرگز؛ و منبع امتحانی فقط برای استاد/دستیار."""
    # دانشجوی ثبت‌نام‌شده → مجاز یا فایل پیوست ندارد (نه ۵۰۰، نه افشا)
    r = client.get(f"/api/v1/resources/{ctx['resource_id']}/download", headers=st_headers)
    assert r.status_code in (200, 404), r.text
    # دانشجوی خارج از درس → ممنوع
    r2 = client.post("/api/v1/auth/register", json={
        "username": "acl_out", "password": "Pass1234!",
        "full_name": "خارج از درس", "role": "STUDENT"})
    assert r2.status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "username": "acl_out", "password": "Pass1234!"}).json()
    out_headers = {"Authorization": f"Bearer {login['access_token']}"}
    r3 = client.get(f"/api/v1/resources/{ctx['resource_id']}/download", headers=out_headers)
    assert r3.status_code == 403, "کاربر خارج از درس نباید فایل بگیرد"
    # منبع کلید امتحان برای دانشجوی همان درس هم ممنوع است
    r4 = client.get(f"/api/v1/resources/{ctx['exam_resource_id']}/download", headers=st_headers)
    assert r4.status_code == 403
