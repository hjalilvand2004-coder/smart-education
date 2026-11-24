# -*- coding: utf-8 -*-
"""
=====================================================================
اجراکننده نسخهٔ قابل حمل (Portable) — دانشجو۳۶۰
=====================================================================
این اسکریپت نقطهٔ ورود ساخت فایل اجرایی با PyInstaller است:
 - سرور FastAPI + رابط کاربری باندل‌شده (SPA) را اجرا می‌کند
 - دیتابیس و داده‌ها را کنار فایل exe نگه می‌دارد (قابل حمل روی فلش USB)
 - مرورگر را به‌صورت خودکار باز می‌کند
 - پورت پیش‌فرض 8084 است؛ اگر اشغال باشد پورت بعدی به‌صورت خودکار استفاده می‌شود
 - تنظیمات اپ فقط با پیشوند S360_ خوانده می‌شوند (اصلاح ۳.۲.۱)
=====================================================================
"""
VERSION = "3.4.1"  # نسخهٔ بستهٔ قابل حمل — همگام با تگ ریلیز به‌روزرسانی شود
import os
import sys
import time
import shutil
import socket
import threading
import webbrowser

APP_NAME = "SmartEducation"
PREFERRED_PORT = 8084  # آدرس رسمی سامانه: http://188.212.96.235:8084
BIND_HOST = "0.0.0.0"  # گوش‌دادن روی همهٔ کارت‌های شبکه تا آدرس IP در دسترس باشد


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
            print("[i] دیتابیس جدید ساخته می‌شود؛ جدول‌ها و دادهٔ نمونهٔ دمو "
                  "به‌صورت خودکار آماده خواهند شد (bootstrap ۳.۲.۲).")

    # متغیرهای محیطی اپ — همهٔ تنظیمات دانشجو۳۶۰ با پیشوند S360_ خوانده می‌شوند
    # (اصلاح ۳.۲.۱: نام‌های قبلی DATABASE_URL/EXPORTS_DIR/FRONTEND_DIST_DIR هیچ‌گاه
    #  خوانده نمی‌شدند و باعث «Not Found» صفحه وب و دیتابیس خالی در exe می‌شدند)
    os.environ["S360_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["S360_STORAGE_DIR"] = os.path.join(data_dir, "storage")

    # مسیر رابط کاربری ساخته‌شده
    fe = os.path.join(resource_base(), "frontend_dist")
    if os.path.isdir(os.path.join(fe, "assets")):
        os.environ["S360_FRONTEND_DIST"] = fe
        print(f"[i] رابط کاربری باندل‌شده: {fe}")
    else:
        print("[!] frontend_dist در بسته یافت نشد — سامانه فقط-API بالا می‌آید.")

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
    print(f"  دانشجو۳۶۰ — نسخهٔ قابل حمل  (v{VERSION})")
    print("  Student360 — Smart Learning Platform (Portable)")
    print("=" * 62)

    prepare_environment()

    import uvicorn  # بعد از تنظیم env ها

    port = find_free_port()
    local_url = f"http://127.0.0.1:{port}"

    # پیش‌فرض‌های ورود یکگانه روی همین پورت (فقط اگر مدیر مقدار نداده باشد)
    os.environ.setdefault("S360_SSO_FRONTEND_BASE", local_url)
    os.environ.setdefault("S360_SSO_REDIRECT_URI", f"{local_url}/api/v1/auth/sso/callback")
    # یکپارچه‌سازی برنامه‌یار۳۶۰ (در Settings پیش‌فرض رسمی دارد؛ اینجا فقط اطمینان)
    os.environ.setdefault("S360_PROGRAMYAR_BASE_URL", "http://188.212.96.235:8083")

    print(f"[i] رابط کاربری (محلی):    {local_url}  ← مرورگر خودکار باز می‌شود")
    print(f"[i] دسترسی از شبکه/IP:    http://<ip-this-server>:{port}")
    print(f"[i] حساب‌های نمونه:        prof.rezaei / student.sara / edu.admin — رمز: Pass1234!")
    print("[i] برای خروج، این پنجره را ببندید یا Ctrl+C بزنید.")
    print("-" * 62)

    open_browser_later(local_url)

    try:
        uvicorn.run(
            "app.main:app",
            host=BIND_HOST,
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
