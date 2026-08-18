from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import content, courses, quizzes, ai_stats
from app.routers import upload  # اضافه کنید
from fastapi.staticfiles import StaticFiles  # برای سرویس‌دهی فایل‌های استاتیک



# ایجاد جدول‌ها در اجرای اولیه.
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="سامانه هوشمند آموزش و آزمون",
    version="2.1.0",
    description=(
        "Backend سامانه تولید محتوای آموزشی، آزمون چهارگزینه‌ای "
        "و آزمون تشریحی."
    ),
)

# اضافه کردن روت آپلود
app.include_router(upload.router, prefix="/api")

# برای دسترسی به تصاویر آپلود شده (سرویس‌دهی فایل‌های استاتیک)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
# CORS برای Frontend مبتنی بر Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
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


@app.get("/", tags=["System"])
def root():
    return {
        "message": "Smart Education API is running",
        "version": "2.1.0",
        "docs_url": "/docs",
        "api_prefix": "/api",
    }


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "message": "Backend is healthy"}