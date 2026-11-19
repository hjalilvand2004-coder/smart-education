"""استودیوی محتوای استاد با AI (بخش ۴): طرح آموزشی → تولید ساختاریافته → کنترل کیفیت
→ ویرایش/بازتولید بخشی → بررسی → انتشار.

اصول کلیدی:
- خروجی AI ابتدا به مدل داده داخلی (بلوک) تبدیل می‌شود، نه مستقیماً فایل نهایی.
- بازتولید یک بخش، ویرایش دستی سایر بخش‌ها را از بین نمی‌برد (AC-03).
- ویرایش نسخه منتشرشده، نسخه جدید می‌سازد؛ سابقه منتشرشده تغییر نمی‌کند.
- انتشار فقط توسط استاد درس و فقط برای نسخه تأییدشده (AC-05).
"""
import copy
import uuid

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.schemas import AIBlock, BlockRegenOut, ContentOut, ContentPlanOut
from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.errors import conflict, forbidden, not_found, validation_error
from app.models.concepts import Concept, ConceptMisconception, TopicConcept
from app.models.content import ContentDocument, ContentPlan, ContentReview, ContentVersion
from app.models.courses import Course
from app.models.resources import Resource
from app.models.syllabus import LearningObjective, SyllabusTopic, SyllabusVersion
from app.services import rag as rag_service

VALID_BLOCK_TYPES = (
    "heading", "text", "definition", "note", "worked_example", "exercise",
    "table", "formula", "image", "code", "self_check", "summary", "reference",
)


# ---------- سند ----------

def create_document(db: Session, user, payload: dict) -> ContentDocument:
    course_id = payload["course_id"]
    sv_id = payload["syllabus_version_id"]
    sv = db.get(SyllabusVersion, sv_id)
    if sv is None or str(sv.course_id) != str(course_id):
        raise validation_error("نسخه سرفصل با درس همخوانی ندارد")
    # AC-01: تولید محتوا فقط با اتصال به نسخه مشخص سرفصل
    doc = ContentDocument(
        course_id=course_id,
        syllabus_version_id=sv_id,
        title=payload.get("title") or "سند آموزشی جدید",
        goal=payload.get("goal", "CONCEPT_TEACHING"),
        scope=payload.get("scope") or {},
        audience_level=payload.get("audience_level"),
        duration_minutes=payload.get("duration_minutes"),
        language=payload.get("language", "FA"),
        style=payload.get("style", "ACADEMIC"),
        components=payload.get("components") or [],
        source_resource_ids=payload.get("source_resource_ids") or [],
        constraints=payload.get("constraints"),
        created_by=user.id,
    )
    db.add(doc)
    db.flush()
    audit(db, user.id, "CONTENT_DOCUMENT_CREATE", "content_document", doc.id,
          after={"title": doc.title, "syllabus_version": str(sv_id)})
    return doc


