"""سرویس‌دهی سرفصل‌ها و محتوا به سایر سامانه‌ها (مثل برنامه‌یار۳۶۰ و تحصیل‌یار۳۶۰).

اگر S360_SERVICE_TOKEN تنظیم شده باشد، همه مسیرها هدر X-Service-Token را می‌خواهند؛
در غیر این صورت سرویس فقط‌خواندنی و باز است (داخل شبکه دانشگاه).
"""
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db, utcnow
from app.core.errors import forbidden, not_found
from app.models.content import ContentDocument, ContentVersion
from app.models.courses import Course
from app.models.syllabus import LearningObjective, SyllabusTopic, SyllabusVersion

router = APIRouter(prefix="/services", tags=["services"])


def _service_guard(x_service_token: str | None = Header(default=None)):
    s = get_settings()
    if s.service_token and x_service_token != s.service_token:
        raise forbidden("توکن سرویس نامعتبر است")


def _active_version(db: Session, course_id):
    return (
        db.query(SyllabusVersion)
        .filter(SyllabusVersion.course_id == course_id,
                SyllabusVersion.status.in_(("APPROVED", "DRAFT", "PENDING_REVIEW")))
        .order_by(SyllabusVersion.version_number.desc())
        .first()
    )


@router.get("/health")
def service_health(db: Session = Depends(get_db), _g=Depends(_service_guard)):
    return {
        "status": "ok",
        "service": "student360-learning-services",
        "version": get_settings().app_version,
        "time": utcnow().isoformat(),
        "courses": db.query(Course).count(),
    }


@router.get("/courses")
def service_courses(db: Session = Depends(get_db), _g=Depends(_service_guard)):
    """فهرست درس‌ها + وضعیت سرفصل، برای سامانه‌های دیگر."""
    out = []
    for c in db.query(Course).order_by(Course.code).all():
        sv = _active_version(db, c.id)
        out.append({
            "id": str(c.id), "code": c.code, "title": c.title,
            "department": c.department, "credits": c.credits, "term": c.term,
            "syllabus_version_id": str(sv.id) if sv else None,
            "syllabus_status": sv.status if sv else None,
        })
    return {"items": out, "total": len(out)}


def _topic_row(db: Session, t: SyllabusTopic, sv: SyllabusVersion, course: Course) -> dict:
    return {
        "topic_id": str(t.id), "title": t.title, "kind": t.kind,
        "description": t.description, "suggested_hours": t.suggested_hours,
        "order": t.order_index, "needs_review": t.needs_review,
        "course_id": str(course.id), "course_code": course.code,
        "course_title": course.title,
        "syllabus_version_id": str(sv.id), "syllabus_status": sv.status,
    }


@router.get("/topics")
def service_topics(course_code: str | None = None, q: str | None = None,
                   limit: int = 500, db: Session = Depends(get_db), _g=Depends(_service_guard)):
    """سرفصل‌های درس‌ها — قابل فیلتر با کد درس یا جستجوی عنوان."""
    query = (
        db.query(SyllabusTopic, SyllabusVersion, Course)
        .join(SyllabusVersion, SyllabusTopic.syllabus_version_id == SyllabusVersion.id)
        .join(Course, SyllabusVersion.course_id == Course.id)
        .order_by(Course.code, SyllabusTopic.order_index)
    )
    if course_code:
        query = query.filter(Course.code == course_code)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(SyllabusTopic.title.like(like))
    rows = query.limit(max(1, min(limit, 1000))).all()
    return {"items": [_topic_row(db, t, sv, c) for t, sv, c in rows], "total": len(rows)}


@router.get("/topics/{topic_id}")
def service_topic_detail(topic_id: str, db: Session = Depends(get_db), _g=Depends(_service_guard)):
    t = db.get(SyllabusTopic, topic_id)
    if t is None:
        raise not_found("سرفصل یافت نشد")
    sv = db.get(SyllabusVersion, t.syllabus_version_id)
    course = db.get(Course, sv.course_id)
    objectives = db.query(LearningObjective).filter(
        LearningObjective.syllabus_version_id == sv.id).order_by(LearningObjective.code).all()
    row = _topic_row(db, t, sv, course)
    row["objectives"] = [
        {"code": o.code, "statement": o.statement,
         "topic_id": str(o.topic_id) if o.topic_id else None}
        for o in objectives
    ]
    return row


@router.get("/topics/{topic_id}/content")
def service_topic_content(topic_id: str, include_blocks: bool = True,
                          db: Session = Depends(get_db), _g=Depends(_service_guard)):
    """محتوای منتشرشده مرتبط با یک سرفصل (سند‌هایی که scope آن‌ها شامل topic است)."""
    t = db.get(SyllabusTopic, topic_id)
    if t is None:
        raise not_found("سرفصل یافت نشد")
    sv = db.get(SyllabusVersion, t.syllabus_version_id)
    docs = db.query(ContentDocument).filter(ContentDocument.course_id == sv.course_id).all()
    items = []
    for d in docs:
        scope = d.scope or {}
        if topic_id not in [str(x) for x in (scope.get("topic_ids") or [])]:
            continue
        v = (
            db.query(ContentVersion)
            .filter(ContentVersion.document_id == d.id, ContentVersion.status == "PUBLISHED")
            .order_by(ContentVersion.version_number.desc())
            .first()
        )
        if v is None:
            continue
        items.append({
            "document_id": str(d.id), "title": d.title,
            "version_id": str(v.id), "version_number": v.version_number,
            "published_at": v.published_at.isoformat() if v.published_at else None,
            "blocks": (v.blocks or []) if include_blocks else None,
        })
    return {"topic_id": topic_id, "topic_title": t.title, "items": items, "total": len(items)}


@router.get("/export/topics")
def service_export_topics(db: Session = Depends(get_db), _g=Depends(_service_guard)):
    """بسته کامل سرفصل‌ها و اهداف برای مهاجرت/همگام‌سازی سایر سامانه‌ها."""
    course_rows = []
    topics_all = []
    objectives_all = []
    for c in db.query(Course).order_by(Course.code).all():
        sv = _active_version(db, c.id)
        course_rows.append({"id": str(c.id), "code": c.code, "title": c.title,
                            "department": c.department, "credits": c.credits})
        if sv is None:
            continue
        for t in db.query(SyllabusTopic) \
                .filter(SyllabusTopic.syllabus_version_id == sv.id) \
                .order_by(SyllabusTopic.order_index).all():
            topics_all.append(_topic_row(db, t, sv, c))
        for o in db.query(LearningObjective) \
                .filter(LearningObjective.syllabus_version_id == sv.id) \
                .order_by(LearningObjective.code).all():
            objectives_all.append({
                "code": o.code, "statement": o.statement,
                "topic_id": str(o.topic_id) if o.topic_id else None,
                "course_code": c.code,
            })
    return {
        "generated_at": utcnow().isoformat(),
        "courses": course_rows,
        "topics": topics_all,
        "objectives": objectives_all,
    }
