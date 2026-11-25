"""نقطه ورود FastAPI — مونولیت ماژولار (بخش ۱۰).

میان‌افزارها: Request-ID، CORS، محدودسازی نرخ ورود.
مدیریت خطای استاندارد با request_id برای ردیابی.
"""
import logging
import sys
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.bootstrap import ensure_schema_and_demo
from app.core.config import get_settings
from app.core.errors import AppError, request_id_var

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("student360")

API_PREFIX = "/api/v1"

# ---------- یکپارچگی کامل پایه‌یار۳۶۰ (سند فنی v3.4.0) ----------
# زمان‌بند همگام‌سازی (cron 0 */30 * * * * → هر ۳۰ دقیقه) و مصرف‌کننده رویدادهای
# RabbitMQ — هر دو فقط با فعال بودن تنظیم مربوطه بالا می‌آیند و خاموشی‌شان هرگز
# مانع سرویس اصلی نمی‌شود.
_payehyar_tasks: list = []


async def _payehyar_lifespan(app):
    import asyncio

    from app.services import payehyar_events, payehyar_scheduler

    if get_settings().payehyar_auto_sync:
        _payehyar_tasks.append(asyncio.create_task(payehyar_scheduler.scheduler_loop()))
        logger.info("payehyar auto-sync scheduler started")
    if get_settings().payehyar_events_enabled:
        _payehyar_tasks.append(asyncio.create_task(payehyar_events.consume_forever()))
        logger.info("payehyar events consumer started")
    yield
    for task in _payehyar_tasks:
        task.cancel()


def _resolve_frontend_dist(frontend_dist_setting: str = ""):
    """یافتن مسیر build فرانت‌اند در همهٔ حالت‌ها: توسعه، متغیر محیطی صریح و بستهٔ پرتیبل.

    ریشهٔ باگ ۴۰۴ نسخهٔ پرتیبل ۳.۲.۰: لانچر exe متغیر FRONTEND_DIST_DIR را
    ست می‌کرد در حالی که اپ فقط S360_FRONTEND_DIST می‌خواند، و مسیر جایگزین
    توسعه‌ای (parents[2]/frontend/dist) در چیدمان بستهٔ PyInstaller وجود ندارد
    (داده‌ها زیر «_internal» قرار می‌گیرند). این تابع مستقل از لانچر، همهٔ
    چیدمان‌های ممکن را به‌ترتیب امتحان می‌کند (دفاع در عمق).
    """
    from pathlib import Path as _Path

    candidates: list = []
    if frontend_dist_setting:
        candidates.append(_Path(frontend_dist_setting))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(_Path(meipass) / "frontend_dist")
    if getattr(sys, "frozen", False):
        exe_dir = _Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "_internal" / "frontend_dist")
        candidates.append(exe_dir / "frontend_dist")
    candidates.append(_Path(__file__).resolve().parents[2] / "frontend" / "dist")
    for cand in candidates:
        if (cand / "index.html").is_file():
            return cand
    return None


def create_app() -> FastAPI:
    settings = get_settings()
    # بوت‌استرپ دیتابیس برای نسخهٔ پرتیبل (رفع «no such table: users» در ۳.۲.۱):
    # دیتابیس SQLite خالی → ساخت جدول‌ها + دادهٔ نمونهٔ دمو؛ بقیه حالت‌ها دست‌نخورده.
    ensure_schema_and_demo()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "سامانه سرویس‌های یادگیری هوشمند دانشجو۳۶۰ — استودیوی تولید محتوای استاد، "
            "بانک سؤال، ارزیابی، تحلیل تسلط، برنامه مطالعه و استاد هوشمند گفتگو‌محور"
        ),
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_payehyar_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        t0 = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        logger.info("%s %s -> %s (%.0fms)", request.method, request.url.path,
                    response.status_code, (time.monotonic() - t0) * 1000)
        return response

    def error_response(status_code: int, code: str, message: str, details: dict | None = None):
        return JSONResponse(status_code=status_code, content={
            "error": {"code": code, "message": message,
                      "details": details or {},
                      "request_id": request_id_var.get()},
        })

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return error_response(422, "VALIDATION_ERROR", "داده ورودی نامعتبر است",
                              {"errors": exc.errors()[:10]})

    @app.exception_handler(Exception)
    async def internal_handler(request: Request, exc: Exception):
        logger.exception("unhandled error on %s", request.url.path)
        return error_response(500, "INTERNAL", "خطای داخلی سرور؛ با پشتیبانی در تماس باشید")

    from app.api.v1 import (assessments, auth, collaboration, content, courses,
                            exports, learning, ops, planning, questions, syllabus,
                            tutor)

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(auth.me_router, prefix=API_PREFIX)
    app.include_router(courses.router, prefix=API_PREFIX)
    app.include_router(syllabus.router, prefix=API_PREFIX)
    app.include_router(content.router, prefix=API_PREFIX)
    app.include_router(exports.router, prefix=API_PREFIX)
    app.include_router(questions.router, prefix=API_PREFIX)
    app.include_router(assessments.router, prefix=API_PREFIX)
    app.include_router(learning.router, prefix=API_PREFIX)
    app.include_router(planning.router, prefix=API_PREFIX)
    app.include_router(tutor.router, prefix=API_PREFIX)
    app.include_router(collaboration.router, prefix=API_PREFIX)
    app.include_router(ops.router, prefix=API_PREFIX)
    from app.api.v1 import integration
    from app.api.v1 import masterdata
    app.include_router(integration.router, prefix=API_PREFIX)
    app.include_router(masterdata.router, prefix=API_PREFIX)
    from app.api.v1 import users_admin, reports, services_ext, ai_stats
    app.include_router(users_admin.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)
    app.include_router(services_ext.router, prefix=API_PREFIX)
    app.include_router(ai_stats.router, prefix=API_PREFIX)
    from app.api.v1 import smart
    app.include_router(smart.router, prefix=API_PREFIX)
    from app.api.v1 import journey
    app.include_router(journey.router, prefix=API_PREFIX)

    @app.get("/healthz", tags=["ops"])
    def health():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    # نسخه پرتیبل: serve فرانت‌اند build‌شده + fallback SPA (بدون نیاز به nginx)
    dist = _resolve_frontend_dist(settings.frontend_dist)
    if dist is not None:
        from fastapi.responses import FileResponse

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={
                    "error": {"code": "NOT_FOUND", "message": "مسیر API یافت نشد",
                              "details": {}, "request_id": request_id_var.get()}})
            target = (dist / full_path).resolve()
            if full_path and str(target).startswith(str(dist)) and target.is_file():
                return FileResponse(target)
            return FileResponse(dist / "index.html")
        logger.info("serving frontend dist from %s", dist)
    else:
        logger.info("frontend dist not found — API-only mode")

    return app


app = create_app()
