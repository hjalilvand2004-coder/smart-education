from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from .config import DATABASE_URL


# ============================================================
# مسیرها و تنظیمات دیتابیس
# ============================================================

# مسیر پوشه app
APP_DIR = Path(__file__).resolve().parent

# ریشه Backend
BACKEND_DIR = APP_DIR.parent

# مسیر پیش‌فرض دیتابیس
DEFAULT_DATABASE_FILE = BACKEND_DIR / "education.db"


def make_absolute_sqlite_url(database_url: str) -> str:
    """
    تبدیل مسیر SQLite به URL با مسیر مطلق.

    مثال:

        sqlite:///./education.db

    تبدیل می‌شود به:

        sqlite:////J:/.../backend/education.db

    اگر مسیر SQLite از قبل مطلق باشد، بدون تغییر اساسی
    به URL استاندارد تبدیل می‌شود.
    """

    if not database_url.startswith("sqlite"):
        return database_url

    # دیتابیس حافظه‌ای SQLite
    if database_url in {
        "sqlite://",
        "sqlite:///:memory:",
    }:
        return database_url

    prefix = "sqlite:///"

    if not database_url.startswith(prefix):
        return database_url

    raw_path = database_url[len(prefix):]

    # حذف query string احتمالی
    raw_path = raw_path.split("?", 1)[0]

    # مسیر استاندارد برای دیتابیس پیش‌فرض
    if raw_path in {
        "",
        ":memory:",
        "./education.db",
        "education.db",
    }:
        database_file = DEFAULT_DATABASE_FILE

    else:
        database_file = Path(raw_path)

        # مسیرهایی مانند ./education.db نسبی هستند.
        if not database_file.is_absolute():
            database_file = BACKEND_DIR / database_file

        database_file = database_file.resolve()

    database_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # برای Windows، SQLAlchemy به چهار اسلش نیاز دارد:
    #
    # sqlite:///C:/file.db  -> مسیر نسبی/غیرمطمئن
    # sqlite:///C:/file.db  -> در URL داخلی SQLAlchemy
    #
    # با as_posix از مشکل backslash جلوگیری می‌کنیم.
    return f"sqlite:///{database_file.as_posix()}"


DATABASE_URL = make_absolute_sqlite_url(DATABASE_URL)


# ============================================================
# تنظیمات Engine
# ============================================================

connect_args: dict[str, Any] = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
    }


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)


# ============================================================
# فعال‌سازی Foreign Key در SQLite
# ============================================================

@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    connection_record: Any,
) -> None:
    """
    فعال‌سازی Foreign Key برای SQLite.

    SQLite به‌صورت پیش‌فرض ممکن است Foreign Keyها را
    enforce نکند. این گزینه باعث می‌شود ondelete='CASCADE'
    و ondelete='SET NULL' به‌درستی اجرا شوند.
    """

    if not DATABASE_URL.startswith("sqlite"):
        return

    cursor = dbapi_connection.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys=ON")

    finally:
        cursor.close()


# ============================================================
# Session
# ============================================================

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ============================================================
# Base مدل‌های SQLAlchemy
# ============================================================

class Base(DeclarativeBase):
    """
    کلاس پایه تمام مدل‌های SQLAlchemy.
    """

    pass


# ============================================================
# Dependency برای FastAPI
# ============================================================

def get_db() -> Generator[Session, None, None]:
    """
    برای هر درخواست FastAPI یک Session ایجاد می‌کند
    و پس از پایان درخواست آن را می‌بندد.
    """

    db = SessionLocal()

    try:
        yield db

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# ایجاد جدول‌ها
# ============================================================

def create_tables() -> None:
    """
    جدول‌های مدل‌های SQLAlchemy را ایجاد می‌کند.

    جدول‌های موجود حذف نمی‌شوند.
    """

    # باید مدل‌ها قبل از create_all import شوند
    # تا در Base.metadata ثبت شده باشند.
    from . import models  # noqa: F401

    Base.metadata.create_all(
        bind=engine,
    )


# ============================================================
# حذف همه جدول‌ها
# ============================================================

def drop_all_tables() -> None:
    """
    تمام جدول‌های دیتابیس را حذف می‌کند.

    هشدار:
    این تابع تمام اطلاعات را حذف می‌کند و نباید
    به‌صورت خودکار هنگام اجرای برنامه فراخوانی شود.
    """

    from . import models  # noqa: F401

    Base.metadata.drop_all(
        bind=engine,
    )


# ============================================================
# بازسازی کامل دیتابیس
# ============================================================

def reset_database() -> None:
    """
    تمام جدول‌ها را حذف و دوباره ایجاد می‌کند.

    هشدار:
    تمام دوره‌ها، سرفصل‌ها، محتواها، آزمون‌ها،
    پرسش‌ها و تلاش‌های آزمون حذف می‌شوند.
    """

    drop_all_tables()
    create_tables()


# ============================================================
# حذف اطلاعات یک درس
# ============================================================

def clear_course_data(
    db: Session,
    course_id: int,
) -> None:
    """
    حذف کامل یک درس و اطلاعات وابسته به آن.

    موارد وابسته شامل موارد زیر هستند:

    - سرفصل‌های CourseTopic
    - محتوای آموزشی
    - آزمون‌ها
    - پرسش‌ها
    - تلاش‌های آزمون

    حذف با خود شیء Course انجام می‌شود تا cascade رابطه‌های
    تعریف‌شده در models.py فعال شوند.
    """

    if course_id <= 0:
        raise ValueError(
            "course_id باید بزرگ‌تر از صفر باشد."
        )

    from .models import Course

    course = db.get(
        Course,
        course_id,
    )

    if course is None:
        return

    db.delete(course)
    db.flush()


# ============================================================
# نمایش مسیر دیتابیس
# ============================================================

def get_database_url() -> str:
    """
    بازگرداندن URL نهایی دیتابیس برای بررسی و اشکال‌زدایی.
    """

    return DATABASE_URL