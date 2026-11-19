"""ارزیابی: آزمون، تلاش، پاسخ، بازبینی نمره و اعتراض (بخش‌های ۵ و ۷)."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col, utcnow

ASSESSMENT_KINDS = ("QUIZ", "PRACTICE", "EXAM")
ASSESSMENT_MODES = ("FIXED", "ADAPTIVE_PRACTICE")
FEEDBACK_POLICIES = ("IMMEDIATE", "AFTER_FINISH", "NONE")


class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    offering_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(12), default="QUIZ")
    mode: Mapped[str] = mapped_column(String(20), default="FIXED")  # FIXED | ADAPTIVE_PRACTICE
    blueprint: Mapped[dict] = mapped_column(JSONB, default=dict)  # {sections:[{concept_ids,count,difficulty}]}
    policy: Mapped[dict] = mapped_column(JSONB, default=dict)  # {feedback, allow_hint, shuffle, max_bank_exposure}
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE", index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class Attempt(TimestampMixin, Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="IN_PROGRESS", index=True)
    question_version_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ثابت هنگام آزمون
    selection_log: Mapped[list | None] = mapped_column(JSONB, default=list)  # مسیر انتخاب سؤال
    adaptive_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Response(TimestampMixin, Base):
    __tablename__ = "responses"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id"), index=True)
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"), index=True)
    answer: Mapped[dict] = mapped_column(JSONB, default=dict)
    correctness: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # نمره رسمی نهایی
    grading: Mapped[str] = mapped_column(String(16), default="PENDING")  # AUTO/AI_SUGGESTED/HUMAN/PENDING/NOT_EXECUTED
    ai_feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GradingReview(TimestampMixin, Base):
    """بازبینی/اصلاح نمره توسط استاد — نمره رسمی طبق سیاست انسانی نهایی می‌شود (AC-10)."""

    __tablename__ = "grading_reviews"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    response_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("responses.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    rubric_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResponseDispute(TimestampMixin, Base):
    """اعتراض دانشجو به ارزیابی — ثبت و پیگیری."""

    __tablename__ = "response_disputes"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    response_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("responses.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="OPEN")  # OPEN/RESOLVED/REJECTED
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
