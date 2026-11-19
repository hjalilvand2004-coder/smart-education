"""برنامه مطالعه شخصی و مرور فاصله‌دار (بخش‌های ۶.۳ و ۶.۷)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden, not_found
from app.core.permissions import is_enrolled
from app.core.security import get_current_user
from app.models.identity import User
from app.models.planning import StudyActivity, StudyPlan
from app.services import planning_service

router = APIRouter(tags=["planning"])


class StudyPlanIn(BaseModel):
    course_id: str
    exam_date: str | None = None
    weekly_hours: float = 5
    goals: str | None = None
    regenerate: bool = False


@router.post("/study-plans")
def create_plan(body: StudyPlanIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not is_enrolled(db, user.id, body.course_id):
        raise forbidden("برنامه مطالعه فقط برای دانشجوی ثبت‌نام‌شده ساخته می‌شود")
    plan = planning_service.generate_study_plan(db, user, body.course_id, body.model_dump())
    db.commit()
    return planning_service.plan_payload(db, plan)


@router.get("/me/study-plans")
def my_plans(course_id: str | None = None, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    q = db.query(StudyPlan).filter(StudyPlan.student_id == user.id,
                                   StudyPlan.status == "ACTIVE")
    if course_id:
        q = q.filter(StudyPlan.course_id == course_id)
    plan = q.order_by(StudyPlan.created_at.desc()).first()
    if plan is None:
        return None
    return planning_service.plan_payload(db, plan)


class ActivityPatch(BaseModel):
    status: str


@router.patch("/study-activities/{activity_id}")
def patch_activity(activity_id: str, body: ActivityPatch, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """جابه‌جایی یا رد پیشنهاد — امکان پذیرش/انجام/رد هر فعالیت."""
    from app.core.errors import validation_error

    activity = db.get(StudyActivity, activity_id)
    if activity is None:
        raise not_found("فعالیت یافت نشد")
    plan = db.get(StudyPlan, activity.plan_id)
    if str(plan.student_id) != str(user.id):
        raise forbidden("این فعالیت متعلق به شما نیست")
    if body.status not in ("PROPOSED", "ACCEPTED", "DONE", "DISMISSED"):
        raise validation_error("وضعیت نامعتبر است")
    activity.status = body.status
    db.commit()
    return {"id": str(activity.id), "status": activity.status}


@router.get("/me/review-schedule")
def review_schedule(course_id: str | None = None, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return planning_service.get_due_reviews(db, user.id, course_id) if course_id else []
