"""محتوای آموزشی ساختاریافته: سند، طرح آموزشی، نسخه‌ها و بررسی‌ها (بخش ۴).

- محتوای مرجع، ساختاریافته (بلوکی) است و خروجی‌های مختلف از آن تبدیل می‌شوند.
- ویرایش بلوک با قفل بهینه (expected_revision) — جلوگیری از بازنویسی هم‌زمان.
- انتشار نسخه قبلی را تغییر نمی‌دهد؛ ویرایش نسخه منتشرشده، نسخه جدید می‌سازد.
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col, utcnow

CONTENT_STATUSES = (
    "DRAFT", "GENERATING", "GENERATED", "UNDER_REVIEW", "APPROVED",
    "PUBLISHED", "ARCHIVED", "FAILED", "NEEDS_REVISION", "WITHDRAWN",
)


class ContentDocument(TimestampMixin, Base):
    """سند آموزشی متصل به نسخه مشخص سرفصل (AC-01)."""

    __tablename__ = "content_documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    syllabus_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("syllabus_versions.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    goal: Mapped[str] = mapped_column(String(32), default="CONCEPT_TEACHING")
    scope: Mapped[dict] = mapped_column(JSONB, default=dict)  # {topic_ids, concept_ids}
    audience_level: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="FA")
    style: Mapped[str] = mapped_column(String(24), default="ACADEMIC")
    components: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_resource_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    constraints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class ContentPlan(TimestampMixin, Base):
    """طرح طراحی آموزشی (مرحله اول) — پیش از تولید کامل، توسط استاد اصلاح/تأیید می‌شود."""

    __tablename__ = "content_plans"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_documents.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="PROPOSED", index=True)  # PROPOSED/CONFIRMED
    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class ContentVersion(TimestampMixin, Base):
    __tablename__ = "content_versions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_documents.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    syllabus_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("syllabus_versions.id"), index=True)
    structured_content: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"blocks": [...]}
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)  # قفل بهینه ویرایش بلوک‌ها
    plan_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    qc_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    human_changes: Mapped[list | None] = mapped_column(JSONB, default=list)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContentReview(TimestampMixin, Base):
    __tablename__ = "content_reviews"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    content_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_versions.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(24))  # SUBMIT_FOR_REVIEW/APPROVE/REQUEST_CHANGES
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
