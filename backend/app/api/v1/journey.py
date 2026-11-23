"""روتر «مسیر یادگیری» — تجربه منسجم دانشجو و اقدام‌محور استاد (نسخه ۳.۱)."""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden, not_found, validation_error
from app.core.security import get_current_user
from app.models.identity import User
from app.models.journey import STUCK_KINDS
from app.services import journey_service

router = APIRouter(tags=["journey"])


# ---------- تمرکز روزانه ----------

@router.get("/me/courses/{course_id}/today")
def today(course_id: str, db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    return journey_service.daily_focus(db, user, course_id)


# ---------- جلسه یادگیری با زمان انتخابی ----------

class SessionIn(BaseModel):
    minutes: int = Field(ge=5, le=30)


@router.post("/me/courses/{course_id}/learning-sessions")
def start_learning_session(course_id: str, body: SessionIn,
                           db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    out = journey_service.start_session(db, user, course_id, body.minutes)
    db.commit()
    return out


@router.get("/me/courses/{course_id}/learning-sessions/active")
def active_session(course_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return journey_service.get_active_session(db, user.id, course_id)


class SessionActionIn(BaseModel):
    action: str
    step_index: int | None = None


@router.post("/me/learning-sessions/{session_id}/actions")
def session_action(session_id: str, body: SessionActionIn,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    out = journey_service.session_action(db, user, session_id, body.action, body.step_index)
    db.commit()
    return out


# ---------- آمادگی آزمون صادقانه ----------

class ExamPrepIn(BaseModel):
    exam_date: str | None = None
    available_minutes: int | None = None


@router.post("/me/courses/{course_id}/exam-prep")
def create_exam_prep(course_id: str, body: ExamPrepIn,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    out = journey_service.exam_prep(db, user, course_id, body.model_dump())
    db.commit()
    return out


# ---------- نقشه مفاهیم دوحالته ----------

@router.get("/me/courses/{course_id}/concept-map")
def concept_map(course_id: str, mode: str = "simple",
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return journey_service.concept_map(db, user, course_id, mode)


# ---------- «اینجا گیر کردم» ----------

class StuckIn(BaseModel):
    kind: str
    content_version_id: str | None = None
    block_index: int | None = None
    block_anchor: str | None = None
    note: str | None = None
    start_tutor: bool = True
    concept_id: str | None = None


@router.post("/me/courses/{course_id}/stuck-marks", status_code=201)
def mark_stuck(course_id: str, body: StuckIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    out = journey_service.mark_stuck(db, user, course_id, body.model_dump())
    db.commit()
    return out


# ---------- کلینیک خطا ----------

@router.get("/me/courses/{course_id}/error-clinic")
def error_clinic(course_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    out = journey_service.error_clinic(db, user, course_id)
    db.commit()  # upsert دفتر خطا در همین GET ثبت می‌شود
    return out


class AttributionIn(BaseModel):
    explanation: str = Field(min_length=3, max_length=1000)


@router.post("/me/error-notes/{entry_id}/attribution")
def attribute_error(entry_id: str, body: AttributionIn,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    out = journey_service.attribute_error(db, user, entry_id, body.explanation)
    db.commit()
    return out


# ---------- «به من یاد بده» ----------

class TeachBackIn(BaseModel):
    concept_id: str
    modality: str = "TEXT"
    content: str | None = None
    audio_path: str | None = None


@router.post("/me/courses/{course_id}/teach-backs", status_code=201)
def teach_back(course_id: str, body: TeachBackIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    out = journey_service.teach_back(db, user, course_id, body.model_dump())
    db.commit()
    return out


# ---------- ترجیح اعلام‌شده ----------

class PreferenceIn(BaseModel):
    preference: str
    accessibility_needs: list[str] | None = None


@router.post("/me/courses/{course_id}/interaction-preferences")
def set_preference(course_id: str, body: PreferenceIn,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    out = journey_service.set_interaction_preference(db, user, course_id, body.model_dump())
    db.commit()
    return out


# ---------- داشبورد اقدام‌محور استاد ----------

@router.get("/courses/{course_id}/professor-actions")
def professor_actions(course_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    return journey_service.professor_actions(db, user, course_id)
