"""مدل یادگیری، تسلط و رویدادها (بخش ۶)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden
from app.core.permissions import (Role, ensure_course_role,
                                  ensure_enrolled_or_staff, is_enrolled)
from app.core.security import get_current_user
from app.models.identity import User
from app.services import learning_service

router = APIRouter(tags=["learning"])


@router.get("/me/courses/{course_id}/mastery")
def my_mastery(course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """تسلط شخصی — نبود شواهد با وضعیت «UNKNOWN» نمایش داده می‌شود (AC-08)."""
    if not is_enrolled(db, user.id, course_id) and user.role == "STUDENT":
        raise forbidden("دسترسی به این درس ندارید")
    return learning_service.mastery_payload(db, user.id, course_id)


@router.get("/me/courses/{course_id}/diagnostics")
def my_diagnostics(course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.learning import DiagnosticHypothesis

    if not is_enrolled(db, user.id, course_id) and user.role == "STUDENT":
        raise forbidden("دسترسی به این درس ندارید")
    learning_service.build_diagnostics(db, user.id, course_id)
    db.commit()
    rows = (
        db.query(DiagnosticHypothesis)
        .filter(DiagnosticHypothesis.learner_id == user.id,
                DiagnosticHypothesis.course_id == course_id,
                DiagnosticHypothesis.status == "ACTIVE")
        .all()
    )
    from app.models.concepts import Concept

    out = []
    for h in rows:
        c = db.get(Concept, h.concept_id)
        out.append({
            "id": str(h.id), "concept_id": str(h.concept_id),
            "concept_name": c.name if c else None,
            "hypothesis_type": h.hypothesis_type, "confidence": h.confidence,
            "rationale": h.rationale, "recommended_actions": h.recommended_actions,
        })
    return out


@router.get("/courses/{course_id}/mastery/aggregate")
def aggregate_mastery(course_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """نقشه ضعف کلاس — تجمیعی؛ دسترسی فردی فقط برای مجازها (بخش ۱۵.۳)."""
    from app.core.permissions import get_course_role

    role = get_course_role(db, user.id, course_id)
    if role not in (Role.PROFESSOR, Role.ASSISTANT, Role.GROUP_ADMIN) and \
            user.role not in ("EDUCATION_ADMIN", "TECH_ADMIN"):
        raise forbidden("این گزارش فقط برای کارکنان آموزشی درس است")
    return learning_service.aggregate_mastery(db, course_id)


class LearningEventIn(BaseModel):
    course_id: str
    type: str = "CONTENT_VIEWED"
    payload: dict = {}


@router.post("/learning-events")
def record_event(body: LearningEventIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """ثبت رویداد مشاهده محتوا (داده‌ای برای تحلیل؛ به‌تنهایی شواهد تسلط نیست)."""
    from app.models.learning import LearningEvent

    if not is_enrolled(db, user.id, body.course_id):
        raise forbidden()
    event = learning_service.record_event(
        db, user.id, body.course_id, body.type,
        payload=body.payload,
    )
    db.commit()
    return {"id": str(event.id)}


@router.get("/courses/{course_id}/tutor-reports")
def tutor_reports(course_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """گزارش پاسخ‌های نادرست استاد هوشمند (بخش ۸ — امکان اصلاح توسط استاد)."""
    from app.core.permissions import get_course_role
    from app.models.tutor import TutorMessage, TutorSession

    role = get_course_role(db, user.id, course_id)
    if role not in (Role.PROFESSOR, Role.ASSISTANT) and user.role not in ("EDUCATION_ADMIN",):
        raise forbidden()
    rows = (
        db.query(TutorMessage)
        .join(TutorSession, TutorMessage.session_id == TutorSession.id)
        .filter(TutorSession.course_id == course_id, TutorMessage.reported == True)  # noqa: E712
        .all()
    )
    return [
        {"id": str(m.id), "session_id": str(m.session_id), "content": m.content[:400],
         "report_note": m.report_note, "citations": m.citations}
        for m in rows
    ]
