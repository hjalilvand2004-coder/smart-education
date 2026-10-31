# -*- coding: utf-8 -*-
"""
=====================================================================
Auth Router — ورود، ثبت‌نام و نشست کاربران
=====================================================================
نقش‌های سامانه:
    admin          مدیر سامانه (بوت‌استرپ اولیه)
    group_manager  مدیرگروه  ← ثبت‌نام نیازمند تایید «مدیر سامانه»
    professor      استاد     ← ثبت‌نام نیازمند تایید «مدیر سامانه یا مدیرگروه»
    student        دانشجو    ← فعال‌سازی خودکار

نقاط اتصال:
    POST /api/auth/register         → ثبت‌نام
    POST /api/auth/login            → ورود و دریافت توکن
    GET  /api/auth/me               → اطلاعات کاربر جاری
    POST /api/auth/change-password  → تغییر رمز عبور
=====================================================================
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import (
    ROLE_LABELS,
    create_token,
    get_current_user,
    hash_password,
    public_user_info,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# نقش‌هایی که هنگام ثبت‌نام قابل انتخاب هستند
REGISTERABLE_ROLES = ("group_manager", "professor", "student")


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=255)
    username: str = Field(..., min_length=3, max_length=64)
    email: Optional[str] = Field(None, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(..., description="group_manager | professor | student")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


# ==================================================================
# ثبت‌نام
# ==================================================================
@router.post("/register")
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    role = (payload.role or "").strip().lower()
    if role not in REGISTERABLE_ROLES:
        raise HTTPException(
            status_code=422,
            detail="نقش انتخابی مجاز نیست (مدیرگروه، استاد یا دانشجو).",
        )

    username = payload.username.strip().lower()
    if not username.replace("_", "").replace(".", "").isalnum():
        raise HTTPException(
            status_code=422,
            detail="نام کاربری فقط می‌تواند شامل حروف، عدد، نقطه و زیرخط باشد.",
        )

    weak = validate_password_strength(payload.password)
    if weak:
        raise HTTPException(status_code=422, detail=weak)

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(
            status_code=400,
            detail="این نام کاربری قبلاً ثبت شده است.",
        )

    # سیاست فعال‌سازی: دانشجو خودکار؛ مدیرگروه و استاد نیازمند تایید
    status = "active" if role == "student" else "pending"

    user = User(
        username=username,
        full_name=payload.full_name.strip(),
        email=(payload.email or "").strip() or None,
        hashed_password=hash_password(payload.password),
        role=role,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    message = (
        "ثبت‌نام انجام شد؛ می‌توانید وارد سامانه شوید."
        if status == "active"
        else (
            "ثبت‌نام شما ثبت شد و پس از تایید «مدیر سامانه» فعال خواهد شد."
            if role == "group_manager"
            else "ثبت‌نام شما ثبت شد و پس از تایید «مدیر سامانه» یا «مدیرگروه» فعال خواهد شد."
        )
    )

    return {
        "ok": True,
        "status": status,
        "requires_approval": status == "pending",
        "message": message,
        "user": public_user_info(user),
    }


# ==================================================================
# ورود
# ==================================================================
@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    username = payload.username.strip().lower()
    user = db.query(User).filter(User.username == username).first()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="نام کاربری یا رمز عبور نادرست است.",
        )

    if user.status == "pending":
        approver = (
            "مدیر سامانه"
            if user.role == "group_manager"
            else "مدیر سامانه یا مدیرگروه"
        )
        raise HTTPException(
            status_code=403,
            detail=f"حساب شما هنوز تایید نشده است؛ در انتظار تایید {approver}.",
        )
    if user.status == "rejected":
        raise HTTPException(
            status_code=403,
            detail="درخواست ثبت‌نام شما رد شده است؛ با مدیر سامانه تماس بگیرید.",
        )
    if user.status == "disabled":
        raise HTTPException(
            status_code=403,
            detail="حساب کاربری شما غیرفعال شده است.",
        )

    user.last_login_at = datetime.utcnow()
    db.commit()

    return {
        "ok": True,
        "token": create_token(user),
        "user": public_user_info(user),
    }


# ==================================================================
# کاربر جاری
# ==================================================================
@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return {"ok": True, "user": public_user_info(current_user)}


# ==================================================================
# تغییر رمز عبور
# ==================================================================
@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="رمز عبور فعلی نادرست است.",
        )

    weak = validate_password_strength(payload.new_password)
    if weak:
        raise HTTPException(status_code=422, detail=weak)

    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="رمز جدید نباید با رمز فعلی یکسان باشد.",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()

    return {
        "ok": True,
        "message": "رمز عبور با موفقیت تغییر کرد.",
    }


# ==================================================================
# راهنمای نقش‌ها (برای صفحهٔ ثبت‌نام)
# ==================================================================
@router.get("/roles")
def roles() -> Dict[str, Any]:
    return {
        "roles": [
            {"id": r, "label": ROLE_LABELS[r]} for r in REGISTERABLE_ROLES
        ],
    }
