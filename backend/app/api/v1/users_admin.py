"""مدیریت کاربران و گردش‌کار تایید (فقط مدیر سامانه) — برگرفته از سامانه آموزش هوشمند."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.database import get_db
from app.core.errors import forbidden, not_found, validation_error
from app.core.security import get_current_user, hash_password
from app.models.identity import CourseRole, User

router = APIRouter(prefix="/users", tags=["users"])

GLOBAL_ADMINS = ("EDUCATION_ADMIN", "TECH_ADMIN")
MANAGEABLE_ROLES = ("STUDENT", "PROFESSOR", "ASSISTANT", "GROUP_ADMIN",
                    "EDUCATION_ADMIN", "QUALITY_REVIEWER", "TECH_ADMIN")


def _ensure_admin(user: User) -> None:
    if user.role not in GLOBAL_ADMINS:
        raise forbidden("این بخش فقط برای مدیر سامانه فعال است")


@router.get("")
def list_users(role: str | None = None, approval: str | None = None,
               search: str | None = None, page: int = 1, page_size: int = 50,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_admin(user)
    q = db.query(User).order_by(User.created_at.desc())
    if role:
        q = q.filter(User.role == role)
    if approval:
        q = q.filter(User.approval_status == approval)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter((User.username.like(like)) | (User.full_name.like(like)))
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": str(u.id), "username": u.username, "full_name": u.full_name,
         "email": u.email, "role": u.role, "is_active": u.is_active,
         "approval_status": u.approval_status, "sso_linked": bool(u.sso_subject)}
        for u in rows
    ]}


@router.get("/pending-count")
def pending_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_admin(user)
    return {"pending": db.query(User).filter(User.approval_status == "PENDING").count()}


@router.post("/{user_id}/approve")
def approve(user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise not_found("کاربر یافت نشد")
    target.approval_status = "ACTIVE"
    target.is_active = True
    audit(db, user.id, "USER_APPROVE", "user", target.id, after={"role": target.role})
    db.commit()
    return {"id": str(target.id), "approval_status": "ACTIVE"}


@router.post("/{user_id}/reject")
def reject(user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise not_found("کاربر یافت نشد")
    target.approval_status = "REJECTED"
    target.is_active = False
    audit(db, user.id, "USER_REJECT", "user", target.id)
    db.commit()
    return {"id": str(target.id), "approval_status": "REJECTED"}


@router.post("/{user_id}/disable")
def disable(user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise not_found("کاربر یافت نشد")
    if str(target.id) == str(user.id):
        raise validation_error("غیرفعال‌سازی حساب خودتان مجاز نیست")
    target.is_active = False
    audit(db, user.id, "USER_DISABLE", "user", target.id)
    db.commit()
    return {"id": str(target.id), "is_active": False}


@router.post("/{user_id}/enable")
def enable(user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise not_found("کاربر یافت نشد")
    target.is_active = True
    if target.approval_status == "REJECTED":
        target.approval_status = "ACTIVE"
    audit(db, user.id, "USER_ENABLE", "user", target.id)
    db.commit()
    return {"id": str(target.id), "is_active": True}


class RoleIn(BaseModel):
    role: str


@router.put("/{user_id}/role")
def change_role(user_id: str, body: RoleIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    _ensure_admin(user)
    if body.role not in MANAGEABLE_ROLES:
        raise validation_error("نقش نامعتبر است")
    target = db.get(User, user_id)
    if target is None:
        raise not_found("کاربر یافت نشد")
    old = target.role
    target.role = body.role
    audit(db, user.id, "USER_ROLE_CHANGE", "user", target.id,
          before={"role": old}, after={"role": body.role})
    db.commit()
    return {"id": str(target.id), "role": body.role}


class PasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/{user_id}/reset-password")
def reset_password(user_id: str, body: PasswordIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _ensure_admin(user)
    target = db.get(User, user_id)
    if target is None:
        raise not_found("کاربر یافت نشد")
    target.password_hash = hash_password(body.new_password)
    audit(db, user.id, "USER_PASSWORD_RESET", "user", target.id)
    db.commit()
    return {"id": str(target.id), "message": "رمز عبور بازنشانی شد"}


@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_admin(user)
    if str(user_id) == str(user.id):
        raise validation_error("حذف حساب خودتان مجاز نیست")
    target = db.get(User, user_id)
    if target is None:
        raise not_found("کاربر یافت نشد")
    db.query(CourseRole).filter(CourseRole.user_id == target.id).delete()
    db.delete(target)
    audit(db, user.id, "USER_DELETE", "user", target.id, after={"username": target.username})
    db.commit()
    return {"deleted": True}
