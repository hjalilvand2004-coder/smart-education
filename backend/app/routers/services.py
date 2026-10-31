# -*- coding: utf-8 -*-
"""
=====================================================================
Services Router — سرویس‌دهی سرفصل‌ها و محتوای درسی به سامانه‌های دیگر
=====================================================================
این روتر «سمت ارائهٔ سرویس» (Provider) سامانه هوشمند آموزش است؛
سامانه‌های دیگر (برنامه‌ریزی درسی و هر سامانهٔ دیگر) می‌توانند
سرفصل‌های دروس و محتوای آن‌ها را از این نقاط اتصال بخوانند:

    GET /api/services/health                 → شناسنامهٔ سرویس
    GET /api/services/courses                → فهرست درس‌ها
    GET /api/services/topics                 → فهرست سرفصل‌ها (فیلتر درس)
    GET /api/services/topics/{id}            → یک سرفصل + محتوای آن
    GET /api/services/topics/{id}/content    → محتوای کامل یک سرفصل
    GET /api/services/export/topics          → بستهٔ کامل سرفصل‌ها (JSON)
    POST /api/services/push/topics           → ارسال سرفصل‌ها به سامانهٔ دیگر

قرارداد دریافت (Ingest Contract) برای سامانهٔ گیرنده:
    POST {target}/api/ingest/topics
    بدنه:  {"source": "...", "generated_at": "...",
            "topics": [ {course_title, topic_title, description,
                         session_minute, sort_order,
                         contents:[{title, body, source}]} ]}
=====================================================================
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import SERVICE_BASE_URL, SERVICE_PUSH_TIMEOUT
from ..database import get_db
from ..models import Course, CourseTopic, EducationalContent

router = APIRouter(prefix="/services", tags=["services"])

APP_VERSION = "2.3.0"

# مبدأ پوش‌های خروجی — برای تشخیص در لاگ سامانهٔ گیرنده
PUSH_SOURCE_ID = "smart-education"


# ==================================================================
# مدل‌های ورودی (Request Bodies)
# ==================================================================
class PushTopicsRequest(BaseModel):
    """درخواست ارسال سرفصل‌ها به یک سامانهٔ دیگر."""

    target_base_url: str = Field(
        ...,
        description=(
            "آدرس پایهٔ سامانهٔ گیرنده؛ مثلاً http://188.212.96.235:8083 — "
            "داده‌ها به {target}/api/ingest/topics ارسال می‌شود."
        ),
    )
    course_id: Optional[int] = Field(
        None,
        description="فقط سرفصل‌های این درس ارسال شود (اختیاری).",
    )
    include_content: bool = Field(
        True,
        description="محتوای سرفصل‌ها هم ارسال شود؟",
    )
    access_token: Optional[str] = Field(
        None,
        description="توکن اختیاری که در هدر Authorization قرار می‌گیرد.",
    )


# ==================================================================
# توابع کمکی سریال‌سازی
# ==================================================================
def _serialize_topic(
    topic: CourseTopic,
    include_content: bool = False,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """تبدیل یک سرفصل به دیکشنری سازگار با سامانه‌های بیرونی."""
    data: Dict[str, Any] = {
        "topic_id": topic.id,
        "course_id": topic.course_id,
        "course_title": topic.course.title if topic.course else None,
        "topic_title": topic.title,
        "description": topic.description,
        "session_minute": topic.session_minute,
        "sort_order": topic.sort_order,
        "is_active": topic.is_active,
    }
    if include_content and db is not None:
        contents = (
            db.query(EducationalContent)
            .filter(EducationalContent.topic_id == topic.id)
            .order_by(EducationalContent.created_at.asc())
            .all()
        )
        data["contents"] = [
            {
                "content_id": c.id,
                "title": c.title,
                "body": c.body,
                "source": c.source,
                "created_at": c.created_at.isoformat(timespec="seconds"),
            }
            for c in contents
        ]
    return data


def _build_topics_bundle(
    db: Session,
    course_id: Optional[int] = None,
    include_content: bool = True,
    include_inactive: bool = False,
) -> Dict[str, Any]:
    """
    بستهٔ کامل سرفصل‌ها (و در صورت نیاز محتوا) را برای ارسال به
    سامانه‌های دیگر می‌سازد — هم برای export و هم برای push استفاده
    می‌شود تا خروجی یکسانی داشته باشند.
    """
    query = db.query(CourseTopic)
    if course_id is not None:
        query = query.filter(CourseTopic.course_id == course_id)
    if not include_inactive:
        query = query.filter(CourseTopic.is_active.is_(True))

    topics = query.order_by(
        CourseTopic.course_id.asc(), CourseTopic.sort_order.asc()
    ).all()

    items = [
        _serialize_topic(t, include_content=include_content, db=db)
        for t in topics
    ]

    course = None
    if course_id is not None:
        row = db.query(Course).filter(Course.id == course_id).first()
        course = {"id": row.id, "title": row.title} if row else None

    return {
        "source": PUSH_SOURCE_ID,
        "system": "سامانه هوشمند آموزش (Smart Education)",
        "service_base_url": SERVICE_BASE_URL,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "course": course,
        "include_content": include_content,
        "total_topics": len(items),
        "topics": items,
    }


# ==================================================================
# شناسنامهٔ سرویس (Service Card) — برای کشف سرویس توسط سامانه‌های دیگر
# ==================================================================
@router.get("/health")
def service_health() -> Dict[str, Any]:
    """
    شناسنامهٔ سرویس‌دهی این سامانه — سامانه‌های دیگر با این مسیر
    متوجه می‌شوند چه سرویسی در دسترس است.
    """
    return {
        "service": "smart-education",
        "name": "سامانه هوشمند آموزش و آزمون",
        "version": APP_VERSION,
        "base_url": SERVICE_BASE_URL,
        "capabilities": ["courses", "topics", "topic-content", "push-topics"],
        "endpoints": {
            "health": "/api/services/health",
            "courses": "/api/services/courses",
            "topics": "/api/services/topics?course_id=",
            "topic_detail": "/api/services/topics/{topic_id}",
            "topic_content": "/api/services/topics/{topic_id}/content",
            "export_all": "/api/services/export/topics",
            "ingest_contract": "POST /api/ingest/topics (سمت سامانهٔ گیرنده)",
        },
        "server_time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


# ==================================================================
# فهرست درس‌ها
# ==================================================================
@router.get("/courses")
def list_courses(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """فهرست درس‌های سامانه همراه با تعداد سرفصل و محتوا."""
    topics_count = (
        func.count(CourseTopic.id)
    )
    rows = (
        db.query(
            Course.id,
            Course.title,
            Course.description,
            Course.is_active,
            topics_count,
        )
        .outerjoin(CourseTopic, CourseTopic.course_id == Course.id)
        .group_by(Course.id)
        .order_by(Course.id.asc())
        .all()
    )

    contents_count = dict(
        db.query(CourseTopic.course_id, func.count(EducationalContent.id))
        .join(
            EducationalContent,
            EducationalContent.topic_id == CourseTopic.id,
        )
        .group_by(CourseTopic.course_id)
        .all()
    )

    courses = [
        {
            "course_id": r[0],
            "title": r[1],
            "description": r[2],
            "is_active": r[3],
            "topics_count": r[4] or 0,
            "contents_count": contents_count.get(r[0], 0),
        }
        for r in rows
    ]

    return {
        "source": PUSH_SOURCE_ID,
        "total": len(courses),
        "courses": courses,
    }


# ==================================================================
# فهرست سرفصل‌ها
# ==================================================================
@router.get("/topics")
def list_topics(
    course_id: Optional[int] = Query(None, description="فیلتر بر اساس درس"),
    include_inactive: bool = Query(False, description="سرفصل‌های غیرفعال هم؟"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """فهرست سرفصل‌های دروس (بدون متن کامل محتوا — سبک برای همگام‌سازی)."""
    query = db.query(CourseTopic)
    if course_id is not None:
        query = query.filter(CourseTopic.course_id == course_id)
    if not include_inactive:
        query = query.filter(CourseTopic.is_active.is_(True))

    total = query.count()
    topics = (
        query.order_by(CourseTopic.course_id.asc(), CourseTopic.sort_order.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # تعداد محتوای هر سرفصل در یک کوئری
    content_counts: Dict[int, int] = dict(
        db.query(
            EducationalContent.topic_id,
            func.count(EducationalContent.id),
        )
        .group_by(EducationalContent.topic_id)
        .all()
    )

    items = []
    for t in topics:
        d = _serialize_topic(t)
        d["contents_count"] = content_counts.get(t.id, 0)
        d["content_url"] = f"/api/services/topics/{t.id}/content"
        items.append(d)

    return {
        "source": PUSH_SOURCE_ID,
        "total": total,
        "limit": limit,
        "offset": offset,
        "topics": items,
    }


# ==================================================================
# جزئیات یک سرفصل
# ==================================================================
@router.get("/topics/{topic_id}")
def topic_detail(
    topic_id: int,
    include_content: bool = Query(True, description="محتوا همراه باشد؟"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """یک سرفصل مشخص همراه با محتوای آموزشی آن."""
    topic = db.query(CourseTopic).filter(CourseTopic.id == topic_id).first()
    if topic is None:
        raise HTTPException(status_code=404, detail="سرفصل یافت نشد.")

    data = _serialize_topic(topic, include_content=include_content, db=db)
    data["contents_count"] = len(data.get("contents") or [])
    return data


# ==================================================================
# محتوای کامل یک سرفصل
# ==================================================================
@router.get("/topics/{topic_id}/content")
def topic_content(
    topic_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """تمام محتوای آموزشی تولیدشده برای یک سرفصل (متن کامل)."""
    topic = db.query(CourseTopic).filter(CourseTopic.id == topic_id).first()
    if topic is None:
        raise HTTPException(status_code=404, detail="سرفصل یافت نشد.")

    contents = (
        db.query(EducationalContent)
        .filter(EducationalContent.topic_id == topic_id)
        .order_by(EducationalContent.created_at.asc())
        .all()
    )

    return {
        "source": PUSH_SOURCE_ID,
        "topic_id": topic.id,
        "course_id": topic.course_id,
        "course_title": topic.course.title if topic.course else None,
        "topic_title": topic.title,
        "description": topic.description,
        "session_minute": topic.session_minute,
        "total_contents": len(contents),
        "contents": [
            {
                "content_id": c.id,
                "title": c.title,
                "body": c.body,
                "source": c.source,
                "created_at": c.created_at.isoformat(timespec="seconds"),
            }
            for c in contents
        ],
    }


# ==================================================================
# بستهٔ کامل — برای همگام‌سازی یک‌جا در سامانه‌های دیگر
# ==================================================================
@router.get("/export/topics")
def export_topics(
    course_id: Optional[int] = Query(None, description="فیلتر بر اساس درس"),
    include_content: bool = Query(True),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    بستهٔ کامل JSON سرفصل‌ها (و محتوا) — مناسب برای فراخوانی یک‌باره
    توسط سامانهٔ برنامه‌ریزی درسی و سایر سامانه‌ها.
    """
    return _build_topics_bundle(
        db,
        course_id=course_id,
        include_content=include_content,
        include_inactive=include_inactive,
    )


