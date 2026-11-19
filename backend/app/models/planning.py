"""برنامه مطالعه شخصی و زمان‌بندی مرور فاصله‌دار (بخش‌های ۶.۳ و ۶.۷)."""
import uuid
from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col, utcnow


class StudyPlan(TimestampMixin, Base):
    __tablename__ = "study_plans"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_hours: Mapped[float] = mapped_column(Float, default=5)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rationale_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE", index=True)  # ACTIVE/ARCHIVED


class StudyActivity(TimestampMixin, Base):
    __tablename__ = "study_activities"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_plans.id"), index=True)
    day_offset: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(300))
    activity_type: Mapped[str] = mapped_column(String(16), default="STUDY")  # REVIEW/PRACTICE/STUDY/DIAGNOSTIC
    concept_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="PROPOSED", index=True)  # PROPOSED/ACCEPTED/DONE/DISMISSED


class ReviewSchedule(TimestampMixin, Base):
    """مرور فاصله‌دار (SM-2 ساده‌شده). خروجی، زمان پیشنهادی مرور است؛
    نه ادعای اندازه‌گیری دقیق حافظه."""

    __tablename__ = "review_schedules"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    interval_days: Mapped[float] = mapped_column(Float, default=1)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    last_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    algorithm: Mapped[str] = mapped_column(String(24), default="sm2-lite-v1")
