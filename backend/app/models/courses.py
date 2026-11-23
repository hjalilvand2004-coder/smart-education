"""درس، ارئه درس و ثبت‌نام."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, uid_col


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    degree_level: Mapped[str | None] = mapped_column(String(60), nullable=True)  # مقطع
    field_of_study: Mapped[str | None] = mapped_column(String(120), nullable=True)  # رشته
    credits: Mapped[int | None] = mapped_column(default=None, nullable=True)
    term: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    # --- رونوشت همگام‌شده از مرجع (پایه‌یار۳۶۰): منبع حقیقت درس/سرفصل خارج است ---
    reference_system: Mapped[str | None] = mapped_column(String(32), nullable=True)  # baseyar360
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reference_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_system: Mapped[str | None] = mapped_column(String(32), nullable=True)  # مالک داده مرجع
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_state: Mapped[str | None] = mapped_column(String(16), nullable=True)  # VALID/REVIEW_REQUIRED/STALE/UNLINKED


class CourseOffering(TimestampMixin, Base):
    """ارائه ترم مشخص از یک درس."""

    __tablename__ = "course_offerings"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    term: Mapped[str] = mapped_column(String(40))
    professor_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Enrollment(TimestampMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("offering_id", "student_id", name="uq_enrollment"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
