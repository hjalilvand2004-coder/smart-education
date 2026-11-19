"""یادگیری مشارکتی / دانشجو تولیدکننده (بخش ۹).

چرخه: DRAFT → AI_FEEDBACK → SUBMITTED → PEER_REVIEW → TEACHER_REVIEW → APPROVED
- هیچ تولید دانشجویی مستقیماً وارد بانک رسمی سؤال نمی‌شود.
- رویداد مشارکت معتبر فقط پس از تأیید مرجع به باشگاه ارسال می‌شود (outbox).
"""
import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col

CREATION_TYPES = ("QUESTION_DESIGN", "EXPLANATION", "EXAMPLE", "CRITIQUE")
CREATION_STATUSES = (
    "DRAFT", "AI_FEEDBACK", "SUBMITTED", "PEER_REVIEW", "TEACHER_REVIEW", "APPROVED", "REJECTED",
)


class StudentCreation(TimestampMixin, Base):
    __tablename__ = "student_submissions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(20), index=True)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)  # {title, body, ...}
    ai_feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_use_disclosed: Mapped[bool] = mapped_column(Boolean, default=False)
    peer_reviewer_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # همتایان تخصیص‌یافته
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)


class PeerReview(TimestampMixin, Base):
    __tablename__ = "peer_reviews"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    creation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("student_submissions.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {clarity, correctness, usefulness}
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModerationReview(TimestampMixin, Base):
    """بررسی نهایی استاد/مدیر + کنترل محتوای نامناسب."""

    __tablename__ = "moderation_reviews"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    creation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("student_submissions.id"), index=True)
    moderator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(12))  # APPROVE/REJECT
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
