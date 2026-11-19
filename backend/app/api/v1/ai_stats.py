"""آمار استفاده از هوش مصنوعی: اجرای فرایندها، تولید محتوا، بانک سوال و استاد هوشمند."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden
from app.core.security import get_current_user
from app.models.content import ContentVersion
from app.models.identity import User
from app.models.ops import AIRun, JobRun
from app.models.questions import Question
from app.models.tutor import TutorMessage, TutorSession

router = APIRouter(tags=["ai-stats"])

STAFF_ROLES = ("PROFESSOR", "ASSISTANT", "GROUP_ADMIN",
               "EDUCATION_ADMIN", "TECH_ADMIN", "QUALITY_REVIEWER")


@router.get("/ai-stats/summary")
def ai_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in STAFF_ROLES:
        raise forbidden("آمار هوش مصنوعی فقط برای کارکنان آموزشی فعال است")
    jobs_rows = db.query(JobRun.kind, JobRun.status, func.count(JobRun.id)) \
        .group_by(JobRun.kind, JobRun.status).all()
    jobs: dict[str, dict] = {}
    for kind, status_, count in jobs_rows:
        item = jobs.setdefault(kind, {"total": 0, "SUCCEEDED": 0, "FAILED": 0})
        item["total"] += count
        if status_ in item:
            item[status_] = count
    return {
        "ai_runs": db.query(func.count(AIRun.id)).scalar() or 0,
        "jobs_by_kind": jobs,
        "content_versions": db.query(func.count(ContentVersion.id)).scalar() or 0,
        "questions": db.query(func.count(Question.id)).scalar() or 0,
        "tutor_sessions": db.query(func.count(TutorSession.id)).scalar() or 0,
        "tutor_messages": db.query(func.count(TutorMessage.id)).scalar() or 0,
    }
