"""یادگیری مشارکتی / دانشجو تولیدکننده (بخش ۹)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden
from app.core.permissions import is_enrolled
from app.core.security import get_current_user
from app.models.collaboration import StudentCreation
from app.models.identity import User
from app.services import collaboration_service

router = APIRouter(tags=["collaboration"])


class CreationIn(BaseModel):
    course_id: str
    activity_type: str = "EXPLANATION"
    concept_id: str | None = None
    content: dict = {}
    ai_use_disclosed: bool = False


@router.post("/student-creations")
def create_creation(body: CreationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    creation = collaboration_service.create_creation(db, user, body.course_id, body.model_dump())
    db.commit()
    return collaboration_service.creation_payload(db, creation)


@router.get("/student-creations")
def list_creations(course_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.api.v1.assessments import ensure_staff_safe
    from app.core.permissions import get_course_role

    rows = db.query(StudentCreation).filter(StudentCreation.course_id == course_id)
    role = get_course_role(db, user.id, course_id)
    is_staff = role is not None or user.role in ("EDUCATION_ADMIN", "TECH_ADMIN")
    if not is_staff:
        rows = rows.filter(StudentCreation.student_id == user.id)
    return [collaboration_service.creation_payload(db, c) for c in
            rows.order_by(StudentCreation.created_at.desc()).limit(100).all()]


class SubmitIn(BaseModel):
    pass


@router.post("/student-creations/{creation_id}/submit")
def submit_creation(creation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    creation = db.get(StudentCreation, creation_id)
    if creation is None:
        raise forbidden("تولید یافت نشد")
    creation = collaboration_service.submit_creation(db, creation, user)
    db.commit()
    return collaboration_service.creation_payload(db, creation)


class PeerReviewIn(BaseModel):
    scores: dict
    comment: str | None = None


@router.post("/student-creations/{creation_id}/peer-reviews")
def peer_review(creation_id: str, body: PeerReviewIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    creation = db.get(StudentCreation, creation_id)
    if creation is None:
        raise forbidden("تولید یافت نشد")
    if not is_enrolled(db, user.id, creation.course_id):
        raise forbidden("بررسی همتا فقط برای همکلاسی‌ها")
    review = collaboration_service.add_peer_review(db, creation, user, body.model_dump())
    db.commit()
    return {"id": str(review.id), "creation_status": creation.status}


class TeacherReviewIn(BaseModel):
    decision: str
    comment: str | None = None


@router.post("/student-creations/{creation_id}/teacher-reviews")
def teacher_review(creation_id: str, body: TeacherReviewIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """تأیید استاد — هرگز ورود مستقیم به بانک رسمی سؤال (بخش ۹)."""
    creation = db.get(StudentCreation, creation_id)
    if creation is None:
        raise forbidden("تولید یافت نشد")
    creation = collaboration_service.teacher_review(db, creation, user, body.decision, body.comment)
    db.commit()
    return collaboration_service.creation_payload(db, creation)