def _document_inputs(db: Session, doc: ContentDocument) -> dict:
    """ورودی‌های استاندارد مدل: مفاهیم، اهداف، منابع (فقط منابع مجاز همان درس)."""
    concept_ids = doc.scope.get("concept_ids") or []
    concepts: list[Concept] = []
    if concept_ids:
        concepts = db.query(Concept).filter(Concept.id.in_(concept_ids)).all()
    else:
        topics = doc.scope.get("topic_ids") or []
        if topics:
            concepts = (
                db.query(Concept)
                .join(TopicConcept, TopicConcept.concept_id == Concept.id)
                .filter(TopicConcept.topic_id.in_(topics))
                .all()
            )
        else:
            concepts = db.query(Concept).filter(Concept.course_id == doc.course_id).all()

    from app.services.concept_service import get_prerequisites

    concept_inputs = []
    for c in concepts:
        prereqs = get_prerequisites(db, c.id)
        misconceptions = [
            {"title": m.title, "correction_hint": m.correction_hint}
            for m in db.query(ConceptMisconception)
            .filter(ConceptMisconception.concept_id == c.id).all()
        ]
        concept_inputs.append({
            "id": str(c.id), "key": c.key, "name": c.name,
            "description": c.description,
            "prerequisites": [p.name for p in prereqs if p],
            "misconceptions": misconceptions,
        })
    objectives = [
        {"id": str(o.id), "code": o.code, "statement": o.statement}
        for o in db.query(LearningObjective)
        .filter(LearningObjective.syllabus_version_id == doc.syllabus_version_id)
    ]
    # متناسب‌سازی با سرفصل: موضوعات در محدوده سند (عنوان/توضیح/ساعات) به ورودی مدل اضافه می‌شود
    topic_ids = doc.scope.get("topic_ids") or []
    topics_info = []
    if topic_ids:
        rows = (
            db.query(SyllabusTopic)
            .filter(SyllabusTopic.id.in_(topic_ids))
            .order_by(SyllabusTopic.order_index)
            .all()
        )
        topics_info = [
            {"title": t.title, "description": t.description,
             "suggested_hours": t.suggested_hours}
            for t in rows
        ]
    course = db.get(Course, doc.course_id)
    resources = []
    for rid in doc.source_resource_ids or []:
        r = db.get(Resource, rid)
        if r and str(r.course_id) == str(doc.course_id) and r.status == "AVAILABLE":
            resources.append({"id": str(r.id), "title": r.title})
    return {
        "title": doc.title,
        "goal": doc.goal,
        "style": doc.style,
        "components": doc.components,
        "language": doc.language,
        "audience_level": doc.audience_level,
        "duration_minutes": doc.duration_minutes,
        "course_title": course.title if course else None,
        "syllabus_topics": topics_info,
        "objectives": objectives,
        "concepts": concept_inputs,
        "resources": resources,
        "constraints": doc.constraints or {},
    }


# ---------- مرحله اول: طرح آموزشی ----------

def propose_plan(db: Session, doc: ContentDocument, user, job_id=None) -> ContentPlan:
    gateway = AIGateway(db)
    inputs = _document_inputs(db, doc)
    plan_out: ContentPlanOut = gateway.run("content_plan", inputs, schema=ContentPlanOut,
                                           created_by=user.id, job_id=job_id)
    plan = ContentPlan(document_id=doc.id, plan=plan_out.model_dump(),
                       generated_by_run_id=job_id)
    db.add(plan)
    db.flush()
    return plan


def confirm_plan(db: Session, plan: ContentPlan, user) -> ContentPlan:
    if plan.status == "CONFIRMED":
        return plan
    plan.status = "CONFIRMED"
    plan.confirmed_by = user.id
    plan.confirmed_at = utcnow()
    db.flush()
    return plan


# ---------- مرحله دوم: تولید ساختاریافته ----------

def generate_content(db: Session, doc: ContentDocument, plan: ContentPlan,
                     user, job_id=None) -> ContentVersion:
    """تولید پیش‌نویس؛ خروجی AI به بلوک‌های مدل داده داخلی تبدیل می‌شود."""
    from app.models.content import ContentVersion as CV

    if str(db.get(SyllabusVersion, doc.syllabus_version_id).status) != "APPROVED":
        raise validation_error("تولید محتوا فقط بر پایه نسخه مصوب سرفصل مجاز است (AC-01)")
    gateway = AIGateway(db)
    inputs = _document_inputs(db, doc)
    inputs["plan"] = plan.plan
    out: ContentOut = gateway.run("content_generation", inputs, schema=ContentOut,
                                  created_by=user.id, job_id=job_id)

    valid_concept_ids = {str(c.id) for c in
                         db.query(Concept).filter(Concept.course_id == doc.course_id)}
    valid_resource_ids = {str(r.id) for r in
                          db.query(Resource).filter(Resource.course_id == doc.course_id)}
    blocks = []
    for b in out.blocks:
        data = b.model_dump()
        data["id"] = data.get("id") or uuid.uuid4().hex[:12]
        data["type"] = data["type"] if data["type"] in VALID_BLOCK_TYPES else "text"
        data["concept_ids"] = [cid for cid in data.get("concept_ids", []) if cid in valid_concept_ids]
        data["source_refs"] = [rid for rid in data.get("source_refs", []) if rid in valid_resource_ids]
        blocks.append(data)

    last = (
        db.query(CV).filter(CV.document_id == doc.id)
        .order_by(CV.version_number.desc()).first()
    )
    version = CV(
        document_id=doc.id,
        version_number=(last.version_number + 1) if last else 1,
        syllabus_version_id=doc.syllabus_version_id,
        structured_content={"blocks": blocks},
        status="GENERATED",
        plan_id=plan.id,
        generated_by_run_id=job_id,
        created_by=user.id,
    )
    db.add(version)
    db.flush()
    version.qc_report = run_qc(db, version)
    doc.current_version_id = version.id
    db.flush()
    return version


