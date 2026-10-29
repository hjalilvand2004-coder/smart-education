# -*- coding: utf-8 -*-
"""
=====================================================================
اجراکننده نسخهٔ قابل حمل (Portable) — سامانه هوشمند آموزش
=====================================================================
این اسکریپت نقطهٔ ورود ساخت فایل اجرایی با PyInstaller است:
 - سرور FastAPI + رابط کاربری + استودیو گزارش‌ها را اجرا می‌کند
 - دیتابیس و خروجی گزارش‌ها را کنار فایل exe نگه می‌دارد
   (قابل حمل روی فلش USB)
 - مرورگر را به‌صورت خودکار باز می‌کند
 - پورت پیش‌فرض 8100 است تا اگر «سامانه برنامه‌ریزی درسی» (پورت
   8000) همزمان اجرا باشد، هر دو سامانه بدون تداخل کار کنند و
   سرویس‌دهی لیست درس‌ها برقرار بماند
=====================================================================
"""
import os
import sys
import time
import shutil
import socket
import threading
import webbrowser

APP_NAME = "SmartEducation"
PREFERRED_PORT = 8100  # پورت 8000 برای سرویس scheduler رزرو شده است


def app_base() -> str:
    """پوشه‌ای که فایل اجرایی (exe) در آن قرار دارد — برای داده‌ها."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_base() -> str:
    """پوشه منابع باندل‌شده (frontend_dist و ...)."""
    if getattr(sys, "frozen", False):
        # onedir: sys._MEIPASS به پوشه _internal اشاره می‌کند
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_free_port(preferred: int = PREFERRED_PORT, tries: int = 12) -> int:
    """پورت دلخواه را امتحان می‌کند؛ اگر اشغال بود پورت‌های بعدی."""
    port = preferred
    for _ in range(tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port  # آزاد است
        port += 1
    return preferred


def prepare_environment() -> None:
    """
    پوشه‌های داده (data و exports) را کنار exe آماده می‌کند و
    متغیرهای محیطی برنامه را تنظیم می‌کند.
    """
    base = app_base()
    data_dir = os.path.join(base, "data")
    exports_dir = os.path.join(base, "exports")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(exports_dir, exist_ok=True)

    db_path = os.path.join(data_dir, "education.db")

    # اگر دیتابیس نیست، از نسخهٔ نمونهٔ باندل‌شده کپی کن
    if not os.path.exists(db_path):
        seed = os.path.join(resource_base(), "education.db")
        if os.path.exists(seed):
            shutil.copy2(seed, db_path)
            print(f"[i] دیتابیس نمونه در {db_path} قرار گرفت.")
        else:
            print("[i] دیتابیس جدید ساخته می‌شود.")

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["EXPORTS_DIR"] = exports_dir

    # مسیر رابط کاربری ساخته‌شده
    fe = os.path.join(resource_base(), "frontend_dist")
    if os.path.isdir(os.path.join(fe, "assets")):
        os.environ["FRONTEND_DIST_DIR"] = fe

    # آدرس سرویس برنامه‌ریزی درسی (قابل تغییر با SCHEDULER_BASE_URL)
    os.environ.setdefault("SCHEDULER_BASE_URL", "http://127.0.0.1:8000")

    # مسیر کار برنامه کنار exe تا لاگ‌ها و فایل‌ها آنجا باشند
    os.chdir(os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__
    )))


def open_browser_later(url: str, delay: float = 2.2) -> None:
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    print("=" * 62)
    print("  سامانه هوشمند آموزش — نسخهٔ قابل حمل")
    print("  Smart Education — Portable Edition")
    print("=" * 62)

    prepare_environment()

    import uvicorn  # بعد از تنظیم env ها

    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    scheduler_url = os.environ.get("SCHEDULER_BASE_URL", "")

    print(f"[i] آدرس سامانه:        {url}")
    print(f"[i] استودیو گزارش‌ها:   {url}/reports-page")
    print(f"[i] سرویس برنامه‌ریزی:  {scheduler_url} (در صورت اجرا بودن)")
    print("[i] برای خروج، این پنجره را ببندید یا Ctrl+C بزنید.")
    print("-" * 62)

    open_browser_later(url)

    try:
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"[!] خطا در اجرای سرور: {exc}")
        time.sleep(8)
        raise


if __name__ == "__main__":
    main()
