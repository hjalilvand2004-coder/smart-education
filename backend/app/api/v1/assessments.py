"""ارزیابی: آزمون، تلاش، پاسخ، تصحیح، بازبینی و اعتراض (بخش ۷)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden, not_found, validation_error
from app.core.permissions import (Role, ensure_course_role,
                                  ensure_enrolled_or_staff, is_enrolled)
from app.core.security import get_current_user
from app.models.assessment import (Assessment, Attempt, Response,
                                   ResponseDispute)
from app.models.identity import User
from app.models.questions import QuestionVersion
from app.services import assessment_service

router = APIRouter(tags=["assessment"])


class AssessmentIn(BaseModel):
    course_id: str
    offering_id: str | None = None
    title: str
    kind: str = "QUIZ"
    mode: str = "FIXED"
    blueprint: dict = {}
    policy: dict | None = None
    duration_minutes: int | None = None


@router.post("/assessments")
def create_assessment(body: AssessmentIn, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    ensure_course_role(db, user, body.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    assessment = assessment_service.create_assessment(db, user, body.model_dump())
    db.commit()
    return assessment_service.assessment_payload(db, assessment)


@router.get("/assessments")
def list_assessments(course_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    ensure_enrolled_or_staff(db, user, course_id)
    rows = db.query(Assessment).filter(Assessment.course_id == course_id).all()
    return [assessment_service.assessment_payload(db, a) for a in rows]


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise not_found("ارزیابی یافت نشد")
    ensure_enrolled_or_staff(db, user, assessment.course_id)
    payload = assessment_service.assessment_payload(db, assessment)
    role_ok = ensure_staff_safe(db, user, assessment.course_id)
    if role_ok:
        payload["results"] = assessment_service.aggregate_results(db, assessment)
    return payload


def ensure_staff_safe(db, user, course_id) -> bool:
    from app.core.permissions import get_course_role

    role = get_course_role(db, user.id, course_id)
    return role in (Role.PROFESSOR, Role.ASSISTANT, Role.GROUP_ADMIN) or \
        user.role in ("EDUCATION_ADMIN", "TECH_ADMIN")


@router.post("/assessments/{assessment_id}/attempts")
def start_attempt(assessment_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise not_found("ارزیابی یافت نشد")
    attempt = assessment_service.start_attempt(db, assessment, user)
    db.commit()
    questions = []
    policy = assessment.policy or {}
    for i, qv_id in enumerate(attempt.question_version_ids or [], start=1):
        qv = db.get(QuestionVersion, qv_id)
        questions.append(assessment_service.question_for_student(db, qv, i, policy))
    return {
        "id": str(attempt.id), "status": attempt.status,
        "assessment": assessment_service.assessment_payload(db, assessment),
        "questions": questions,
    }


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    from app.models.assessment import Response

    attempt = db.get(Attempt, attempt_id)
    if attempt is None:
        raise not_found("تلاش یافت نشد")
    if str(attempt.student_id) != str(user.id) and not ensure_staff_safe(db, user, _course_of(db, attempt)):
        raise forbidden("این تلاش متعلق به شما نیست")
    assessment = db.get(Assessment, attempt.assessment_id)
    policy = assessment.policy or {}
    responses = db.query(Response).filter(Response.attempt_id == attempt.id).all()
    answered = {str(r.question_version_id) for r in responses}
    questions = []
    for i, qv_id in enumerate(attempt.question_version_ids or [], start=1):
        qv = db.get(QuestionVersion, qv_id)
        if str(qv_id) in answered:
            continue
        questions.append(assessment_service.question_for_student(db, qv, i, policy))
    return {
        "id": str(attempt.id), "status": attempt.status, "score": attempt.score,
        "max_score": attempt.max_score,
        "selection_log": attempt.selection_log,
        "remaining_questions": questions,
    }


def _course_of(db, attempt) -> str:
    return db.get(Assessment, attempt.assessment_id).course_id


class ResponseIn(BaseModel):
    question_version_id: str
    answer: dict = {}
    time_spent_ms: int | None = None
    hint_used: bool = False


@router.post("/attempts/{attempt_id}/responses")
def record_response(attempt_id: str, body: ResponseIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """ثبت پاسخ — تصحیح بسته به نوع سؤال؛ نتیجه طبق سیاست بازخورد برمی‌گردد."""
    attempt = db.get(Attempt, attempt_id)
    if attempt is None:
        raise not_found("تلاش یافت نشد")
    if str(attempt.student_id) != str(user.id):
        raise forbidden("این تلاش متعلق به شما نیست")
    if attempt.status != "IN_PROGRESS":
        raise validation_error("این تلاش پایان یافته است")
    qv = db.get(QuestionVersion, body.question_version_id)
    if qv is None:
        raise not_found("سؤال یافت نشد")
    if body.question_version_id not in (attempt.question_version_ids or []):
        raise forbidden("این سؤال در تلاش شما نیست")
    assessment = db.get(Assessment, attempt.assessment_id)
    if not assessment.policy.get("allow_hint") and body.hint_used:
        raise forbidden("در این آزمون راهنمایی مجاز نیست")
    response = assessment_service.record_response(
        db, attempt, qv, body.answer, body.time_spent_ms, body.hint_used)
    # در حالت تطبیقی، سؤال بعدی انتخاب و ثبت می‌شود
    next_qv_id = assessment_service.advance_adaptive(db, attempt)
    db.commit()
    payload = {
        "response_id": str(response.id),
        "auto_scored": response.grading == "AUTO",
        "grading": response.grading,
    }
    feedback_policy = (assessment.policy or {}).get("feedback", "IMMEDIATE")
    if feedback_policy == "IMMEDIATE":
        payload.update({
            "correctness": response.correctness,
            "ai_feedback": response.ai_feedback,
        })
        if next_qv_id:
            nqv = db.get(QuestionVersion, next_qv_id)
            remaining = len([q for q in (attempt.question_version_ids or [])])
            payload["next_question"] = assessment_service.question_for_student(
                db, nqv, remaining, assessment.policy or {})
    elif feedback_policy == "AFTER_FINISH" and next_qv_id:
        payload["next_question_id"] = next_qv_id
    return payload


@router.post("/attempts/{attempt_id}/finish")
def finish_attempt(attempt_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    attempt = db.get(Attempt, attempt_id)
    if attempt is None:
        raise not_found("تلاش یافت نشد")
    if str(attempt.student_id) != str(user.id):
        raise forbidden("این تلاش متعلق به شما نیست")
    result = assessment_service.finish_attempt(db, attempt)
    db.commit()
    return result


@router.get("/responses/{response_id}")
def get_response(response_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    response = db.get(Response, response_id)
    if response is None:
        raise not_found("پاسخ یافت نشد")
    attempt = db.get(Attempt, response.attempt_id)
    assessment = db.get(Assessment, attempt.assessment_id)
    is_owner = str(attempt.student_id) == str(user.id)
    if not is_owner and not ensure_staff_safe(db, user, assessment.course_id):
        raise forbidden()
    return {
        "id": str(response.id),
        "question_version_id": str(response.question_version_id),
        "answer": response.answer,
        "correctness": response.correctness,
        "score": response.score,
        "final_score": response.final_score,
        "grading": response.grading,
        "ai_feedback": response.ai_feedback,
        "time_spent_ms": response.time_spent_ms,
        "hint_used": response.hint_used,
        "attempt_id": str(attempt.id),
    }


class GradingReviewIn(BaseModel):
    scores: list | None = None
    final_score: float
    comment: str | None = None


@router.post("/responses/{response_id}/grading-reviews")
def grading_review(response_id: str, body: GradingReviewIn,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """اصلاح/نهایی‌کردن نمره توسط استاد — نمره رسمی طبق سیاست انسانی (AC-10)."""
    response = db.get(Response, response_id)
    if response is None:
        raise not_found("پاسخ یافت نشد")
    response = assessment_service.human_grading_review(db, response, user, body.model_dump())
    db.commit()
    return {"id": str(response.id), "grading": response.grading,
            "final_score": response.final_score}


class DisputeIn(BaseModel):
    comment: str


@router.post("/responses/{response_id}/disputes")
def dispute_response(response_id: str, body: DisputeIn, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """اعتراض دانشجو به ارزیابی — ثبت و پیگیری (AC-10)."""
    response = db.get(Response, response_id)
    if response is None:
        raise not_found("پاسخ یافت نشد")
    attempt = db.get(Attempt, response.attempt_id)
    if str(attempt.student_id) != str(user.id):
        raise forbidden("این پاسخ متعلق به شما نیست")
    dispute = assessment_service.dispute_response(db, response, user, body.comment)
    db.commit()
    return {"id": str(dispute.id), "status": dispute.status}
