# -*- coding: utf-8 -*-
"""
=====================================================================
اجراکننده نسخهٔ قابل حمل (Portable) — دانشجو۳۶۰
=====================================================================
این اسکریپت نقطهٔ ورود ساخت فایل اجرایی با PyInstaller است:
 - سرور FastAPI + رابط کاربری باندل‌شده (SPA) را اجرا می‌کند
 - دیتابیس و داده‌ها را کنار فایل exe نگه می‌دارد (قابل حمل روی فلش USB)
 - مرورگر را به‌صورت خودکار باز می‌کند
 - پورت پیش‌فرض 8093 است؛ اگر اشغال باشد پورت بعدی به‌صورت خودکار استفاده می‌شود
 - تنظیمات اپ فقط با پیشوند S360_ خوانده می‌شوند (اصلاح ۳.۲.۱)
=====================================================================
"""
VERSION = "3.14.0"  # نسخهٔ بستهٔ قابل حمل — همگام با تگ ریلیز به‌روزرسانی شود
import os
import sys
import time
import shutil
import socket
import threading
import webbrowser

APP_NAME = "SmartEducation"
PREFERRED_PORT = 8093  # آدرس رسمی سامانه: http://192.168.100.4:8093/
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


def _load_env_file() -> None:
    """خواندن .env (یا .env.txt) کنار فایل اجرایی — اصلاح v3.4.2.

    پیش‌تر مستند شده بود که «فایل .env را کنار exe بگذارید» اما اجراکننده
    هرگز آن را نمی‌خواند و کلید پایه‌یار نادیده گرفته می‌شد. حالا متغیرهای
    فایل با قاعدهٔ setdefault اعمال می‌شوند (متغیر محیطی واقعی اولویت دارد)
    و مسیرهای مدیریتی خود اجراکننده (DATABASE_URL/STORAGE_DIR) بعداً بازنویسی
    می‌شوند. فرمت: سطرهای KEY=VALUE؛ # توضیح؛ کوتیشن حذف می‌شود؛ UTF-8 با BOM."""
    base = app_base()
    for name in (".env", ".env.txt"):  # Notepad ویندوز گاهی پسوند .txt می‌گذارد
        path = os.path.join(base, name)
        if not os.path.isfile(path):
            continue
        loaded = 0
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
                        loaded += 1
            print(f"[i] تنظیمات از فایل {name} بارگذاری شد ({loaded} متغیر).")
        except OSError as exc:
            print(f"[!] خواندن {name} ناموفق بود: {exc}")
        return
    print("[i] فایل .env کنار برنامه یافت نشد — کلید اتصال پایه‌یار را می‌توانید "
          "از داخل اپ (صفحهٔ همگام‌سازی پایه‌یار۳۶۰ ← تنظیمات و تست اتصال) ذخیره کنید.")


def prepare_environment() -> None:
    """
    پوشه‌های داده (data و exports) را کنار exe آماده می‌کند و
    متغیرهای محیطی برنامه را تنظیم می‌کند.
    """
    _load_env_file()
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


def _s360_guard() -> None:
    """راه‌اندازی محافظت‌شده (v3.4.2) — هیچ خروج بی‌صدایی.

    گزارش کاربر v3.4.1: بعد از بنر، برنامه بی‌صدا بسته می‌شد. اکنون هر استثنا
    چاپ و در crash.log کنار برنامه ثبت می‌شود و پنجره تا Enter باز می‌ماند؛
    اشغال بودن پورت 8093 هم پیش از راه‌اندازی با پیام واضح گزارش می‌شود."""
    import faulthandler
    import socket
    import time as _time
    import traceback as _tb

    try:
        faulthandler.enable()
    except Exception:
        pass
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    def _app_dir() -> str:
        try:
            return app_base()
        except Exception:
            return os.path.dirname(os.path.abspath(
                sys.executable if getattr(sys, "frozen", False) else __file__))

    def _dump(kind: str, exc: BaseException | None = None) -> None:
        log_path = os.path.join(_app_dir(), "crash.log")
        text = (_tb.format_exception(type(exc), exc, exc.__traceback__)
                if exc is not None else _tb.format_exc())
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(f"\n===== {_time.strftime('%Y-%m-%d %H:%M:%S')} — {kind} =====\n")
                fh.write("".join(text))
        except Exception:
            pass
        print(f"\n[!] خطای جدی ({kind}) رخ داد — جزئیات در {log_path}", flush=True)
        print("".join(text), flush=True)
        try:
            input("\n[?] برای بستن این پنجره Enter را بزنید… ")
        except Exception:
            pass

    sys.excepthook = lambda t, v, b: _dump("خطای پردازش", v)

    def _thread_hook(args) -> None:
        if args.exc_type in (SystemExit, KeyboardInterrupt):
            return
        _dump("خطای رشتهٔ پس‌زمینه", args.exc_value)
    threading.excepthook = _thread_hook

    # هشدار پورت اشغال — پیش از راه‌اندازی سرور (مظنون اصلی «بعد از بنر می‌میرد»)
    try:
        _probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _probe.bind(("127.0.0.1", 8093))
        _probe.close()
    except OSError:
        print("\n[!] هشدار: پورت 8093 اشغال است — به احتمال زیاد نمونهٔ دیگری از برنامه همین حالا در حال اجراست.", flush=True)
        print("    همهٔ پنجره‌های SmartEducation را ببندید و در Task Manager نیز SmartEducation.exe را End Task کنید،", flush=True)
        print("    سپس برنامه را دوباره اجرا کنید. اگر باز هم اجرا نشد، فایل crash.log کنار برنامه را گزارش دهید.", flush=True)

    try:
        main()
    except KeyboardInterrupt:
        print("\n[i] برنامه با Ctrl+C بسته شد.", flush=True)
    except SystemExit:
        raise
    except BaseException as exc:
        _dump("راه‌اندازی", exc)
    else:
        print("\n[i] سرور متوقف شد — برای اجرای دوباره، همین برنامه را باز کنید.", flush=True)


if __name__ == "__main__":
    _s360_guard()
