"""یادگیری مشارکتی / دانشجو تولیدکننده (بخش ۹).

چرخه: DRAFT → AI_FEEDBACK → SUBMITTED → PEER_REVIEW → TEACHER_REVIEW → APPROVED
- بازخورد AI صرفاً مجوز ورود به بررسی همتا است؛ تأیید AI پذیرش نیست.
- هیچ تولید دانشجویی مستقیماً وارد بانک رسمی سؤال نمی‌شود.
- رویداد مشارکت معتبر فقط پس از تأیید استاد به باشگاه ارسال می‌شود (outbox).
"""
import json

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.schemas import CreationFeedbackOut
from app.core.audit import audit
from app.core.errors import forbidden, validation_error
from app.models.collaboration import (ModerationReview, PeerReview,
                                      StudentCreation)
from app.models.ops import OutboxEvent

_BANNED_PATTERNS = ["احمق", "بیشرف", "توهین", "بی‌مغز"]


def _content_check(content: dict) -> None:
    text = json.dumps(content, ensure_ascii=False)
    for w in _BANNED_PATTERNS:
        if w in text:
            raise validation_error("محتوا شامل واژه‌های نامناسب است و ثبت نمی‌شود")


def create_creation(db: Session, student, course_id, payload: dict) -> StudentCreation:
    from app.core.permissions import is_enrolled

    if not is_enrolled(db, student.id, course_id):
        raise forbidden("فقط دانشجوی ثبت‌نام‌شده می‌تواند تولید داشته باشد")
    _content_check(payload.get("content") or {})
    creation = StudentCreation(
        course_id=course_id, student_id=student.id,
        activity_type=payload.get("activity_type", "EXPLANATION"),
        concept_id=payload.get("concept_id"),
        content=payload.get("content") or {},
        ai_use_disclosed=bool(payload.get("ai_use_disclosed")),
        status="DRAFT",
    )
    db.add(creation)
    db.flush()
    # بازخورد AI فوری (چرخه: DRAFT → AI_FEEDBACK)
    gateway = AIGateway(db)
    try:
        from app.models.concepts import Concept

        concept = db.get(Concept, payload.get("concept_id")) if payload.get("concept_id") else None
        feedback: CreationFeedbackOut = gateway.run(
            "creation_feedback",
            {"activity_type": creation.activity_type,
             "content": creation.content,
             "concept_name": concept.name if concept else None},
            schema=CreationFeedbackOut,
        )
        creation.ai_feedback = feedback.model_dump()
        creation.status = "AI_FEEDBACK"
    except Exception:  # noqa: BLE001 — حالت جایگزین بدون AI: مستقیم به بررسی
        creation.ai_feedback = {"feedback": "بازخورد AI در دسترس نیست؛ تولید شما برای بررسی ارسال شد."}
        creation.status = "SUBMITTED"
    db.flush()
    return creation


def submit_creation(db: Session, creation: StudentCreation, student) -> StudentCreation:
    if str(creation.student_id) != str(student.id):
        raise forbidden("این تولید متعلق به شما نیست")
    if creation.status not in ("DRAFT", "AI_FEEDBACK"):
        raise validation_error("این تولید قبلاً ارسال شده است")
    creation.status = "SUBMITTED"
    _assign_peers(db, creation)
    db.flush()
    return creation


def _assign_peers(db: Session, creation: StudentCreation) -> None:
    """تخصیص تا دو همتا از همکلاسی‌ها (به‌جز نویسنده)."""
    from app.models.courses import CourseOffering, Enrollment

    classmates = [
        e.student_id for e in db.query(Enrollment)
        .join(CourseOffering, Enrollment.offering_id == CourseOffering.id)
        .filter(CourseOffering.course_id == creation.course_id,
                Enrollment.student_id != creation.student_id)
        .all()
    ]
    creation.peer_reviewer_ids = [str(s) for s in classmates[:2]]
    if classmates:
        creation.status = "PEER_REVIEW"


def add_peer_review(db: Session, creation: StudentCreation, reviewer, payload: dict) -> PeerReview:
    if str(reviewer.id) == str(creation.student_id):
        raise forbidden("نویسنده نمی‌تواند همتای خود را بررسی کند")
    scores = payload.get("scores") or {}
    for k in ("clarity", "correctness", "usefulness"):
        if k not in scores:
            raise validation_error(f"امتیاز {k} الزامی است")
    review = PeerReview(creation_id=creation.id, reviewer_id=reviewer.id,
                        scores=scores, comment=payload.get("comment"))
    db.add(review)
    count = db.query(PeerReview).filter(PeerReview.creation_id == creation.id).count()
    if count >= 2 and creation.status == "PEER_REVIEW":
        creation.status = "TEACHER_REVIEW"
    db.flush()
    return review


def teacher_review(db: Session, creation: StudentCreation, teacher, decision: str,
                   comment: str | None = None) -> StudentCreation:
    from app.core.permissions import ensure_course_role
    from app.core.permissions import Role

    ensure_course_role(db, teacher, creation.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    db.add(ModerationReview(creation_id=creation.id, moderator_id=teacher.id,
                            decision=decision, comment=comment))
    if decision == "APPROVE":
        creation.status = "APPROVED"
        # رویداد مشارکت معتبر برای باشگاه — فقط پس از تأیید مرجع مربوط
        db.add(OutboxEvent(event_type="club.valid_participation", payload={
            "student_id": str(creation.student_id),
            "course_id": str(creation.course_id),
            "activity_type": creation.activity_type,
            "creation_id": str(creation.id),
        }))
        audit(db, teacher.id, "CREATION_APPROVE", "student_creation", creation.id)
    else:
        creation.status = "REJECTED"
    db.flush()
    return creation


def creation_payload(db: Session, creation: StudentCreation) -> dict:
    from app.models.collaboration import PeerReview as PR

    reviews = db.query(PR).filter(PR.creation_id == creation.id).all()
    return {
        "id": str(creation.id),
        "course_id": str(creation.course_id),
        "student_id": str(creation.student_id),
        "activity_type": creation.activity_type,
        "concept_id": str(creation.concept_id) if creation.concept_id else None,
        "content": creation.content,
        "ai_feedback": creation.ai_feedback,
        "ai_use_disclosed": creation.ai_use_disclosed,
        "status": creation.status,
        "peer_reviews": [
            {"id": str(r.id), "scores": r.scores, "comment": r.comment,
             "reviewer_id": str(r.reviewer_id)}
            for r in reviews
        ],
        "created_at": creation.created_at.isoformat(),
    }
