"""احراز هویت: ورود محلی، ثبت‌نام با گردش‌کار تایید، و ورود یکگانه SSO/OIDC."""
import secrets

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import forbidden, unauthorized, validation_error
from app.core.ratelimit import rate_limit
from app.core.security import (create_access_token, get_current_user,
                               hash_password, verify_password)
from app.models.courses import Course
from app.models.identity import APPROVAL_STATUSES, CourseRole, User, degree_level_fa
from app.services import sso_client

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["auth"])

# نقش‌های مجاز ثبت‌نام خود خدمت؛ STUDENT فعال می‌شود، استاد/مدیرگروه در انتظار تایید
SELF_REGISTER_ROLES = ("STUDENT", "PROFESSOR", "GROUP_ADMIN")


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    email: str | None = None
    role: str = "STUDENT"


class ExchangeIn(BaseModel):
    ticket: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db), _rl=Depends(rate_limit("login", 20, 60))):
    s = get_settings()
    user = db.query(User).filter(User.username == body.username).first()
    # حاکمیت ورود: در استقرار تولیدی (S360_SSO_REQUIRED=true) ورود محلی بسته است
    # و فقط مدیر فنی برای عملیات می‌تواند وارد شود (بازخورد ۳.۱).
    if s.sso_required and user and user.role != "TECH_ADMIN":
        raise forbidden("ورود محلی در این محیط غیرفعال است؛ از ورود یکگانه پرتال مرکزی استفاده کنید")
    if user is None or not verify_password(body.password, user.password_hash):
        raise unauthorized("نام کاربری یا رمز عبور اشتباه است")
    if user.approval_status == "PENDING":
        raise unauthorized("حساب شما در انتظار تایید مدیر سامانه است")
    if user.approval_status == "REJECTED" or not user.is_active:
        raise unauthorized("حساب شما غیرفعال است؛ با مدیر سامانه تماس بگیرید")
    token = create_access_token(user.id, user.role)
    audit(db, user.id, "LOGIN", "user", user.id)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(db, user)}


class RefreshIn(BaseModel):
    pass  # توکن فعلی از سربرگ Authorization خوانده می‌شود


@router.post("/refresh")
def refresh_token(db: Session = Depends(get_db),
                  _rl=Depends(rate_limit("refresh", 60, 60)),
                  user: User = Depends(get_current_user)):
    """تمدید نشست: توکن جدید با عمر کامل برای کاربرِ توکن معتبر —
    عمر کوتاه توکن + تمدید کنترل‌شده (بازنگری نشست، بازخورد ۳.۱)."""
    token = create_access_token(user.id, user.role)
    audit(db, user.id, "TOKEN_REFRESH", "user", user.id)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(db, user)}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db), _rl=Depends(rate_limit("register", 10, 300))):
    """ثبت‌نام خودخدمت: دانشجو فعال؛ استاد/مدیرگروه در انتظار تایید مدیر سامانه."""
    if body.role not in SELF_REGISTER_ROLES:
        raise validation_error("این نقش برای ثبت‌نام خودخدمت مجاز نیست")
    if db.query(User).filter(User.username == body.username).first() is not None:
        raise validation_error("این نام کاربری از قبل وجود دارد")
    status = "ACTIVE" if body.role == "STUDENT" else "PENDING"
    user = User(
        username=body.username, full_name=body.full_name, email=body.email,
        password_hash=hash_password(body.password), role=body.role,
        is_active=(status == "ACTIVE"), approval_status=status,
    )
    db.add(user)
    db.flush()
    audit(db, user.id, "SELF_REGISTRATION", "user", user.id, after={"role": body.role, "status": status})
    db.commit()
    message = ("ثبت‌نام انجام شد؛ می‌توانید وارد شوید." if status == "ACTIVE"
               else "ثبت‌نام ثبت شد؛ پس از تایید مدیر سامانه می‌توانید وارد شوید.")
    return {"status": status, "role": body.role, "message": message}


