"""تست‌های مقطع تحصیلی دانشجو (v3.12.0) — مدل، مهاجرت ستونی افزودنی،
اندپوینت تعیین مقطع، /auth/me و پیکربندی ویجت متناسب با مقطع.

الگوی کاربران: سید حداقلی conftest (st_test دانشجو، prof_test استاد، edu_test مدیر).
"""
from sqlalchemy import create_engine, inspect, text

from app.models.identity import DEGREE_LEVELS, User, degree_level_fa
from app.core.database import SessionLocal


def _find_user(username: str) -> User | None:
    db = SessionLocal()
    u = db.query(User).filter(User.username == username).first()
    db.close()
    return u


# ---------- مدل و برچسب فارسی ----------

def test_degree_levels_constants():
    assert DEGREE_LEVELS == ("KARDANI", "KARSHENASI", "ARASTD", "PHD")
    assert degree_level_fa("ARASTD") == "کارشناسی ارشد"
    assert degree_level_fa("PHD") == "دکترا"
    assert degree_level_fa(None) == "کارشناسی"  # پیش‌فرض امن
    assert degree_level_fa("GARBAGE") == "کارشناسی"


def test_student_default_degree_is_karshenasi(client, ctx):
    """کاربران سیدشده بدون مقطع صریح → پیش‌فرض کارشناسی."""
    st = _find_user("st_test")
    assert st is not None
    assert st.degree_level == "KARSHENASI"


# ---------- /auth/me ----------

def test_me_includes_degree(client, st_headers):
    r = client.get("/api/v1/auth/me", headers=st_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["degree_level"] in DEGREE_LEVELS
    assert body["degree_level_fa"] == degree_level_fa(body["degree_level"])


# ---------- اندپوینت تعیین مقطع ----------

def test_change_degree_level_roundtrip(client, admin_headers):
    u = _find_user("st_test")
    r = client.put(f"/api/v1/users/{u.id}/degree-level", headers=admin_headers,
                   json={"degree_level": "PHD"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["degree_level"] == "PHD"
    assert body["degree_level_fa"] == "دکترا"
    # پایداری در دیتابیس + بازگشت به کارشناسی برای سایر تست‌ها
    db = SessionLocal()
    db.expire_all()
    assert db.get(User, u.id).degree_level == "PHD"
    db.close()
    client.put(f"/api/v1/users/{u.id}/degree-level", headers=admin_headers,
               json={"degree_level": "KARSHENASI"})


def test_change_degree_level_validations(client, admin_headers):
    u = _find_user("st_test")
    assert client.put(f"/api/v1/users/{u.id}/degree-level", headers=admin_headers,
                      json={"degree_level": "MASTER"}).status_code == 422
    # استاد مقطع ندارد
    prof = _find_user("prof_test")
    r = client.put(f"/api/v1/users/{prof.id}/degree-level", headers=admin_headers,
                   json={"degree_level": "PHD"})
    assert r.status_code == 422


def test_change_degree_requires_admin(client, prof_headers):
    u = _find_user("st_test")
    r = client.put(f"/api/v1/users/{u.id}/degree-level", headers=prof_headers,
                   json={"degree_level": "KARDANI"})
    assert r.status_code == 403


def test_users_list_includes_degree(client, admin_headers):
    r = client.get("/api/v1/users", headers=admin_headers,
                   params={"role": "STUDENT"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and all("degree_level" in it and "degree_level_fa" in it for it in items)
    st = next(it for it in items if it["username"] == "st_test")
    assert st["degree_level_fa"] == "کارشناسی"


# ---------- پیکربندی ویجت متناسب با مقطع ----------

def test_widget_config_carries_degree(client, st_headers):
    r = client.get("/api/v1/integration/msu-agent/widget-config", headers=st_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["degree_level"] in DEGREE_LEVELS
    assert body["degree_level_fa"] == degree_level_fa(body["degree_level"])


# ---------- مهاجرت ستونی افزودنی ----------

def test_additive_column_migration(tmp_path):
    """دیتابیس قدیمی بدون ستون degree_level → bootstrap ستون را می‌افزاید و
    مقدار پیش‌فرض می‌دهد؛ دادهٔ موجود دست‌نخورده می‌ماند."""
    import sqlite3

    from app.core.bootstrap import ensure_schema_and_demo
    import app.models  # noqa: F401

    db_file = tmp_path / "old.db"
    raw = sqlite3.connect(db_file)
    # شبیه‌سازی دیتابیس نسخهٔ قبل: جدول users بدون degree_level + یک کاربر
    raw.execute("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, username VARCHAR(64), "
                "full_name VARCHAR(200), password_hash VARCHAR(256), role VARCHAR(32), "
                "is_active BOOLEAN, approval_status VARCHAR(16))")
    raw.execute("INSERT INTO users (id, username, full_name, password_hash, role, "
                "is_active, approval_status) VALUES ('u1', 'old.student', 'دانشجو قدیمی', "
                "'x', 'STUDENT', 1, 'ACTIVE')")
    raw.commit()
    raw.close()

    eng = create_engine(f"sqlite:///{db_file}")
    ensure_schema_and_demo(eng)  # جداول غایب + ستون degree_level

    cols = {c["name"] for c in inspect(eng).get_columns("users")}
    assert "degree_level" in cols
    with eng.connect() as conn:
        val = conn.execute(text("SELECT degree_level FROM users WHERE id='u1'")).scalar()
    assert val == "KARSHENASI"  # مقدار پیش‌فرض برای کاربر موجود
    # idempotent — اجرای دوم خطا نمی‌دهد
    ensure_schema_and_demo(eng)
