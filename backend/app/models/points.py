"""امتیاز مشارکت اساتید — ثبت خودکار زحمت تولید محتوا و خروجی‌ها (v3.5.0).

هر بار استاد از یک سرفصلِ واکشی‌شده از پایه‌یار۳۶۰ محتوا تولید می‌کند یا خروجی
می‌گیرد، امتیاز در همین جدول ثبت می‌شود. قاعدهٔ جلوگیری از امتیاز تکراری با
dedup_key یکتا تضمین می‌شود (هر نسخهٔ محتوا یک‌بار امتیاز تولید و هر قالب
خروجی حداکثر یک‌بار امتیاز خروجی می‌گیرد).
"""
import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, uid_col


class ContributionPoint(TimestampMixin, Base):
    """یک رکورد امتیاز برای اقدام استاد روی محتوای سرفصل (MDM پایه‌یار۳۶۰)."""

    __tablename__ = "contribution_points"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)  # CONTENT_GENERATE / CONTENT_EXPORT
    points: Mapped[int] = mapped_column(Integer, default=0)
    course_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    fmt: Mapped[str | None] = mapped_column(String(12), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
