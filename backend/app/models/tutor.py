"""استاد هوشمند گفتگو‌محور (بخش ۸): نشست، پیام و ارجاع منابع.

- حالت «یادگیری» از «آزمون» جدا است؛ در حالت آزمون سطح کمک طبق سیاست محدود می‌شود.
- کلید امتحان فعال وارد مخزن بازیابی نمی‌شود (AC-09).
- گفتگو منبع قطعی تسلط محسوب نمی‌شود (رویداد TUTOR_MESSAGE وزن صفر دارد).
"""
import uuid
from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col

TUTOR_MODES = ("LEARNING", "ASSESSMENT")


class TutorSession(TimestampMixin, Base):
    __tablename__ = "tutor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    mode: Mapped[str] = mapped_column(String(12), default="LEARNING")
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE", index=True)


class TutorMessage(TimestampMixin, Base):
    __tablename__ = "tutor_messages"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tutor_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # latency, run_id, mode
    reported: Mapped[bool] = mapped_column(Boolean, default=False)
    report_note: Mapped[str | None] = mapped_column(Text, nullable=True)
