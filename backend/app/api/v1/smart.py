"""سرویس‌های یادگیری هوشمند (بخش ۳) — endpoints دسته کامل.

دانشجو: داشبورد، نقاط ضعف، ریشه‌یابی، منابع، کوییز هوشمند، تحلیل پاسخ،
تمرین جبرانی، سبک یادگیری، منحنی فراموشی، فشار شناختی، آموزش‌های کوتاه.
استاد/دستیار: شبیه‌سازی امتحان، صف اعتبارسنجی سؤال‌های تولیدی.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden
from app.core.permissions import Role, ensure_course_role, is_enrolled
from app.core.security import get_current_user
from app.models.identity import User
from app.services import smart_service

router = APIRouter(tags=["smart-learning"])


def _student_access(db: Session, user: User, course_id: str) -> None:
    if not is_enrolled(db, user.id, course_id) and user.role == "STUDENT":
        raise forbidden("دسترسی به این درس ندارید")


class ExamSimulationIn(BaseModel):
    title: str | None = None
    duration_minutes: int | None = None


# ---------------- داشبورد یکپارچه ----------------

@router.get("/me/courses/{course_id}/smart/overview")
def smart_overview(course_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    result = smart_service.overview(db, user.id, course_id)
    db.commit()
    return result


# ---------------- سرویس ۲: نقاط ضعف مفهومی ----------------

@router.get("/me/courses/{course_id}/smart/weaknesses")
def smart_weaknesses(course_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    result = smart_service.weaknesses(db, user.id, course_id)
    db.commit()
    return result


# ---------------- سرویس ۳: ریشه‌یابی مشکلات یادگیری ----------------

@router.get("/me/courses/{course_id}/smart/root-causes")
def smart_root_causes(course_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    result = smart_service.root_causes(db, user.id, course_id)
    db.commit()
    return result


# ---------------- سرویس ۵: پیشنهاد منابع آموزشی ----------------

@router.get("/me/courses/{course_id}/smart/resources")
def smart_resources(course_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    return {"recommendations": smart_service.recommend_resources(db, user.id, course_id)}


# ---------------- سرویس ۶: کوییز هوشمند ----------------

@router.post("/me/courses/{course_id}/smart/quiz")
def smart_quiz(course_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    result = smart_service.create_smart_quiz(db, user, course_id)
    db.commit()
    return result


# ---------------- سرویس ۸: تحلیل پاسخ دانشجو ----------------

@router.get("/me/courses/{course_id}/smart/answer-analysis")
def smart_answer_analysis(course_id: str, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    return smart_service.answer_analysis(db, user.id, course_id)


# ---------------- سرویس ۹: بسته تمرین جبرانی ----------------

@router.get("/me/courses/{course_id}/smart/remedial-pack")
def smart_remedial(course_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    return smart_service.remedial_pack(db, user.id, course_id)


# ---------------- سرویس ۱۰: سبک یادگیری ----------------

@router.get("/me/courses/{course_id}/smart/learning-style")
def smart_style(course_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    return smart_service.learning_style(db, user.id, course_id)


# ---------------- سرویس ۱۱: منحنی فراموشی ----------------

@router.get("/me/courses/{course_id}/smart/forgetting-curve")
def smart_forgetting(course_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    return smart_service.forgetting_curve(db, user.id, course_id)


# ---------------- سرویس ۱۲: فشار شناختی ----------------

@router.get("/me/courses/{course_id}/smart/cognitive-load")
def smart_load(course_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    return smart_service.cognitive_load(db, user.id, course_id)


# ---------------- سرویس ۱۳: آموزش‌های کوتاه و مرحله‌ای ----------------

@router.get("/me/courses/{course_id}/smart/micro-lessons")
def smart_micro(course_id: str, document_id: str | None = None,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _student_access(db, user, course_id)
    return {"lessons": smart_service.micro_lessons(db, course_id, document_id)}


# ---------------- سرویس ۱۵: شبیه‌سازی امتحان (استاد/دستیار) ----------------

@router.post("/courses/{course_id}/smart/exam-simulation")
def smart_exam_simulation(course_id: str, payload: ExamSimulationIn | None = None,
                          db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    ensure_course_role(db, user, course_id, {Role.PROFESSOR, Role.ASSISTANT})
    return smart_service.exam_simulation(db, user, course_id,
                                         payload.model_dump() if payload else {})


# ---------------- سرویس ۱۵: صف اعتبارسنجی (Human-in-the-loop) ----------------

@router.get("/courses/{course_id}/smart/validation-queue")
def smart_validation_queue(course_id: str, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    ensure_course_role(db, user, course_id, {Role.PROFESSOR, Role.ASSISTANT})
    return smart_service.validation_queue(db, course_id)
