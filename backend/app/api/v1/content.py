"""استودیوی محتوا: سند، تولید، ویرایش بلوک، بررسی، انتشار (بخش ۴)."""
from fastapi import APIRouter, BackgroundTasks, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import schedule_job
from app.core.database import get_db
from app.core.errors import conflict, not_found, validation_error
from app.core.permissions import Role, ensure_course_role, ensure_staff
from app.core.security import get_current_user
from app.models.content import ContentDocument, ContentPlan, ContentVersion
from app.models.identity import User
from app.services import content_service

router = APIRouter(tags=["content"])


class DocumentIn(BaseModel):
    course_id: str
    syllabus_version_id: str
    title: str
    goal: str = "CONCEPT_TEACHING"
    scope: dict = {}
    audience_level: str | None = None
    duration_minutes: int | None = None
    language: str = "FA"
    style: str = "ACADEMIC"
    components: list[str] = []
    source_resource_ids: list[str] = []
    constraints: dict | None = None


def document_payload(db: Session, doc: ContentDocument) -> dict:
    versions = (
        db.query(ContentVersion)
        .filter(ContentVersion.document_id == doc.id)
        .order_by(ContentVersion.version_number.desc())
        .all()
    )
    plans = (
        db.query(ContentPlan)
        .filter(ContentPlan.document_id == doc.id)
        .order_by(ContentPlan.created_at.desc())
        .all()
    )
    return {
        "id": str(doc.id),
        "course_id": str(doc.course_id),
        "syllabus_version_id": str(doc.syllabus_version_id),
        "title": doc.title,
        "goal": doc.goal,
        "scope": doc.scope,
        "audience_level": doc.audience_level,
        "duration_minutes": doc.duration_minutes,
        "language": doc.language,
        "style": doc.style,
        "components": doc.components,
        "source_resource_ids": doc.source_resource_ids,
        "constraints": doc.constraints,
        "current_version_id": str(doc.current_version_id) if doc.current_version_id else None,
        "versions": [
            {"id": str(v.id), "version_number": v.version_number, "status": v.status,
             "revision": v.revision, "qc_overall": (v.qc_report or {}).get("overall"),
             "published_at": v.published_at.isoformat() if v.published_at else None}
            for v in versions
        ],
        "plans": [
            {"id": str(p.id), "status": p.status, "plan": p.plan}
            for p in plans
        ],
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/content-documents")
def list_documents(course_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user), page: int = 1, page_size: int = 20):
    ensure_staff(db, user, course_id)
    q = (
        db.query(ContentDocument)
        .filter(ContentDocument.course_id == course_id)
        .order_by(ContentDocument.created_at.desc())
    )
    total = q.count()
    docs = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {"id": str(d.id), "title": d.title, "goal": d.goal, "style": d.style,
             "current_version_id": str(d.current_version_id) if d.current_version_id else None}
            for d in docs
        ],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/content-documents")
