"""سرفصل مصوب: نسخه‌ها، فصل/موضوع‌ها و اهداف یادگیری.

- هر تولید محتوا باید به نسخه مشخصی از سرفصل متصل باشد (AC-01).
- نسخه مصوب قابل ویرایش مستقیم نیست؛ تغییر، نسخه جدید می‌سازد (بخش ۳.۱).
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, uid_col

SYLLABUS_STATUSES = ("DRAFT", "PENDING_REVIEW", "APPROVED", "SUPERSEDED")


class SyllabusVersion(TimestampMixin, Base):
    __tablename__ = "syllabus_versions"
    __table_args__ = (UniqueConstraint("course_id", "version_number", name="uq_syllabus_version"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200), default="سرفصل درس")
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    source_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)  # TEXT/DOCX/PDF/MANUAL/REFERENCE_SYNC
    official_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    official_file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approval_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)  # مرجع تصویب
    reference_version: Mapped[str | None] = mapped_column(String(32), nullable=True)  # نسخه سرفصل در پایه‌یار۳۶۰
    approved_date_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prerequisites_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_policy: Mapped[str | None] = mapped_column(Text, nullable=True)  # سیاست ارزیابی
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ambiguous_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # بخش‌های نیازمند بررسی
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class SyllabusTopic(TimestampMixin, Base):
    """فصل (kind=CHAPTER) یا موضوع (kind=TOPIC) در نسخه سرفصل."""

    __tablename__ = "syllabus_topics"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    syllabus_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("syllabus_versions.id"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    kind: Mapped[str] = mapped_column(String(12), default="TOPIC")
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    suggested_hours: Mapped[float | None] = mapped_column(nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)  # استخراج مبهم
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # شناسه موضوع در پایه‌یار۳۶۰


class LearningObjective(TimestampMixin, Base):
    """هدف یادگیری قابل ارزیابی متصل به نسخه سرفصل (و اختیاری موضوع)."""

    __tablename__ = "learning_objectives"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    syllabus_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("syllabus_versions.id"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    code: Mapped[str] = mapped_column(String(16))  # مثل LO1
    statement: Mapped[str] = mapped_column(Text)
    bloom_level: Mapped[str | None] = mapped_column(String(24), nullable=True)
    assessable: Mapped[bool] = mapped_column(Boolean, default=True)
