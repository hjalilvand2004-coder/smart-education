"""یکپارچه‌سازی با سامانه «برنامه‌یار۳۶۰»: واکشی درس‌های یکتا و ورود به دانشجو۳۶۰.

جریان: واکشی → فرم اطلاعات درس → ثبت سرفصل‌ها (موضوع‌ها) → ساخت درس + نسخه سرفصل
تا استودیوی محتوا بتواند برای هر سرفصل به‌صورت جداگانه محتوا تولید کند.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import conflict, forbidden
from app.core.security import get_current_user
from app.models.courses import Course
from app.models.identity import CourseRole, User
from app.models.syllabus import SyllabusTopic, SyllabusVersion
from app.core.audit import audit
from app.services.programyar import DEFAULT_BASE_URL, ProgramyarClient

router = APIRouter(tags=["integration"])

STAFF_GLOBAL_ROLES = ("PROFESSOR", "ASSISTANT", "GROUP_ADMIN",
                      "EDUCATION_ADMIN", "TECH_ADMIN", "QUALITY_REVIEWER")


def _ensure_staff_user(user: User) -> None:
    if user.role not in STAFF_GLOBAL_ROLES:
        raise forbidden("این بخش فقط برای اساتید و کارکنان آموزشی فعال است")


@router.get("/integration/programyar/status")
def programyar_status(user: User = Depends(get_current_user)):
    """وضعیت اتصال به برنامه‌یار۳۶۰ (بدون لاگین به مقصد)."""
    import httpx

    s = get_settings()
    base = (s.programyar_base_url or DEFAULT_BASE_URL).rstrip("/")
    reachable, auth_required = False, False
    try:
        with httpx.Client(base_url=base, timeout=8.0) as client:
            resp = client.get("/api/courses/unique")
            reachable = True
            auth_required = resp.status_code in (401, 403) or "وارد شوید" in resp.text
    except httpx.HTTPError:
        reachable = False
    return {
        "base_url": base,
        "reachable": reachable,
        "auth_required": auth_required,
        "credentials_configured": bool(s.programyar_username and s.programyar_password),
        "message": ("برنامه‌یار۳۶۰ در دسترس است" if reachable
                    else "اتصال به برنامه‌یار۳۶۰ برقرار نشد؛ آدرس/شبکه را بررسی کنید."),
    }


class FetchIn(BaseModel):
    username: str | None = None
    password: str | None = None
    base_url: str | None = None


@router.post("/integration/programyar/courses")
def fetch_programyar_courses(body: FetchIn | None = None, user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """واکشی «درس‌های یکتا» از برنامه‌یار۳۶۰ برای انتخاب و ورود به دانشجو۳۶۰."""
    _ensure_staff_user(user)
    b = body or FetchIn()
    client = ProgramyarClient(base_url=b.base_url)
    result = client.get_unique_courses(b.username, b.password)
    existing = {c.code for c in db.query(Course).all()}
    for item in result.get("items", []):
        item["already_imported"] = bool(item.get("code")) and item["code"] in existing
    return result


class TopicIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    description: str | None = None
    suggested_hours: float | None = None
    needs_review: bool = False


class ImportCourseIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=2, max_length=200)
    department: str | None = None
    degree_level: str | None = None
    field_of_study: str | None = None
    credits: int | None = None
    term: str | None = None
    description: str | None = None
    prerequisites_note: str | None = None
    source_ref: str | None = None  # شناسه رکورد در برنامه‌یار۳۶۰
    topics: list[TopicIn] = []


@router.post("/integration/programyar/import")
def import_course_from_programyar(body: ImportCourseIn, db: Session = Depends(get_db),
                                  user: User = Depends(get_current_user)):
    """ثبت درس واکشی‌شده + فرم اطلاعات + سرفصل‌ها در دانشجو۳۶۰."""
    _ensure_staff_user(user)
    if db.query(Course).filter(Course.code == body.code).first() is not None:
        raise conflict("درسی با همین کد از قبل در دانشجو۳۶۰ ثبت شده است")

    course = Course(
        code=body.code, title=body.title, department=body.department,
        degree_level=body.degree_level, field_of_study=body.field_of_study,
        credits=body.credits, term=body.term, created_by=user.id,
        description=(body.description or None),
    )
    db.add(course)
    db.flush()

    src_note = f"منبع: برنامه‌یار۳۶۰ ({body.source_ref})" if body.source_ref else "منبع: برنامه‌یار۳۶۰"
    sv = SyllabusVersion(
        course_id=course.id, version_number=1, title=f"سرفصل درس {body.title}",
        status="DRAFT", source_kind="MANUAL", prerequisites_note=body.prerequisites_note,
        notes=src_note, created_by=user.id,
    )
    db.add(sv)
    db.flush()
    for idx, t in enumerate(body.topics):
        db.add(SyllabusTopic(
            syllabus_version_id=sv.id, kind="CHAPTER", title=t.title,
            description=t.description, order_index=idx,
            suggested_hours=t.suggested_hours, needs_review=t.needs_review,
        ))
    # استادِ واردکننده، استاد درس می‌شود تا بلافاصله در استودیو محتوا تولید کند
    if user.role == "PROFESSOR":
        db.add(CourseRole(course_id=course.id, user_id=user.id, role="PROFESSOR"))
    audit(db, user.id, "COURSE_IMPORT_PROGRAMYAR", "course", course.id,
          after={"code": course.code, "topics": len(body.topics), "source_ref": body.source_ref})
    db.commit()
    return {
        "course_id": str(course.id),
        "syllabus_version_id": str(sv.id),
        "topics_count": len(body.topics),
        "message": f"درس «{body.title}» با {len(body.topics)} سرفصل در دانشجو۳۶۰ ثبت شد.",
    }


# ---------- پایه‌یار۳۶۰: مرجع حقیقت درس/سرفصل (بازخورد ۳.۱) ----------

class BaseyarSyncIn(BaseModel):
    course_id: str
    mode: str = "INITIAL_PULL"  # INITIAL_PULL / CHANGE_EVENT / RECONCILE


@router.post("/integration/baseyar/sync")
def baseyar_sync(body: BaseyarSyncIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """همگام‌سازی رونوشت درس/سرفصل با مرجع پایه‌یار۳۶۰ (سه مسیر).

    تغییر نسخه سرفصل هرگز بی‌صدا اعمال نمی‌شود؛ گزارش تغییر و نگاشت‌های
    نیازمند بررسی استاد تولید می‌شود و شواهد/محتوا به نسخه خود وفادار می‌مانند."""
    _ensure_staff_user(user)
    from app.services import baseyar_service

    return baseyar_service.sync_course(db, user, body.course_id, body.mode)


@router.get("/integration/baseyar/status")
def baseyar_status(course_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _ensure_staff_user(user)
    from app.services import baseyar_service

    return baseyar_service.status_for(db, course_id)


@router.post("/integration/baseyar/reviews/{log_id}/apply")
def baseyar_apply_review(log_id: str, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """پس از بررسی استاد: هم‌ترازکردن رونوشت با نسخه مرجع + پاک‌سازی پرچم‌های بررسی."""
    _ensure_staff_user(user)
    from app.services import baseyar_service

    return baseyar_service.apply_review(db, user, log_id)