# ---------- مرحله سوم: کنترل کیفیت ----------

def run_qc(db: Session, version: ContentVersion) -> dict:
    """کنترل کیفیت ساختاری — تضمین صحت علمی نیست؛ تأیید استاد همچنان ضروری است."""
    doc = db.get(ContentDocument, version.document_id)
    blocks = (version.structured_content or {}).get("blocks", [])
    objectives = db.query(LearningObjective).filter(
        LearningObjective.syllabus_version_id == version.syllabus_version_id).all()
    topic_ids = [t.id for t in db.query(SyllabusTopic).filter(
        SyllabusTopic.syllabus_version_id == version.syllabus_version_id)]
    in_scope_concepts = {
        str(tc.concept_id)
        for tc in db.query(TopicConcept).filter(TopicConcept.topic_id.in_(topic_ids or [uuid.uuid4()]))
    }
    concept_ids_in_blocks = {cid for b in blocks for cid in b.get("concept_ids", [])}

    coverage = []
    for o in objectives:
        # پوشش هدف: از طریق مفاهیمِ موضوعِ هدف یا بلوک هدف‌محور
        o_topic_concepts = {
            str(tc.concept_id) for tc in db.query(TopicConcept)
            .filter(TopicConcept.topic_id == o.topic_id)
        } if o.topic_id else set()
        evidence = [
            b.get("id") for b in blocks
            if (set(b.get("concept_ids", [])) & o_topic_concepts)
            or (o.code in (b.get("title") or ""))
        ]
        coverage.append({
            "objective_id": str(o.id), "code": o.code,
            "statement": o.statement, "covered": bool(evidence),
            "evidence_blocks": evidence,
        })

    out_of_scope = sorted(concept_ids_in_blocks - in_scope_concepts)
    resource_ids = {str(r.id) for r in db.query(Resource).filter(Resource.course_id == doc.course_id)}
    used_refs = {rid for b in blocks for rid in b.get("source_refs", [])}
    invalid_refs = sorted(used_refs - resource_ids)

    warnings = []
    for b in blocks:
        if b["type"] in ("text", "definition", "note") and not (b.get("body") or "").strip():
            warnings.append(f"بلوک {b['id']} ({b['type']}) بدون متن است")
        if b["type"] == "worked_example" and not b.get("steps"):
            warnings.append(f"مثال حل‌شده {b['id']} بدون گام‌های حل است")
        if b["type"] == "self_check" and not b.get("answer"):
            warnings.append(f"پرسش خودارزیابی {b['id']} بدون پاسخ است")
        if len(b.get("body") or "") > 2500:
            warnings.append(f"بلوک {b['id']} بیش از حد طولانی است؛ پیشنهاد تقسیم")

    missing_sources = []
    if not used_refs and blocks:
        missing_sources.append("هیچ ارجاعی به منابع مجاز درس وجود ندارد")

    covered_count = sum(1 for c in coverage if c["covered"])
    overall = "PASS"
    if out_of_scope or invalid_refs:
        overall = "WARN"
    if objectives and covered_count == 0:
        overall = "FAIL"
    return {
        "coverage": coverage,
        "coverage_ratio": round(covered_count / len(coverage), 2) if coverage else None,
        "out_of_scope_concepts": out_of_scope,
        "invalid_refs": invalid_refs,
        "missing_sources": missing_sources,
        "structure_warnings": warnings,
        "overall": overall,
        "checked_at": utcnow().isoformat(),
        "note": "این کنترل تضمین صحت علمی نیست؛ تأیید استاد ضروری است.",
    }


