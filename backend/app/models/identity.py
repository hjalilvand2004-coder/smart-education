"""هویت و نقش‌ها."""
import uuid
from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import GUID, Base, TimestampMixin, uid_col

# وضعیت حساب: ثبت‌نام استاد/مدیرگروه نیازمند تایید مدیر سامانه است
APPROVAL_STATUSES = ("ACTIVE", "PENDING", "REJECTED")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), index=True)  # Role enum value
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)
    sso_subject: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    course_roles: Mapped[list["CourseRole"]] = relationship(back_populates="user")

    def to_public(self) -> dict:
        return {
            "id": str(self.id),
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "approval_status": self.approval_status,
        }


class CourseRole(TimestampMixin, Base):
    """نقش کاربر در یک درس (استاد، دستیار، مدیر گروه)."""

    __tablename__ = "course_roles"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    user: Mapped["User"] = relationship(back_populates="course_roles")
