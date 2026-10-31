# -*- coding: utf-8 -*-
"""
=====================================================================
Security — احراز هویت و کنترل دسترسی (بدون وابستگی جدید)
=====================================================================
- هش رمز عبور: PBKDF2-HMAC-SHA256 (کتابخانهٔ استاندارد)
- توکن نشست: امضای HMAC-SHA256 با کلید پایدار روی دیسک
  (توکن‌ها بعد از ری‌استارت برنامه هم معتبر می‌مانند)
- وابستگی‌های FastAPI:
    get_current_user  → کاربر فعال از هدر Authorization
    require_roles(...) → محدودسازی نقش‌ها
=====================================================================
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

# ------------------------------------------------------------------
# ثابت‌ها
# ------------------------------------------------------------------
PBKDF2_ITERATIONS = 200_000
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # یک هفته

ROLES = ("admin", "group_manager", "professor", "student")
ROLE_LABELS = {
    "admin": "مدیر سامانه",
    "group_manager": "مدیرگروه",
    "professor": "استاد",
    "student": "دانشجو",
}
STATUS_LABELS = {
    "pending": "در انتظار تایید",
    "active": "فعال",
    "rejected": "رد شده",
    "disabled": "غیرفعال",
}


# ==================================================================
# رمز عبور
# ==================================================================
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        salt.hex(),
        digest.hex(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:  # noqa: BLE001
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """اگر رمز ضعیف باشد پیام فارسی برمی‌گرداند؛ در غیر این صورت None."""
    if len(password or "") < 6:
        return "رمز عبور باید حداقل ۶ نویسه باشد."
    return None


# ==================================================================
# کلید امضای توکن (پایدار روی دیسک)
# ==================================================================
def _secret_file_path() -> str:
    # در حالت پرتابل کنار exe (پوشهٔ data) و در حالت توسعه کنار بک‌اند
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        data_dir = os.path.join(base, "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "secret.key")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "secret.key")


def get_secret_key() -> bytes:
    path = _secret_file_path()
    try:
        with open(path, "rb") as f:
            key = f.read().strip()
        if len(key) >= 32:
            return key
    except OSError:
        pass
    key = secrets.token_hex(32).encode("utf-8")
    try:
        with open(path, "wb") as f:
            f.write(key)
    except OSError:
        # اگر نوشتن ممکن نبود، کلید موقتی می‌سازیم (فقط این نشست)
        return secrets.token_bytes(48)
    return key


# ==================================================================
# توکن نشست
# ==================================================================
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _from_b64url(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_token(user: User) -> str:
    payload = {
        "uid": user.id,
        "role": user.role,
        "username": user.username,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(get_secret_key(), body.encode("ascii"), hashlib.sha256)
    return f"{body}.{_b64url(signature.digest())}"


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(
            get_secret_key(), body.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _from_b64url(sig)):
            return None
        payload = json.loads(_from_b64url(body))
        if int(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:  # noqa: BLE001
        return None


# ==================================================================
# وابستگی‌های FastAPI
# ==================================================================
def _extract_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(request)
    payload = decode_token(token) if token else None
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="نشست شما معتبر نیست؛ لطفاً وارد سامانه شوید.",
        )
    user = db.query(User).filter(User.id == payload.get("uid")).first()
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=401,
            detail="حساب کاربری شما فعال نیست.",
        )
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """مانند get_current_user اما بدون خطا — برای مسیرهای اختیاری."""
    token = _extract_token(request)
    payload = decode_token(token) if token else None
    if not payload:
        return None
    user = db.query(User).filter(User.id == payload.get("uid")).first()
    if user is None or user.status != "active":
        return None
    return user


def require_roles(*roles: str):
    """سازندهٔ وابستگی محدودش نقش — require_roles("admin", "group_manager")."""
    allowed: List[str] = list(roles)

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail="شما به این بخش دسترسی ندارید.",
            )
        return current_user

    return _checker


def public_user_info(user: User) -> Dict[str, Any]:
    """خروجی امن اطلاعات کاربر (بدون هش رمز)."""
    return {
        "id": user.id,
        "full_name": user.full_name,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "status": user.status,
        "status_label": STATUS_LABELS.get(user.status, user.status),
        "created_at": user.created_at.isoformat(timespec="seconds")
        if user.created_at
        else None,
    }