# ---------- مرحله چهارم: ویرایش، بازتولید بخشی، بررسی و انتشار ----------

def _ensure_editable(version: ContentVersion) -> None:
    if version.status in ("GENERATING",):
        raise validation_error("محتوا در حال تولید است؛ ویرایش ممکن نیست")


def edit_block(db: Session, version: ContentVersion, block_id: str, patch: dict,
               expected_revision: int, user) -> ContentVersion:
    """ویرایش یک بلوک با قفل بهینه؛ ویرایش نسخه منتشرشده نسخه جدید می‌سازد."""
    _ensure_editable(version)
    if expected_revision != version.revision:
        raise conflict("این نسخه توسط دیگری تغییر کرده است؛ نسخه تازه را بگیرید و دوباره تلاش کنید",
                       {"current_revision": version.revision})
    if version.status == "PUBLISHED":
        version = create_new_draft_from(db, version, user)

    # کپی عمیق: تغییر درجا باعث می‌شود SQLAlchemy مقدار جدید را «برابر» ببیند و UPDATE نزند
    blocks = copy.deepcopy((version.structured_content or {}).get("blocks", []))
    target = next((b for b in blocks if b.get("id") == block_id), None)
    if target is None:
        raise not_found("بلوک موردنظر یافت نشد")
    allowed_fields = {"title", "body", "items", "steps", "columns", "rows",
                      "formula", "language", "question", "answer", "explanation"}
    clean = {k: v for k, v in (patch or {}).items() if k in allowed_fields}
    if not clean:
        raise validation_error("فیلد قابل ویرایشی در درخواست نیست")
    target.update(clean)
    version.revision += 1
    changes = list(version.human_changes or [])
    changes.append({"block_id": block_id, "fields": sorted(clean.keys()),
                    "by": str(user.id), "at": utcnow().isoformat()})
    version.human_changes = changes
    version.structured_content = {"blocks": blocks}  # SQLAlchemy mutation tracking
    db.flush()
    audit(db, user.id, "CONTENT_BLOCK_EDIT", "content_version", version.id,
          after={"block_id": block_id, "fields": sorted(clean.keys())})
    return version


def regenerate_block(db: Session, version: ContentVersion, block_id: str,
                     instruction: str | None, user, job_id=None) -> ContentVersion:
    """بازتولید فقط یک بخش؛ سایر بخش‌ها و ویرایش‌های دستی دست‌نخورده می‌مانند (AC-03)."""
    _ensure_editable(version)
    if version.status == "PUBLISHED":
        version = create_new_draft_from(db, version, user)
    blocks = copy.deepcopy((version.structured_content or {}).get("blocks", []))
    idx = next((i for i, b in enumerate(blocks) if b.get("id") == block_id), None)
    if idx is None:
        raise not_found("بلوک موردنظر یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    neighbors = [
        {"id": b["id"], "type": b["type"], "title": b.get("title")}
        for b in blocks[max(0, idx - 2): idx + 3] if b["id"] != block_id
    ]
    gateway = AIGateway(db)
    out: BlockRegenOut = gateway.run(
        "block_regeneration",
        {"block": blocks[idx], "neighbors": neighbors,
         "instruction": instruction, "document_title": doc.title},
        schema=BlockRegenOut, created_by=user.id, job_id=job_id,
    )
    new_block = out.block.model_dump()
    new_block["id"] = block_id  # شناسه بلوک ثابت می‌ماند تا ارجاع‌ها نشکنند
    blocks[idx] = new_block
    version.revision += 1
    version.structured_content = {"blocks": blocks}
    changes = list(version.human_changes or [])
    changes.append({"block_id": block_id, "fields": ["__regenerated__"],
                    "by": str(user.id), "at": utcnow().isoformat()})
    version.human_changes = changes
    db.flush()
    return version


