import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import content, courses, integration, quizzes, ai_stats, reports
from app.routers import upload  # اضافه کنید
from fastapi.staticfiles import StaticFiles  # برای سرویس‌دهی فایل‌های استاتیک

# ایجاد جدول‌ها در اجرای اولیه.
Base.metadata.create_all(bind=engine)

APP_VERSION = "2.2.0"

app = FastAPI(
    title="سامانه هوشمند آموزش و آزمون",
    version=APP_VERSION,
    description=(
        "Backend سامانه تولید محتوای آموزشی، آزمون چهارگزینه‌ای "
        "و آزمون تشریحی — با گزارش‌سازی چهارفرمتی "
        "(HTML / PowerPoint / PDF / Word) و یکپارچگی سرویس برنامه‌ریزی درسی."
    ),
)

# اضافه کردن روت آپلود
app.include_router(upload.router, prefix="/api")

# برای دسترسی به تصاویر آپلود شده (سرویس‌دهی فایل‌های استاتیک)
if not os.path.isdir("uploads"):
    os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# صفحهٔ «استودیو گزارش‌ها» (فارسی، بدون نیاز به فرانت‌اند)
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
REPORTS_PAGE = os.path.join(_STATIC_DIR, "reports.html")


@app.get("/reports-page", include_in_schema=False)
def reports_page():
    if os.path.exists(REPORTS_PAGE):
        return FileResponse(REPORTS_PAGE, media_type="text/html; charset=utf-8")
    return {"detail": "reports page not found"}


# CORS برای Frontend مبتنی بر Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8100",
        "http://127.0.0.1:8100",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# تمام APIها با /api شروع می‌شوند.
app.include_router(courses.router, prefix="/api")
app.include_router(content.router, prefix="/api")
app.include_router(quizzes.router, prefix="/api")
app.include_router(ai_stats.router, prefix="/api")  # اضافه شد
app.include_router(reports.router, prefix="/api")        # گزارش‌سازی ۴ فرمتی
app.include_router(integration.router, prefix="/api")    # اتصال به scheduler


@app.get("/", tags=["System"])
def root():
    return {
        "message": "Smart Education API is running",
        "version": APP_VERSION,
        "docs_url": "/docs",
        "api_prefix": "/api",
        "reports_page": "/reports-page",
        "exports": ["/api/reports/export/html", "/api/reports/export/pptx",
                    "/api/reports/export/pdf", "/api/reports/export/docx"],
    }


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "message": "Backend is healthy", "version": APP_VERSION}


# ------------------------------------------------------------------
# سرویس‌دهی رابط کاربری ساخته‌شده (frontend/dist) در حالت پرتابل
# اگر متغیر محیطی FRONTEND_DIST_DIR تنظیم شده باشد، UI روی همین
# پورت سرو می‌شود و نیازی به Node.js نیست.
# ------------------------------------------------------------------
_FE_DIST = os.environ.get("FRONTEND_DIST_DIR", "")
if _FE_DIST and os.path.isdir(os.path.join(_FE_DIST, "assets")):
    app.mount("/", StaticFiles(directory=_FE_DIST, html=True), name="frontend")