# ==================================================================
# ارسال (Push) سرفصل‌ها به یک سامانهٔ دیگر
# ==================================================================
@router.post("/push/topics")
def push_topics(
    payload: PushTopicsRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    سرفصل‌ها (و در صورت نیاز محتوا) به‌صورت JSON به سامانهٔ گیرنده
    ارسال می‌شود:

        POST {target_base_url}/api/ingest/topics

    سامانهٔ گیرنده (برنامه‌ریزی درسی یا هر سامانهٔ دیگر) باید این مسیر
    را طبق قرارداد Ingest پیاده‌سازی کرده باشد.
    """
    target = (payload.target_base_url or "").strip().rstrip("/")
    if not target.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=422,
            detail="آدرس سامانهٔ گیرنده باید با http:// یا https:// شروع شود.",
        )

    bundle = _build_topics_bundle(
        db,
        course_id=payload.course_id,
        include_content=payload.include_content,
        include_inactive=False,
    )

    if bundle["total_topics"] == 0:
        return {
            "ok": False,
            "target": target,
            "delivered_topics": 0,
            "message": "سرفولی برای ارسال وجود ندارد (ابتدا سرفصل بسازید یا درس انتخاب کنید).",
        }

    ingest_url = f"{target}/api/ingest/topics"
    headers = {
        "Content-Type": "application/json",
        "X-Source-System": PUSH_SOURCE_ID,
        "User-Agent": f"{PUSH_SOURCE_ID}/{APP_VERSION}",
    }
    if payload.access_token:
        headers["Authorization"] = f"Bearer {payload.access_token}"

    try:
        resp = httpx.post(
            ingest_url,
            json=bundle,
            headers=headers,
            timeout=SERVICE_PUSH_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "target": target,
            "ingest_url": ingest_url,
            "delivered_topics": 0,
            "message": f"ارسال ناموفق بود: {exc.__class__.__name__}",
        }

    ok = 200 <= resp.status_code < 300
    return {
        "ok": ok,
        "target": target,
        "ingest_url": ingest_url,
        "status_code": resp.status_code,
        "delivered_topics": bundle["total_topics"],
        "included_content": payload.include_content,
        "response_preview": resp.text[:500] if resp.text else "",
        "message": (
            f"ارسال موفق: {bundle['total_topics']} سرفصل به {ingest_url}"
            if ok
            else f"سامانهٔ گیرنده کد {resp.status_code} برگرداند."
        ),
    }
