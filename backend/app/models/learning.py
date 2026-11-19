"""مدل یادگیری: رویدادها، تخمین تسلط و فرضیه‌های تشخیصی (بخش ۶).

- پاسخ خام دانشجو از تخمین مدل جدا ذخیره می‌شود؛ تخمین‌ها قابل بازتولید هستند
  (تابع خالص از learning_events با ذخیره model_version).
- نبود شواهد = وضعیت UNKNOWN، نه ضعف قطعی (AC-08).
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Float, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col, utcnow

EVENT_TYPES = (
    "RESPONSE_SUBMITTED", "CONTENT_VIEWED", "TUTOR_MESSAGE",
    "PRACTICE_COMPLETED", "RESOURCE_VIEWED",
)
MASTERY_STATUSES = ("KNOWN", "PARTIAL", "WEAK", "UNKNOWN")
DIAGNOSIS_TYPES = (
    "CURRENT_WEAK", "PREREQ_WEAK", "MISCONCEPTION",
    "SOLUTION_METHOD", "CALCULATION_ERROR", "COMPREHENSION", "INSUFFICIENT_EVIDENCE",
)


class LearningEvent(TimestampMixin, Base):
    """شواهد خام یادگیری — مبنای محاسبه تسلط و مرور فاصله‌دار."""

    __tablename__ = "learning_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    offering_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    event_type: Mapped[str] = mapped_column(String(24), index=True)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    question_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    correctness: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hint_used: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MasteryEstimate(TimestampMixin, Base):
    __tablename__ = "mastery_estimates"
    __table_args__ = (UniqueConstraint("learner_id", "course_id", "concept_id", name="uq_mastery"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    estimated_mastery: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="UNKNOWN", index=True)
    uncertainty: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(String(40), default="weighted-rules-v1")
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiagnosticHypothesis(TimestampMixin, Base):
    """فرضیه آموزشی ریشه ضعف — تشخیص قطعی نیست؛ امکان پیشنهاد سؤال تشخیصی جدید."""

    __tablename__ = "diagnostic_hypotheses"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    hypothesis_type: Mapped[str] = mapped_column(String(28), index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE", index=True)
