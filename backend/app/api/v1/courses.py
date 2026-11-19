"""درس‌ها، سرفصل مجاز، گراف مفاهیم و منابع."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db, utcnow
from app.core.errors import not_found
from app.core.permissions import get_course_role, is_enrolled
from app.core.security import get_current_user
from app.models.identity import User
from app.models.courses import Course, CourseOffering, Enrollment
from app.models.syllabus import LearningObjective, SyllabusTopic, SyllabusVersion
from app.models.identity import CourseRole
from app.services import concept_service

router = APIRouter(tags=["courses"])


@router.get("/courses")
def list_courses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """درس‌های مرتبط با کاربر بر اساس نقش/ثبت‌نام."""
    out = []
    courses = db.query(Course).order_by(Course.code).all()
    for c in courses:
        role = get_course_role(db, user.id, c.id)
        enrolled = is_enrolled(db, user.id, c.id)
        staff_global = user.role in ("EDUCATION_ADMIN", "TECH_ADMIN", "QUALITY_REVIEWER")
        if not (role or enrolled or staff_global):
            continue
        active_sv = (
            db.query(SyllabusVersion)
            .filter(SyllabusVersion.course_id == c.id)
            .order_by(SyllabusVersion.version_number.desc())
            .first()
        )
        offering = db.query(CourseOffering).filter(CourseOffering.course_id == c.id).first()
        out.append({
            "id": str(c.id), "code": c.code, "title": c.title,
            "department": c.department, "term": offering.term if offering else c.term,
            "credits": c.credits,
            "my_role": role.value if role else ("STUDENT" if enrolled else user.role),
            "enrolled": enrolled,
            "syllabus_status": active_sv.status if active_sv else None,
        })
    return out


@router.get("/courses/{course_id}")
def course_detail(course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    role = get_course_role(db, user.id, course.id)
    enrolled = is_enrolled(db, user.id, course.id)
    if not (role or enrolled or user.role in ("EDUCATION_ADMIN", "TECH_ADMIN")):
        raise not_found("درس یافت نشد")
    prof_role = db.query(CourseRole).filter(CourseRole.course_id == course.id,
                                            CourseRole.role == "PROFESSOR").first()
    professor = db.get(User, prof_role.user_id) if prof_role else None
    return {
        "id": str(course.id), "code": course.code, "title": course.title,
        "department": course.department, "degree_level": course.degree_level,
        "field_of_study": course.field_of_study, "credits": course.credits,
        "description": course.description,
        "professor": professor.full_name if professor else None,
        "my_role": role.value if role else ("STUDENT" if enrolled else user.role),
    }


def syllabus_payload(db: Session, sv: SyllabusVersion) -> dict:
    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.syllabus_version_id == sv.id)
        .order_by(SyllabusTopic.order_index)
        .all()
    )
    objectives = (
        db.query(LearningObjective)
        .filter(LearningObjective.syllabus_version_id == sv.id)
        .order_by(LearningObjective.code)
        .all()
    )
    chapters = [t for t in topics if t.kind == "CHAPTER"]
    topics_by_parent: dict = {}
    for t in topics:
        if t.parent_id:
            topics_by_parent.setdefault(t.parent_id, []).append(t)
    chapter_list = []
    for ch in chapters:
        chapter_topics = []
        for t in topics_by_parent.get(ch.id, []):
            chapter_topics.append({
                "id": str(t.id), "title": t.title,
                "suggested_hours": t.suggested_hours,
                "needs_review": t.needs_review,
                "description": t.description,
            })
        chapter_list.append({
            "id": str(ch.id), "title": ch.title,
            "suggested_hours": ch.suggested_hours,
            "topics": chapter_topics,
        })
    return {
        "id": str(sv.id),
        "version_number": sv.version_number,
        "title": sv.title,
        "status": sv.status,
        "source_kind": sv.source_kind,
        "approval_reference": sv.approval_reference,
        "approved_date_source": sv.approved_date_source,
        "assessment_policy": sv.assessment_policy,
        "prerequisites_note": sv.prerequisites_note,
        "ambiguous_notes": sv.ambiguous_notes,
        "approved_at": sv.approved_at.isoformat() if sv.approved_at else None,
        "chapters": chapter_list,
        "objectives": [
            {"id": str(o.id), "code": o.code, "statement": o.statement,
             "bloom_level": o.bloom_level, "topic_id": str(o.topic_id) if o.topic_id else None}
            for o in objectives
        ],
    }


@router.get("/courses/{course_id}/syllabus")
def get_syllabus(course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.core.permissions import ensure_enrolled_or_staff

    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    ensure_enrolled_or_staff(db, user, course_id)
    # دانشجو فقط نسخه مصوب را می‌بیند؛ کارکنان آخرین نسخه را می‌بینند
    role = get_course_role(db, user.id, course_id)
    q = db.query(SyllabusVersion).filter(SyllabusVersion.course_id == course_id)
    if role is None and user.role == "STUDENT":
        sv = q.filter(SyllabusVersion.status == "APPROVED").order_by(
            SyllabusVersion.version_number.desc()).first()
    else:
        sv = q.order_by(SyllabusVersion.version_number.desc()).first()
    if sv is None:
        raise not_found("سرفصلی برای این درس ثبت نشده است")
    return syllabus_payload(db, sv)


@router.get("/courses/{course_id}/syllabus/versions")
def list_syllabus_versions(course_id: str, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    from app.core.permissions import ensure_staff

    ensure_staff(db, user, course_id)
    versions = (
        db.query(SyllabusVersion)
        .filter(SyllabusVersion.course_id == course_id)
        .order_by(SyllabusVersion.version_number.desc())
        .all()
    )
    return [
        {"id": str(sv.id), "version_number": sv.version_number, "status": sv.status,
         "source_kind": sv.source_kind,
         "approved_at": sv.approved_at.isoformat() if sv.approved_at else None,
         "notes": sv.notes}
        for sv in versions
    ]


@router.get("/courses/{course_id}/concept-graph")
def concept_graph(course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.core.permissions import ensure_enrolled_or_staff

    ensure_enrolled_or_staff(db, user, course_id)
    graph = concept_service.concept_graph(db, course_id)
    # برای دانشجو، وضعیت تسلط هم روی گراف می‌آید (بدون ارزش‌گذاری قطعی)
    if user.role == "STUDENT" or is_enrolled(db, user.id, course_id):
        from app.models.learning import MasteryEstimate

        estimates = {str(m.concept_id): m for m in
                     db.query(MasteryEstimate).filter(
                         MasteryEstimate.learner_id == user.id,
                         MasteryEstimate.course_id == course_id)}
        for node in graph["nodes"]:
            m = estimates.get(node["id"])
            node["mastery"] = {
                "status": m.status if m else "UNKNOWN",
                "estimated_mastery": m.estimated_mastery if m else None,
            }
    return graph


class ConceptIn(BaseModel):
    name: str
    key: str
    description: str | None = None
    topic_ids: list[str] = []
    prerequisite_ids: list[str] = []
    misconceptions: list[dict] = []
    examples: str | None = None
    counter_examples: str | None = None
    status: str = "DRAFT"


@router.post("/courses/{course_id}/concepts")
def create_concept(course_id: str, body: ConceptIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    from app.core.permissions import ensure_course_role
    from app.core.permissions import Role

    ensure_course_role(db, user, course_id, {Role.PROFESSOR, Role.ASSISTANT})
    concept = concept_service.create_concept(
        db, course_id, user, body.key, body.name, body.description,
        body.topic_ids, body.prerequisite_ids, body.misconceptions,
        body.examples, body.counter_examples, body.status,
    )
    return {"id": str(concept.id), "key": concept.key, "status": concept.status}


class ConceptPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    examples: str | None = None
    counter_examples: str | None = None


@router.patch("/concepts/{concept_id}")
def patch_concept(concept_id: str, body: ConceptPatch, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    from app.core.errors import validation_error
    from app.core.permissions import ensure_course_role
    from app.core.permissions import Role
    from app.models.concepts import Concept

    concept = db.get(Concept, concept_id)
    if concept is None:
        raise not_found("مفهوم یافت نشد")
    ensure_course_role(db, user, concept.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    if body.name is not None:
        concept.name = body.name
    if body.description is not None:
        concept.description = body.description
    if body.examples is not None:
        concept.examples = body.examples
    if body.counter_examples is not None:
        concept.counter_examples = body.counter_examples
    if body.status is not None:
        if body.status not in ("DRAFT", "APPROVED"):
            raise validation_error("وضعیت مفهوم فقط DRAFT یا APPROVED است")
        concept.status = body.status
        if body.status == "APPROVED":
            concept.approved_by = user.id
            concept.approved_at = utcnow()
    db.flush()
    return {"id": str(concept.id), "status": concept.status}
