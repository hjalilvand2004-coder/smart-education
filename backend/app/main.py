"""نقطه ورود FastAPI — مونولیت ماژولار (بخش ۱۰).

میان‌افزارها: Request-ID، CORS، محدودسازی نرخ ورود.
مدیریت خطای استاندارد با request_id برای ردیابی.
"""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.errors import AppError, request_id_var

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("student360")

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "سامانه سرویس‌های یادگیری هوشمند دانشجو۳۶۰ — استودیوی تولید محتوای استاد، "
            "بانک سؤال، ارزیابی، تحلیل تسلط، برنامه مطالعه و استاد هوشمند گفتگو‌محور"
        ),
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
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
    app.include_router(integration.router, prefix=API_PREFIX)
    from app.api.v1 import users_admin, reports, services_ext, ai_stats
    app.include_router(users_admin.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)
    app.include_router(services_ext.router, prefix=API_PREFIX)
    app.include_router(ai_stats.router, prefix=API_PREFIX)

    @app.get("/healthz", tags=["ops"])
    def health():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    # نسخه پرتیبل: serve فرانت‌اند build‌شده + fallback SPA (بدون نیاز به nginx)
    from pathlib import Path as _Path

    dist = (_Path(settings.frontend_dist) if settings.frontend_dist
            else _Path(__file__).resolve().parents[2] / "frontend" / "dist")
    if dist.exists() and (dist / "index.html").exists():
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

    return app


app = create_app()