@router.get("/me")
def me_alias(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _user_payload(db, user)


@me_router.get("/me")
def me_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _user_payload(db, user)


# ---------- ورود یکگانه (SSO/OIDC) ----------

@router.get("/sso/config")
def sso_config():
    s = get_settings()
    enabled = sso_client.sso_enabled()
    return {
        "enabled": enabled,
        "provider": s.sso_base_url,
        "redirect_uri": s.sso_redirect_uri,
        "message": ("ورود یکگانه فعال است." if enabled else
                    "SSO تنظیم نشده؛ در پرتال مرکزی SSO برای این سامانه Client ID/Secret ثبت و "
                    "متغیرهای S360_SSO_CLIENT_ID و S360_SSO_CLIENT_SECRET را تنظیم کنید."),
    }


@router.get("/sso/login")
def sso_login():
    """شروع جریان OIDC: ریدایرکت به پرتال ورود یکپارچه با PKCE."""
    s = get_settings()
    if not sso_client.sso_enabled():
        raise validation_error("SSO تنظیم نشده است؛ Client ID/Secret را در تنظیمات وارد کنید")
    discovery = sso_client.get_discovery(s.sso_base_url)
    state = secrets.token_urlsafe(16)
    verifier, challenge = sso_client.pkce_pair()
    nonce = secrets.token_urlsafe(12)
    sso_client.store_state(state, verifier, nonce)
    url = sso_client.build_authorize_url(
        discovery, s.sso_client_id, s.sso_redirect_uri, s.sso_scope, state, challenge,
        nonce=nonce)
    return RedirectResponse(url, status_code=302)


@router.get("/sso/callback")
def sso_callback(code: str | None = None, state: str | None = None,
                 error: str | None = None, db: Session = Depends(get_db)):
    """پایان جریان OIDC: تبادل توکن، اعتبارسنجی id_token و provision کاربر."""
    s = get_settings()
    front = s.sso_frontend_base.rstrip("/")

    def _redir(qs: str) -> RedirectResponse:
        return RedirectResponse(f"{front}/sso/callback?{qs}", status_code=302)

    if error:
        return _redir(f"error={error}")
    popped = sso_client.pop_state_full(state) if state else None
    if popped is None or not code:
        return _redir("error=state")
    verifier, nonce = popped
    try:
        discovery = sso_client.get_discovery(s.sso_base_url)
        tokens = sso_client.exchange_code(
            discovery, s.sso_client_id, s.sso_client_secret, s.sso_redirect_uri, code, verifier)
        id_token = tokens.get("id_token", "")
        claims = sso_client.verify_id_token(
            id_token, discovery["jwks_uri"], discovery["issuer"], s.sso_client_id,
            expected_nonce=nonce)
        info = sso_client.fetch_userinfo(discovery, tokens.get("access_token", ""))
    except Exception:
        return _redir("error=exchange")

    sub = str(claims.get("sub") or info.get("sub") or "")
    if not sub:
        return _redir("error=no_sub")
    username = (info.get("preferred_username") or claims.get("preferred_username")
                or f"sso_{sub[:10]}")
    user = db.query(User).filter(
        (User.sso_subject == sub) | (User.username == username)).first()
    if user is None:
        user = User(
            username=username,
            full_name=info.get("name") or claims.get("name") or username,
            email=info.get("email") or claims.get("email"),
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role="STUDENT", is_active=True, approval_status="ACTIVE", sso_subject=sub,
        )
        db.add(user)
        db.flush()
    elif user.sso_subject is None:
        user.sso_subject = sub
    if user.approval_status == "PENDING" or not user.is_active:
        db.commit()
        return _redir("error=pending")
    ticket = sso_client.issue_ticket(user.id)
    audit(db, user.id, "LOGIN_SSO", "user", user.id, after={"sub": sub})
    db.commit()
    return _redir(f"ticket={ticket}")


@router.post("/sso/exchange")
def sso_exchange(body: ExchangeIn, db: Session = Depends(get_db),
                 _rl=Depends(rate_limit("sso_exchange", 30, 60))):
    """تبادل بلیت یک‌بارمصرف با توکن سامانه (بدون قرارگرفتن توکن در URL)."""
    user_id = sso_client.pop_ticket(body.ticket)
    if user_id is None:
        raise unauthorized("بلیت نامعتبر یا منقضی است؛ دوباره وارد شوید")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized("حساب معتبر نیست")
    token = create_access_token(user.id, user.role)
    return {"access_token": token, "token_type": "bearer", "user": _user_payload(db, user)}


def _user_payload(db: Session, user: User) -> dict:
    roles = []
    for cr in db.query(CourseRole).filter(CourseRole.user_id == user.id).all():
        course = db.get(Course, cr.course_id)
        if course:
            roles.append({
                "course_id": str(course.id), "course_title": course.title,
                "course_code": course.code, "role": cr.role,
            })
    return {
        "id": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
        "degree_level": user.degree_level,
        "degree_level_fa": degree_level_fa(user.degree_level),
        "approval_status": user.approval_status,
        "sso_linked": bool(user.sso_subject),
        "course_roles": roles,
    }
