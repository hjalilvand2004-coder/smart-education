"""تست‌های بوت‌استرپ دیتابیس — ریشهٔ باگ «no such table: users» نسخهٔ ۳.۲.۱.

در بستهٔ پرتیبل اگر دیتابیس بذرشده نبود، اپ با فایل SQLite خالی بالا می‌آمد و
اولین لاگین کرش می‌کرد. بوت‌استرپ ۳.۲.۲ باید در این حالت جدول‌ها (و در صورت
مجوز، دادهٔ نمونهٔ دمو) را خودکار بسازد.
"""
from sqlalchemy import create_engine, inspect

import app.services.demo_seed as demo_seed_mod
from app.core.bootstrap import ensure_schema_and_demo
from app.core.config import get_settings
from app.core.database import Base
import app.models  # noqa: F401 — پر کردن metadata
from app.models.identity import User
from app.core.security import hash_password


def _fresh_engine(tmp_path, name):
    path = tmp_path / f"{name}.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def test_bootstrap_creates_schema_on_empty_sqlite(tmp_path, monkeypatch):
    """دیتابیس خالی → جدول‌ها خودکار ساخته می‌شوند (بدون داده، وقتی seed خاموش است)."""
    monkeypatch.setenv("S360_BOOTSTRAP_DEMO_SEED", "false")
    get_settings.cache_clear()
    try:
        eng = _fresh_engine(tmp_path, "fresh")
        assert "users" not in inspect(eng).get_table_names()
        ensure_schema_and_demo(eng)
        tables = set(inspect(eng).get_table_names())
        assert {"users", "courses", "course_offerings"} <= tables
        # فراخوانی دوباره نباید خطا بدهد (idempotent)
        ensure_schema_and_demo(eng)
    finally:
        get_settings.cache_clear()


def test_bootstrap_skips_existing_schema(tmp_path, monkeypatch):
    """دیتابیس مقداردهی‌شده → هیچ دخالتی نمی‌کند (داده‌های کاربر دست‌نخورده)."""
    monkeypatch.setenv("S360_BOOTSTRAP_DEMO_SEED", "true")
    get_settings.cache_clear()
    try:
        eng = _fresh_engine(tmp_path, "existing")
        Base.metadata.create_all(eng)
        from sqlalchemy.orm import Session
        with Session(eng) as s:
            s.add(User(username="only.user", full_name="کاربر فعلی",
                       password_hash=hash_password("Pass1234!"), role="STUDENT"))
            s.commit()
        called = []
        monkeypatch.setattr(demo_seed_mod, "seed_demo_data", lambda: called.append(1))
        ensure_schema_and_demo(eng)
        assert called == []  # seed دمو اجرا نشد
        with Session(eng) as s:
            usernames = [u.username for u in s.query(User).all()]
        assert usernames == ["only.user"]
    finally:
        get_settings.cache_clear()


def test_bootstrap_seeds_demo_when_enabled(tmp_path, monkeypatch):
    """دیتابیس خالی + مجوز seed → سرویس demo_seed صدا زده می‌شود (سیم‌کشی درست)."""
    monkeypatch.setenv("S360_BOOTSTRAP_DEMO_SEED", "true")
    get_settings.cache_clear()
    try:
        eng = _fresh_engine(tmp_path, "seeded")
        called = []
        monkeypatch.setattr(demo_seed_mod, "seed_demo_data", lambda: called.append(1))
        ensure_schema_and_demo(eng)
        assert called == [1]
        assert "users" in inspect(eng).get_table_names()
    finally:
        get_settings.cache_clear()


def test_bootstrap_non_sqlite_untouched(tmp_path, monkeypatch):
    """موتور غیر-SQLite (شبیه‌سازی‌شده) → بدون هیچ عملیاتی."""
    monkeypatch.setenv("S360_BOOTSTRAP_DEMO_SEED", "true")
    get_settings.cache_clear()
    try:
        eng = _fresh_engine(tmp_path, "fake")
        monkeypatch.setattr(type(eng.url), "get_backend_name",
                            lambda self: "postgresql", raising=False)
        called = []
        monkeypatch.setattr(demo_seed_mod, "seed_demo_data", lambda: called.append(1))
        ensure_schema_and_demo(eng)
        assert called == []
        assert inspect(eng).get_table_names() == []
    finally:
        get_settings.cache_clear()
