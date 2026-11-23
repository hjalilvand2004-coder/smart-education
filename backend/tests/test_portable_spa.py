"""تست‌های serve فرانت‌اند در نسخهٔ پرتیبل — ریشهٔ باگ «Not Found» نسخهٔ ۳.۲.۰.

لانچر exe قدیمی متغیر FRONTEND_DIST_DIR را ست می‌کرد در حالی که اپ فقط
S360_FRONTEND_DIST می‌خواند؛ و fallback توسعه‌ای (parents[2]/frontend/dist)
در چیدمان بستهٔ PyInstaller وجود ندارد. این تست‌ها رفتار resolver جدید را در
همهٔ چیدمان‌ها قفل می‌کنند تا این باگ دیگر بازنگردد.
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import _resolve_frontend_dist, create_app


def _make_dist(root: Path) -> Path:
    """یک frontend_dist ساختگی با index.html و یک asset."""
    dist = root / "frontend_dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><body>spa-marker</body></html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


# ---------- resolver ----------

def test_resolver_prefers_explicit_setting(tmp_path):
    dist = _make_dist(tmp_path)
    assert _resolve_frontend_dist(str(dist)) == dist


def test_resolver_frozen_meipass(tmp_path, monkeypatch):
    """onedir/onefile: دادهٔ باندل‌شده زیر sys._MEIPASS."""
    dist = _make_dist(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert _resolve_frontend_dist("") == dist


def test_resolver_frozen_internal_without_meipass(tmp_path, monkeypatch):
    """onedir بدون _MEIPASS: مسیر <exe>/_internal/frontend_dist."""
    appdir = tmp_path / "SmartEducation"
    dist = _make_dist(appdir / "_internal")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(appdir / "SmartEducation.exe"),
                        raising=False)
    assert _resolve_frontend_dist("") == dist


def test_resolver_source_tree_fallback(tmp_path, monkeypatch):
    """حالت توسعه: همان مسیر قدیمی <repo>/frontend/dist نسبت به app/main.py."""
    repo = tmp_path / "repo"
    dist = repo / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>dev</html>", encoding="utf-8")
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    # __file__ ساختگی: <repo>/backend/app/main.py → parents[2] == <repo>
    fake_main = repo / "backend" / "app" / "main.py"
    fake_main.parent.mkdir(parents=True)
    fake_main.write_text("", encoding="utf-8")
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "__file__", str(fake_main), raising=False)
    assert _resolve_frontend_dist("") == dist


def test_resolver_skips_setting_without_index(tmp_path, monkeypatch):
    """متغیر محیطی به پوشهٔ بدون index.html نباید جلوی یافتن نسخهٔ درست را بگیرد."""
    bad = tmp_path / "empty"
    bad.mkdir()
    dist = _make_dist(tmp_path / "real")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "real"), raising=False)
    assert _resolve_frontend_dist(str(bad)) == dist


# ---------- یکپارچه: serve SPA با متغیری که لانچر اصلاح‌شده ست می‌کند ----------

def test_spa_served_with_s360_env(tmp_path, monkeypatch):
    dist = _make_dist(tmp_path)
    monkeypatch.setenv("S360_FRONTEND_DIST", str(dist))
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        r = client.get("/")
        assert r.status_code == 200, r.text
        assert "spa-marker" in r.text
        # fallback SPA برای مسیرهای کلاینت‌ساید
        r2 = client.get("/courses")
        assert r2.status_code == 200 and "spa-marker" in r2.text
        # asset واقعی مستقیم سرو می‌شود
        r3 = client.get("/assets/app.js")
        assert r3.status_code == 200 and "console.log" in r3.text
        # مسیرهای API همچنان JSON ۴۰۴ می‌گیرند، نه HTML
        r4 = client.get("/api/v1/definitely-missing")
        assert r4.status_code == 404
        assert r4.headers["content-type"].startswith("application/json")
    finally:
        get_settings.cache_clear()


def test_api_only_mode_without_dist(tmp_path, monkeypatch):
    """بدون هیچ dist معتبری، اپ فقط-API بالا می‌آید (بدون mount SPA)."""
    monkeypatch.setenv("S360_FRONTEND_DIST", str(tmp_path / "nothing"))
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
    finally:
        get_settings.cache_clear()
