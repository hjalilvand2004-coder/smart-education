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

# فونت‌ها و صفحهٔ استودیو گزارش‌ها داخل پکیج app
datas.append(
    (os.path.join(BACKEND_DIR, "app", "reports", "fonts"),
     os.path.join("app", "reports", "fonts"))
)
datas.append(
    (os.path.join(BACKEND_DIR, "app", "static"),
     os.path.join("app", "static"))
)

hiddenimports = (
    [
        # --- پکیج برنامه ---
        "app",
        "app.main",
        "app.config",
        "app.database",
        "app.models",
        "app.schemas",
        "app.crud",
        "app.ai_service",
        "app.routers",
        "app.routers.content",
        "app.routers.courses",
        "app.routers.quizzes",
        "app.routers.ai",
        "app.routers.ai_stats",
        "app.routers.upload",
        "app.routers.reports",
        "app.routers.integration",
        "app.services",
        "app.services.scheduler_client",
        "app.reports",
        "app.reports.builder",
        "app.reports.theme",
        "app.reports.html_report",
        "app.reports.pptx_report",
        "app.reports.pdf_report",
        "app.reports.docx_report",

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
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SmartEducation",
)