def create_document(body: DocumentIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """ایجاد سند آموزشی متصل به نسخه مشخص سرفصل (AC-01)."""
    ensure_course_role(db, user, body.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    doc = content_service.create_document(db, user, body.model_dump())
    db.commit()
    return document_payload(db, doc)


@router.get("/content-documents/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    doc = db.get(ContentDocument, document_id)
    if doc is None:
        raise not_found("سند یافت نشد")
    ensure_staff(db, user, doc.course_id)
    return document_payload(db, doc)


class GenerationJobIn(BaseModel):
    mode: str = "FULL"  # PLAN | CONTENT | FULL
    auto_confirm: bool = True
    block_id: str | None = None  # برای بازتولید یک بخش
    instruction: str | None = None


@router.post("/content-documents/{document_id}/generation-jobs", status_code=202)
def generation_job(document_id: str, body: GenerationJobIn, background_tasks: BackgroundTasks,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user),
                   idempotency_key: str | None = Header(default=None)):
    doc = db.get(ContentDocument, document_id)
    if doc is None:
        raise not_found("سند یافت نشد")
    ensure_course_role(db, user, doc.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    if body.mode not in ("PLAN", "CONTENT", "FULL"):
        raise validation_error("mode نامعتبر است")
    if body.block_id:
        # AC-03: بازتولید یک بخش بدون ازبین‌رفتن سایر ویرایش‌ها
        if body.mode != "CONTENT":
            raise validation_error("بازتولید بلوک با mode=CONTENT انجام می‌شود")
        current = db.get(ContentVersion, doc.current_version_id) if doc.current_version_id else None
        if current is None:
            raise validation_error("نسخه‌ای برای بازتولید بلوک وجود ندارد")
        payload = {"content_version_id": str(current.id), "block_id": body.block_id,
                   "instruction": body.instruction, "user_id": str(user.id)}
        return schedule_job(background_tasks, db, "content_block_regeneration", payload, user,
                            idempotency_key)
    kind = {"PLAN": "content_plan", "CONTENT": "content_generation", "FULL": "content_full"}[body.mode]
    return schedule_job(background_tasks, db, kind, {"document_id": document_id}, user,
                        idempotency_key)


@router.get("/content-plans/{plan_id}")
def get_plan(plan_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.get(ContentPlan, plan_id)
    if plan is None:
        raise not_found("طرح یافت نشد")
    doc = db.get(ContentDocument, plan.document_id)
    ensure_staff(db, user, doc.course_id)
    return {"id": str(plan.id), "document_id": str(plan.document_id),
            "status": plan.status, "plan": plan.plan}


class PlanPatch(BaseModel):
    plan: dict


@router.patch("/content-plans/{plan_id}")
def patch_plan(plan_id: str, body: PlanPatch, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """اصلاح طرح آموزشی توسط استاد پیش از تولید کامل."""
    plan = db.get(ContentPlan, plan_id)
    if plan is None:
        raise not_found("طرح یافت نشد")
    doc = db.get(ContentDocument, plan.document_id)
    ensure_course_role(db, user, doc.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    if plan.status == "CONFIRMED":
        raise validation_error("طرح تأییدشده قابل ویرایش نیست؛ طرح جدید بسازید")
    plan.plan = body.plan
    db.flush()
    db.commit()
    return {"id": str(plan.id), "status": plan.status}


@router.post("/content-plans/{plan_id}/confirm")
def confirm_plan(plan_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = db.get(ContentPlan, plan_id)
    if plan is None:
        raise not_found("طرح یافت نشد")
    doc = db.get(ContentDocument, plan.document_id)
    ensure_course_role(db, user, doc.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    content_service.confirm_plan(db, plan, user)
    db.commit()
    return {"id": str(plan.id), "status": plan.status}


@router.get("/content-versions/{version_id}")
def get_version(version_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """کارکنان: همه نسخه‌ها؛ دانشجوی ثبت‌نام‌شده: فقط نسخه منتشرشده (بدون فیلدهای مدیریتی)."""
    from app.core.errors import AppError, forbidden
    from app.core.permissions import is_enrolled

    version = db.get(ContentVersion, version_id)
    if version is None:
        raise not_found("نسخه محتوا یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    try:
        ensure_staff(db, user, doc.course_id)
        return content_service.build_version_payload(db, version)
    except AppError:
        # دانشجو: فقط نسخه منتشرشده همان درس که در آن ثبت‌نام دارد
        if version.status != "PUBLISHED" or not is_enrolled(db, user.id, doc.course_id):
            raise forbidden("دسترسی به این نسخه محتوا مجاز نیست")
        payload = content_service.build_version_payload(db, version)
        payload["qc_report"] = None
        payload["plan"] = None
        payload["human_changes"] = []
        return payload


class BlockPatchIn(BaseModel):
    patch: dict
    expected_revision: int


@router.patch("/content-versions/{version_id}/blocks/{block_id}")
def edit_block(version_id: str, block_id: str, body: BlockPatchIn,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """ویرایش مستقیم یک بلوک با کنترل نسخه (409 در تداخل)."""
    version = db.get(ContentVersion, version_id)
    if version is None:
        raise not_found("نسخه محتوا یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    ensure_course_role(db, user, doc.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    version = content_service.edit_block(db, version, block_id, body.patch,
                                         body.expected_revision, user)
    db.commit()
    return content_service.build_version_payload(db, version)


class RegenIn(BaseModel):
    instruction: str | None = None


@router.post("/content-versions/{version_id}/blocks/{block_id}/regenerate", status_code=202)
def regenerate_block(version_id: str, block_id: str, body: RegenIn | None = None,
                     background_tasks: BackgroundTasks = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user),
                     idempotency_key: str | None = Header(default=None)):
    version = db.get(ContentVersion, version_id)
    if version is None:
        raise not_found("نسخه محتوا یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    ensure_course_role(db, user, doc.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    payload = {"content_version_id": version_id, "block_id": block_id,
               "instruction": body.instruction if body else None, "user_id": str(user.id)}
    return schedule_job(background_tasks, db, "content_block_regeneration", payload, user,
                        idempotency_key)


class ReviewIn(BaseModel):
    decision: str
    notes: str | None = None


@router.post("/content-versions/{version_id}/reviews")
def review_version(version_id: str, body: ReviewIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    version = db.get(ContentVersion, version_id)
    if version is None:
        raise not_found("نسخه محتوا یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    ensure_staff(db, user, doc.course_id)
    version = content_service.review_version(db, version, user, body.decision, body.notes)
    db.commit()
    return {"id": str(version.id), "status": version.status}


@router.post("/content-versions/{version_id}/publish")
def publish_version(version_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """انتشار فقط توسط استاد درس و فقط برای نسخه تأییدشده (AC-05)."""
    version = db.get(ContentVersion, version_id)
    if version is None:
        raise not_found("نسخه محتوا یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    version = content_service.publish_version(db, version, user)
    db.commit()
    return {"id": str(version.id), "status": version.status,
            "published_at": version.published_at.isoformat()}


@router.get("/courses/{course_id}/contents")
def student_contents(course_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """محتوای منتشرشده مجاز برای دانشجو (AC-05)."""
    from app.core.permissions import ensure_enrolled_or_staff

    ensure_enrolled_or_staff(db, user, course_id)
    versions = content_service.student_readable_versions(db, course_id)
    out = []
    for v in versions:
        doc = db.get(ContentDocument, v.document_id)
        out.append({
            "document_id": str(doc.id), "document_title": doc.title,
            "version_id": str(v.id), "version_number": v.version_number,
            "published_at": v.published_at.isoformat() if v.published_at else None,
        })
    return out
