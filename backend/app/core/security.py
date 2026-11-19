"""احراز هویت: رمز عبور (PBKDF2) و توکن JWT.

توجه: در استقرار نهایی، احراز هویت از طریق OIDC/OAuth2 سامانه هویت دانشگاه انجام
می‌شود (بخش ۲ سند نیازمندی‌ها)؛ این ماژول نقطه اتصال و حالت مستقل توسعه است.
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import unauthorized

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
_PBKDF2_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise unauthorized("توکن منقضی شده است")
    except jwt.InvalidTokenError:
        raise unauthorized("توکن نامعتبر است")


def get_current_user(token: str | None = Depends(_oauth2_scheme), db: Session = Depends(get_db)):
    from app.models.identity import User

    if not token:
        raise unauthorized()
    payload = decode_token(token)
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise unauthorized("کاربر یافت نشد یا غیرفعال است")
    return user


def get_optional_user(token: str | None = Depends(_oauth2_scheme), db: Session = Depends(get_db)):
    """نسخه اختیاری برای مسیرهای عمومی."""
    from app.models.identity import User

    if not token:
        return None
    try:
        payload = decode_token(token)
        return db.get(User, payload["sub"])
    except Exception:
        return None
