# -*- coding: utf-8 -*-
"""
=====================================================================
Integration Router — رد و بدل سرویس بین سامانه‌ها
=====================================================================
این روتر پل ارتباطی «سامانه آموزش هوشمند» با «سامانه برنامه‌ریزی
درسی» (university-scheduler) است:

    GET  /api/integration/scheduler/status   → سلامت و آدرس سرویس
    GET  /api/integration/scheduler/courses  → نمایش زندهٔ دروس سرویس
    POST /api/integration/scheduler/sync     → همگام‌سازی دروس در DB محلی

همگام‌سازی: دروس خوانده‌شده از سرویس بیرونی به‌صورت Upsert در جدول
courses ذخیره می‌شوند (بر اساس عنوان درس). اگر درس قبلاً آمده باشد
فقط توضیحات به‌روز می‌شود؛ در غیر این صورت درس جدید ساخته می‌شود.
=====================================================================
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Course
from ..services.scheduler_client import SchedulerClient

# FastAPI به Depends نیاز دارد؛ import برای سازگاری با نسخه‌های بعدی
from fastapi import Depends  # noqa: F401

router = APIRouter(
    prefix="/integration",
    tags=["integration"],
)


def _sync_courses(db: Session, courses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Upsert دروس نرمال‌شدهٔ سرویس بیرونی در دیتابیس محلی."""
    created, updated, skipped = 0, 0, 0

    for item in courses:
        title = (item.get("title") or "").strip()
        if not title:
            skipped += 1
            continue

        existing = (
            db.query(Course)
            .filter(Course.title == title)
            .first()
        )

        if existing is None:
            db.add(
                Course(
                    title=title,
                    description=item.get("description"),
                    is_active=bool(item.get("is_active", True)),
                )
            )
            created += 1
        else:
            changed = False
            if item.get("description") and item["description"] != existing.description:
                existing.description = item["description"]
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return {
            "ok": False,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "message": "خطای دیتابیس هنگام ذخیره‌سازی؛ همگام‌سازی ناتمام ماند.",
        }

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "message": (
            f"همگام‌سازی انجام شد: {created} درس جدید، "
            f"{updated} به‌روزرسانی، {skipped} بدون تغییر."
        ),
    }


# ------------------------------------------------------------------
# سلامت سرویس بیرونی
# ------------------------------------------------------------------
@router.get("/scheduler/status")
def scheduler_status() -> Dict[str, Any]:
    """بررسی در دسترس بودن سرویس برنامه‌ریزی درسی."""
    client = SchedulerClient()
    status = client.health()
    unique = client.fetch_unique_courses() if status["available"] else None
    offered = client.fetch_offered_courses() if status["available"] else None

    return {
        **status,
        "unique_courses_count": len(unique) if unique is not None else 0,
        "offered_courses_count": len(offered) if offered is not None else 0,
        "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


# ------------------------------------------------------------------
# نمایش زندهٔ دروس سرویس بیرونی (بدون ذخیره)
# ------------------------------------------------------------------
@router.get("/scheduler/courses")
def scheduler_courses() -> Dict[str, Any]:
    """دروس خوانده‌شدهٔ زنده از سرویس برنامه‌ریزی درسی."""
    client = SchedulerClient()
    health = client.health()
    unique = client.fetch_unique_courses() or []
    offered = client.fetch_offered_courses() or []

    normalized = [SchedulerClient.normalize_course(c) for c in unique]

    return {
        "available": health["available"],
        "base_url": health["base_url"],
        "detail": health["detail"],
        "unique_courses": normalized,
        "offered_courses": offered,
        "total_unique": len(normalized),
        "total_offered": len(offered),
    }


# ------------------------------------------------------------------
# همگام‌سازی دروس سرویس بیرونی → دیتابیس محلی
# ------------------------------------------------------------------
@router.post("/scheduler/sync")
def scheduler_sync(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    لیست درس‌ها را از سرویس برنامه‌ریزی درسی می‌خواند و در دیتابیس
    محلی همگام می‌کند (Upsert بر اساس عنوان درس).
    """
    client = SchedulerClient()
    health = client.health()

    if not health["available"]:
        return {
            "ok": False,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "message": (
                "سرویس برنامه‌ریزی درسی در دسترس نیست. "
                f"آدرس: {health['base_url']} — ({health['detail']})"
            ),
        }

    raw_courses = client.fetch_unique_courses() or []
    if not raw_courses:
        return {
            "ok": False,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "message": "سرویس در دسترس است اما فهرست درسی برگرداند نشد.",
        }

    normalized = [SchedulerClient.normalize_course(c) for c in raw_courses]
    result = _sync_courses(db, normalized)

    return {**result, "fetched": len(normalized), "base_url": health["base_url"]}