def create_new_draft_from(db: Session, version: ContentVersion, user) -> ContentVersion:
    """کپی نسخه منتشرشده به پیش‌نویس جدید — سابقه منتشرشده دست‌نخورده می‌ماند."""
    last = (
        db.query(ContentVersion).filter(ContentVersion.document_id == version.document_id)
        .order_by(ContentVersion.version_number.desc()).first()
    )
    new_v = ContentVersion(
        document_id=version.document_id,
        version_number=(last.version_number + 1 if last else 1),
        syllabus_version_id=version.syllabus_version_id,
        structured_content={"blocks": [dict(b) for b in
                                       (version.structured_content or {}).get("blocks", [])]},
        status="GENERATED",
        plan_id=version.plan_id,
        qc_report=version.qc_report,
        human_changes=[{"type": "new_draft_from", "from_version": version.version_number,
                        "by": str(user.id), "at": utcnow().isoformat()}],
        created_by=user.id,
    )
    db.add(new_v)
    db.flush()
    doc = db.get(ContentDocument, version.document_id)
    doc.current_version_id = new_v.id
    db.flush()
    return new_v


def review_version(db: Session, version: ContentVersion, user, decision: str,
                   notes: str | None = None) -> ContentVersion:
    from app.core.permissions import REVIEWER_ROLES, Role, get_course_role

    doc = db.get(ContentDocument, version.document_id)
    if decision == "SUBMIT_FOR_REVIEW":
        if version.status not in ("GENERATED", "NEEDS_REVISION"):
            raise validation_error("این وضعیت برای ارسال به بررسی مناسب نیست")
        version.status = "UNDER_REVIEW"
    elif decision == "APPROVE":
        role = get_course_role(db, user.id, doc.course_id)
        if role not in REVIEWER_ROLES and user.role not in ("EDUCATION_ADMIN", "TECH_ADMIN"):
            raise forbidden("تأیید محتوا فقط توسط نقش‌های مجاز بررسی")
        version.status = "APPROVED"
        version.approved_by = user.id
        version.approved_at = utcnow()
    elif decision == "REQUEST_CHANGES":
        version.status = "NEEDS_REVISION"
    else:
        raise validation_error("تصمیم بررسی نامعتبر است")
    db.add(ContentReview(
        content_version_id=version.id, reviewer_id=user.id,
        decision=decision, notes=notes, coverage_snapshot=version.qc_report,
    ))
    db.flush()
    return version


def publish_version(db: Session, version: ContentVersion, user) -> ContentVersion:
    doc = db.get(ContentDocument, version.document_id)
    from app.core.permissions import ensure_can_publish

    ensure_can_publish(db, user, doc.course_id)
    if version.status != "APPROVED":
        raise validation_error("فقط نسخه تأییدشده قابل انتشار است (AC-05)")
    version.status = "PUBLISHED"
    version.published_at = utcnow()
    doc.current_version_id = version.id
    audit(db, user.id, "CONTENT_PUBLISH", "content_version", version.id,
          before={"status": "APPROVED"},
          after={"version_number": version.version_number, "document": doc.title})
    from app.models.ops import OutboxEvent

    db.add(OutboxEvent(event_type="content.published", payload={
        "content_version_id": str(version.id), "document_id": str(doc.id),
        "course_id": str(doc.course_id), "title": doc.title,
    }))
    db.flush()
    return version


def student_readable_versions(db: Session, course_id) -> list[ContentVersion]:
    return (
        db.query(ContentVersion)
        .join(ContentDocument, ContentVersion.document_id == ContentDocument.id)
        .filter(ContentDocument.course_id == course_id,
                ContentVersion.status == "PUBLISHED")
        .order_by(ContentVersion.published_at.desc())
        .all()
    )


def build_version_payload(db: Session, version: ContentVersion) -> dict:
    doc = db.get(ContentDocument, version.document_id)
    plan = db.get(ContentPlan, version.plan_id) if version.plan_id else None
    return {
        "id": str(version.id),
        "document_id": str(version.document_id),
        "document_title": doc.title if doc else None,
        "version_number": version.version_number,
        "status": version.status,
        "revision": version.revision,
        "blocks": (version.structured_content or {}).get("blocks", []),
        "qc_report": version.qc_report,
        "plan": plan.plan if plan else None,
        "human_changes": version.human_changes or [],
        "generated_by": "AI" if version.generated_by_run_id else "HUMAN",
        "approved_at": version.approved_at.isoformat() if version.approved_at else None,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "created_at": version.created_at.isoformat(),
    }
