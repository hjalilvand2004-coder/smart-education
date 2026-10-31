# -*- coding: utf-8 -*-
"""
=====================================================================
Users Router — مدیریت کاربران و سطوح دسترسی
=====================================================================
دسترسی‌ها:
    مدیر سامانه (admin): همهٔ عملیات روی همهٔ کاربران
    مدیرگروه (group_manager): تایید/رد و مدیریت «استاد» و «دانشجو»
                              (بدون دسترسی به مدیر سامانه و مدیرگروه دیگر)
    استاد / دانشجو: بدون دسترسی به این بخش

نقاط اتصال:
    GET    /api/users                     فهرست کاربران (فیلتر نقش/وضعیت)
    GET    /api/users/pending-count       تعداد در انتظار تایید
    POST   /api/users/{id}/approve        تایید
    POST   /api/users/{id}/reject         رد درخواست
    POST   /api/users/{id}/disable        غیرفعال‌سازی
    POST   /api/users/{id}/enable         فعال‌سازی
    PUT    /api/users/{id}/role           تغییر نقش (فقط مدیر سامانه)
    POST   /api/users/{id}/reset-password بازنشانی رمز
    DELETE /api/users/{id}                حذف کاربر (فقط مدیر سامانه)
=====================================================================
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import (
    ROLE_LABELS,
    STATUS_LABELS,
    hash_password,
    public_user_info,
    require_roles,
    validate_password_strength,
)

router = APIRouter(prefix="/users", tags=["users"])

# نقش‌هایی که مدیرگروه اجازهٔ مدیریت آن‌ها را دارد
GM_MANAGEABLE = ("professor", "student")
ALL_ROLES = ("admin", "group_manager", "professor", "student")


# ==================================================================
# کمکی‌های دسترسی
# ==================================================================
def _ensure_can_manage(
    actor: User, target: User, *, role_change: bool = False
) -> None:
    if actor.id == target.id:
        raise HTTPException(
            status_code=400,
            detail="این عملیات روی حساب خودتان امکان‌پذیر نیست.",
        )
    if actor.role == "admin":
        return
    # مدیرگروه فقط استاد و دانشجو
    if actor.role == "group_manager" and target.role in GM_MANAGEABLE:
        if role_change:
            raise HTTPException(
                status_code=403,
                detail="تغییر نقش فقط توسط مدیر سامانه امکان‌پذیر است.",
            )
        return
    raise HTTPException(
        status_code=403,
        detail="شما اجازهٔ مدیریت این کاربر را ندارید.",
    )


def _get_target(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")
    return user


def _count_admins(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.role == "admin", User.status == "active")
        .count()
    )


# ==================================================================
# فهرست کاربران
# ==================================================================
@router.get("")
def list_users(
    role: Optional[str] = Query(None, description="فیلتر نقش"),
    status: Optional[str] = Query(None, description="فیلتر وضعیت"),
    q: Optional[str] = Query(None, max_length=100, description="جستجوی نام/نام کاربری"),
    current_user: User = Depends(require_roles("admin", "group_manager")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (User.full_name.ilike(like)) | (User.username.ilike(like))
        )

    # مدیرگروه مدیر سامانه و مدیرگروه‌های دیگر را نمی‌بیند
    if current_user.role != "admin":
        query = query.filter(User.role.in_(GM_MANAGEABLE))

    users = query.order_by(User.created_at.desc()).all()

    return {
        "ok": True,
        "total": len(users),
        "users": [public_user_info(u) for u in users],
    }


@router.get("/pending-count")
def pending_count(
    current_user: User = Depends(require_roles("admin", "group_manager")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(User).filter(User.status == "pending")
    if current_user.role != "admin":
        query = query.filter(User.role.in_(GM_MANAGEABLE))
    return {"ok": True, "pending": query.count()}


# ==================================================================
# تایید / رد
# ==================================================================
@router.post("/{user_id}/approve")
def approve_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin", "group_manager")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = _get_target(db, user_id)
    _ensure_can_manage(current_user, target)
    if target.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="فقط حساب‌های «در انتظار تایید» قابل تایید هستند.",
        )
    target.status = "active"
    target.approved_at = datetime.utcnow()
    target.approved_by_id = current_user.id
    db.commit()
    return {
        "ok": True,
        "message": f"حساب {target.full_name} تایید و فعال شد.",
        "user": public_user_info(target),
    }


@router.post("/{user_id}/reject")
def reject_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin", "group_manager")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = _get_target(db, user_id)
    _ensure_can_manage(current_user, target)
    if target.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="فقط درخواست‌های «در انتظار تایید» قابل رد شدن هستند.",
        )
    target.status = "rejected"
    target.approved_at = None
    db.commit()
    return {
        "ok": True,
        "message": f"درخواست {target.full_name} رد شد.",
        "user": public_user_info(target),
    }


# ==================================================================
# فعال / غیرفعال
# ==================================================================
@router.post("/{user_id}/disable")
def disable_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin", "group_manager")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = _get_target(db, user_id)
    _ensure_can_manage(current_user, target)
    if target.role == "admin" and _count_admins(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="حداقل یک مدیر سامانه باید فعال بماند.",
        )
    if target.status == "disabled":
        raise HTTPException(status_code=400, detail="این حساب قبلاً غیرفعال شده است.")
    target.status = "disabled"
    db.commit()
    return {
        "ok": True,
        "message": f"حساب {target.full_name} غیرفعال شد.",
        "user": public_user_info(target),
    }


@router.post("/{user_id}/enable")
def enable_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin", "group_manager")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = _get_target(db, user_id)
    _ensure_can_manage(current_user, target)
    if target.status != "disabled":
        raise HTTPException(
            status_code=400,
            detail="فقط حساب‌های «غیرفعال» قابل فعال‌سازی هستند.",
        )
    target.status = "active"
    db.commit()
    return {
        "ok": True,
        "message": f"حساب {target.full_name} فعال شد.",
        "user": public_user_info(target),
    }


# ==================================================================
# تغییر نقش (فقط مدیر سامانه)
# ==================================================================
class RoleChangeRequest(BaseModel):
    role: str = Field(..., description="admin | group_manager | professor | student")


@router.put("/{user_id}/role")
def change_role(
    user_id: int,
    payload: RoleChangeRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = _get_target(db, user_id)
    if target.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="تغییر نقش حساب خودتان امکان‌پذیر نیست.",
        )
    if target.role == "admin" and payload.role != "admin" and _count_admins(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="حداقل یک مدیر سامانه باید باقی بماند.",
        )
    if payload.role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="نقش نامعتبر است.")

    old_label = ROLE_LABELS.get(target.role, target.role)
    target.role = payload.role
    # اگر نقش جدید نیازمند تایید است و حساب فعال بوده، فعال می‌ماند
    db.commit()
    return {
        "ok": True,
        "message": (
            f"نقش {target.full_name} از «{old_label}» به "
            f"«{ROLE_LABELS.get(payload.role, payload.role)}» تغییر کرد."
        ),
        "user": public_user_info(target),
    }


# ==================================================================
# بازنشانی رمز عبور
# ==================================================================
class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    current_user: User = Depends(require_roles("admin", "group_manager")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = _get_target(db, user_id)
    _ensure_can_manage(current_user, target)

    weak = validate_password_strength(payload.new_password)
    if weak:
        raise HTTPException(status_code=422, detail=weak)

    target.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {
        "ok": True,
        "message": f"رمز عبور {target.full_name} بازنشانی شد.",
    }


# ==================================================================
# حذف کاربر (فقط مدیر سامانه)
# ==================================================================
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    target = _get_target(db, user_id)
    if target.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="حذف حساب خودتان امکان‌پذیر نیست.",
        )
    if target.role == "admin" and _count_admins(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="حداقل یک مدیر سامانه باید باقی بماند.",
        )
    name = target.full_name
    db.delete(target)
    db.commit()
    return {"ok": True, "message": f"کاربر {name} حذف شد."}
