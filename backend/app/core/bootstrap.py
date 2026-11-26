"""بوت‌استرپ خودکار دیتابیس — ریشهٔ باگ «no such table: users» در نسخهٔ پرتیبل.

در بستهٔ پرتیبل ممکن است دیتابیس بذرشده در بسته نباشد (یا کاربر آن را حذف
کرده باشد)؛ اپ تا پیش از ۳.۲.۲ با یک فایل SQLite خالی بالا می‌آمد و اولین
لاگین با «no such table: users» کرش می‌کرد. این ماژول در startup:
  - فقط برای SQLite: اگر جدول users وجود نداشت، کل schema را با create_all
    می‌سازد و در صورت مجوز (S360_BOOTSTRAP_DEMO_SEED) دادهٔ نمونهٔ دمو را با
    همان خط تولید واقعی (demo_seed) می‌ریزد.
  - در Production (PostgreSQL) و دیتابیس‌های مقداردهی‌شده هیچ دخالتی نمی‌کند
    (schema آنجا با Alembic مدیریت می‌شود).
"""
from pathlib import Path

from sqlalchemy import inspect

from app.core.config import get_settings
from app.core.database import Base, engine
import app.models  # noqa: F401 — پر کردن Base.metadata


def ensure_schema_and_demo(eng=None) -> None:
    """ساخت schema و دادهٔ نمونه فقط برای دیتابیس SQLiteِ خالی.

    eng: موتور دیتابیس (پیش‌فرض: موتور اصلی اپ) — برای تست‌ها قابل تزریق.
    """
    eng = eng or engine
    if not eng.url.get_backend_name().startswith("sqlite"):
        return
    db_path = eng.url.database
    if db_path:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    inspector = inspect(eng)
    if "users" in inspector.get_table_names():
        # schema موجود است؛ اما ارتقای افزودنی نسخه‌ها: جداول جدید (مثل
        # msu_agent_connection در v3.11.0) با checkfirst فقط «اگر غایب بودند»
        # ساخته می‌شوند و ستون‌های جدید (مثل users.degree_level در v3.12.0)
        # با ALTER TABLE افزودنی اضافه می‌شوند — هیچ داده‌ای دست نمی‌خورد.
        Base.metadata.create_all(eng)
        _ensure_columns(eng, inspector)
        return
    Base.metadata.create_all(eng)
    if get_settings().bootstrap_demo_seed:
        from app.services.demo_seed import seed_demo_data
        seed_demo_data()


# ستون‌های افزوده‌شده پس از انتشار اولین نسخه — {جدول: {ستون: تعریف SQL}}
# فقط «اگر غایب بودند» با ALTER TABLE افزودنی ساخته می‌شوند (SQLite).
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "degree_level": "VARCHAR(16) NOT NULL DEFAULT 'KARSHENASI'",
    },
}


def _ensure_columns(eng, inspector) -> None:
    """مهاجرت ستونی افزودنی برای دیتابیس‌های SQLite موجود (idempotent)."""
    from sqlalchemy import text

    for table, cols in _ADDED_COLUMNS.items():
        if table not in inspector.get_table_names():
            continue  # جدول تازه با create_all کامل ساخته شده
        existing = {c["name"] for c in inspector.get_columns(table)}
        for col, ddl in cols.items():
            if col not in existing:
                with eng.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
