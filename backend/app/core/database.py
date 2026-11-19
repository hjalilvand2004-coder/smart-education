"""پیکربندی پایگاه داده.

- نوع UUID و JSONB به‌صورت قابل‌حمل تعریف شده‌اند تا توسعه با SQLite و استقرار با PostgreSQL ممکن باشد.
- در PostgreSQL، JSON روی JSONB نگاشت می‌شود (طبق سند نیازمندی‌ها).
- زمان‌ها همیشه در UTC ذخیره می‌شوند (قواعد داده بخش ۱۱).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, Uuid, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings

JSONB = JSON().with_variant(PG_JSONB(), "postgresql")


class GUID(TypeDecorator):
    """UUID قابل‌حمل: رشته و UUID هر دو پذیرفته می‌شوند؛
    در PostgreSQL به UUID بومی و در SQLite به CHAR(32) نگاشت می‌شود."""

    impl = Uuid
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return uuid.UUID(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# نام سازگار برای مقدار پیش‌فرض ستون‌های UUID
uid_col = new_uuid


def ensure_utc(dt):
    """نرمال‌سازی زمان خوانده‌شده از دیتابیس (SQLite به‌صورت naive برمی‌گرداند)."""
    if dt is None or isinstance(dt, str):
        return dt
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


def _is_sqlite() -> bool:
    return get_settings().database_url.startswith("sqlite")


_engine_kwargs: dict = {"future": True}
if _is_sqlite():
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(get_settings().database_url, **_engine_kwargs)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _record):  # pragma: no cover
    if _is_sqlite():
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """وابستگی FastAPI برای نشست پایگاه داده."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
