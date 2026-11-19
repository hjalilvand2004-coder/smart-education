"""عملیات و حاکمیت AI: اجرای مدل، Jobها، حسابرسی و صندوق خروج رویدادها."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col, utcnow


class AIRun(TimestampMixin, Base):
    """هر فراخوانی مدل — نسخه Prompt و مدل ثبت می‌شود (بخش ۱۴.۲)."""

    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(24))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(12), default="SUCCEEDED")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_job_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class JobRun(TimestampMixin, Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(12), default="QUEUED", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[list | None] = mapped_column(JSONB, default=list)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OutboxEvent(TimestampMixin, Base):
    """رویدادهای یکپارچه‌سازی (LMS/باشگاه/داشبورد) — الگوی Transactional Outbox."""

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="PENDING", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
