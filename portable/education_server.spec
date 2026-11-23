# -*- mode: python ; coding: utf-8 -*-
r"""
=====================================================================
 PyInstaller Spec — نسخهٔ قابل حمل سامانه هوشمند آموزش
=====================================================================
 ساخت روی ویندوز (GitHub Actions):
     cd backend
     pyinstaller ..\portable\education_server.spec --noconfirm --clean

 خروجی:
     backend/dist/SmartEducation/  →  کل پوشهٔ قابل حمل
=====================================================================
"""
import os
import sys

SPEC_DIR = SPECPATH                            # پوشه portable/
REPO_ROOT = os.path.dirname(SPEC_DIR)          # ریشه مخزن
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")

# پوشه backend باید روی sys.path باشد تا پکیج app تحلیل شود
sys.path.insert(0, BACKEND_DIR)

FE_DIST = os.path.join(BACKEND_DIR, "frontend_dist")
SEED_DB = os.path.join(BACKEND_DIR, "education.db")

datas = []
if os.path.isdir(FE_DIST):
    datas.append((FE_DIST, "frontend_dist"))
else:
    raise SystemExit(
        f"[!] پوشه {FE_DIST} پیدا نشد.\n"
        "    ابتدا فرانت‌اند را بسازید و dist را به backend/frontend_dist "
        "کپی کنید (در GitHub Actions به‌صورت خودکار انجام می‌شود)."
    )
if os.path.exists(SEED_DB):
    datas.append((SEED_DB, "."))

# فونت‌های فارسی داخل پکیج app — مبنای FONTS_DIR در app/services/export_service.py
# مسیر واقعی: backend/app/assets/fonts (نسخهٔ قدیمی app/reports/fonts دیگر وجود ندارد)
ASSETS_DIR = os.path.join(BACKEND_DIR, "app", "assets")
if os.path.isdir(ASSETS_DIR):
    datas.append((ASSETS_DIR, os.path.join("app", "assets")))

# کشف خودکار همهٔ زیرماژول‌های پکیج app از روی سیستم فایل —
# مقاوم به تغییر ساختار (سیاههٔ ثابتِ قدیمی به معماری حاضر نمی‌خورد)
app_pkg_dir = os.path.join(BACKEND_DIR, "app")
app_modules = ["app", "app.main"]
for _root, _dirs, _files in os.walk(app_pkg_dir):
    _dirs[:] = [d for d in _dirs if d != "__pycache__"]
    for _f in sorted(_files):
        if _f.endswith(".py"):
            _rel = os.path.relpath(os.path.join(_root, _f), os.path.dirname(app_pkg_dir))
            app_modules.append(_rel[:-3].replace(os.sep, "."))

hiddenimports = (app_modules + [
        # --- uvicorn ---
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",

        # --- کتابخانه‌های گزارش‌سازی ---
        "pptx",
        "docx",
        "reportlab",
        "arabic_reshaper",
        "bidi",

        # --- سایر وابستگی‌های داینامیک ---
        "httpx",
        "openpyxl",
        "anyio._backends._asyncio",
        "sqlalchemy.dialects.sqlite",
    ]
)

a = Analysis(
    [os.path.join(SPEC_DIR, "education_server.py")],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # matplotlib (وابسته به numpy) به‌صورت lazy در report_builder استفاده می‌شود — نباید حذف شود
    excludes=["tkinter", "pandas"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartEducation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    # کاهش هشدارهای کاذب آنتی‌ویروس:
    #   - VERSIONINFO (نام محصول/نسخه/سازنده) و آیکون رسمی به فایل exe
    #     اضافه می‌شود تا آنتی‌ویروس آن را «برنامهٔ ناشناس» تشخیص ندهد.
    version=os.path.join(SPEC_DIR, "version_info.txt"),
    icon=os.path.join(SPEC_DIR, "smarteducation.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SmartEducation",
)
