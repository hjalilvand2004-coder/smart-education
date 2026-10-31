from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from ..ai_service import generate_questions
from ..security import get_current_user
from ..database import get_db
from ..models import (
    CourseTopic,
    EducationalContent,
    Question,
    Quiz,
    QuizAttempt,
    AIServiceUsage,
)
from ..schemas import (
    AttemptResponse,
    QuizGenerateRequest,
    QuizResponse,
    QuizResultResponse,
    QuizSubmitRequest,
    QuizAdminResponse,
    QuizSubmitResponse,
    AttemptDetailResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/quizzes",
    tags=["Quizzes"],
)


VALID_QUESTION_TYPES = {
    "multiple_choice",
    "essay",
}


def normalize_question_type(value: str | None) -> str:
    """تبدیل مقدار نوع سؤال به مقدار استاندارد داخلی."""
    question_type = (value or "multiple_choice").strip().lower()

    aliases = {
        "multiple_choice": "multiple_choice",
        "multiple-choice": "multiple_choice",
        "mcq": "multiple_choice",
        "test": "multiple_choice",
        "four_choice": "multiple_choice",
        "essay": "essay",
        "descriptive": "essay",
        "written": "essay",
        "تشریحی": "essay",
        "چهارگزینه‌ای": "multiple_choice",
        "چهارگزینه ای": "multiple_choice",
    }

    normalized = aliases.get(question_type, question_type)

    if normalized not in VALID_QUESTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="نوع سؤال نامعتبر است. مقادیر مجاز: multiple_choice یا essay",
        )

    return normalized


def get_latest_content_for_topic(topic_id: int, db: Session) -> EducationalContent | None:
    """آخرین محتوای تولیدشده برای یک سرفصل را برمی‌گرداند."""
    return (
        db.query(EducationalContent)
        .filter(EducationalContent.topic_id == topic_id)
        .order_by(EducationalContent.id.desc())
        .first()
    )


def validate_generated_item(item: dict[str, Any], question_type: str) -> dict[str, Any]:
    """اعتبارسنجی و تمیز کردن خروجی AI پیش از ذخیره در دیتابیس."""
    if not isinstance(item, dict):
        raise ValueError("هر سؤال تولیدشده باید یک شیء (دیکشنری) باشد.")

    question_text = str(item.get("question_text", "")).strip()
    if not question_text:
        raise ValueError("متن یکی از سؤال‌های تولیدشده خالی است.")

    explanation = str(item.get("explanation", "") or "").strip() or None

    if question_type == "essay":
        model_answer = str(
            item.get("model_answer") or item.get("answer") or item.get("sample_answer") or ""
        ).strip()
        if not model_answer:
            model_answer = "پاسخ تشریحی باید بر اساس مطالب تولیدشده ارزیابی شود."

        return {
            "question_text": question_text,
            "question_type": "essay",
            "option_a": None,
            "option_b": None,
            "option_c": None,
            "option_d": None,
            "correct_option": None,
            "model_answer": model_answer,
            "explanation": explanation,
        }

    # چهارگزینه‌ای
    option_a = str(item.get("option_a", "")).strip()
    option_b = str(item.get("option_b", "")).strip()
    option_c = str(item.get("option_c", "")).strip()
    option_d = str(item.get("option_d", "")).strip()

    if not all([option_a, option_b, option_c, option_d]):
        raise ValueError("یکی از سؤال‌های چهارگزینه‌ای فاقد چهار گزینه کامل است.")

    correct_option = str(item.get("correct_option", "A")).strip().upper()
    if correct_option not in {"A", "B", "C", "D"}:
        raise ValueError("گزینه صحیح یکی از سؤال‌های چهارگزینه‌ای معتبر نیست.")

    return {
        "question_text": question_text,
        "question_type": "multiple_choice",
        "option_a": option_a,
        "option_b": option_b,
        "option_c": option_c,
        "option_d": option_d,
        "correct_option": correct_option,
        "model_answer": None,
        "explanation": explanation,
    }


def _log_ai_usage(
    db: Session,
    provider: str,
    model: str,
    request_type: str,
    success: bool,
    error_message: str | None = None,
    tokens_used: int = 0,
    request_duration_ms: int = 0,
    topic_id: int | None = None,
    question_count: int = 0,
) -> None:
    """
    ثبت یک رکورد استفاده از سرویس هوش مصنوعی در دیتابیس.
    """
    usage = AIServiceUsage(
        provider=provider,
        model=model,
        request_type=request_type,
        success=success,
        error_message=error_message,
        tokens_used=tokens_used,
        request_duration_ms=request_duration_ms,
        topic_id=topic_id,
        question_count=question_count,
    )
    db.add(usage)
    db.commit()


@router.post("/generate", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """ایجاد آزمون از آخرین محتوای تولیدشده برای یک سرفصل (فقط استاد)."""
    if request.number_of_questions < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="تعداد سؤال باید حداقل 1 باشد."
        )
    if request.number_of_questions > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="حداکثر تعداد مجاز برای تولید هر آزمون 50 سؤال است."
        )

    question_type = normalize_question_type(getattr(request, "question_type", "multiple_choice"))

    content: EducationalContent | None = None
    if request.content_id is not None:
        content = db.get(EducationalContent, request.content_id)
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="محتوای درخواستی پیدا نشد.")
        if request.topic_id is not None and content.topic_id != request.topic_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="content_id انتخاب‌شده متعلق به topic_id ارسال‌شده نیست.",
            )
    elif request.topic_id is not None:
        content = get_latest_content_for_topic(request.topic_id, db)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="یکی از مقادیر topic_id یا content_id الزامی است.",
        )

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="برای این سرفصل محتوایی پیدا نشد. ابتدا محتوای آموزشی را تولید کنید.",
        )

    topic = db.get(CourseTopic, content.topic_id)
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="سرفصل مربوط به محتوای انتخاب‌شده پیدا نشد."
        )

    if request.course_id is not None and request.course_id != topic.course_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="course_id ارسال‌شده با درس متعلق به این سرفصل مطابقت ندارد.",
        )

    start_time = time.time()
    provider = request.provider or "openai_compatible"
    model = request.model or "gpt-5.6"

    try:
        logger.info(f"Generating {request.number_of_questions} {question_type} questions for topic '{topic.title}'")
        items = generate_questions(
            title=topic.title,
            content=content.body,
            number=request.number_of_questions,
            question_type=question_type,
            difficulty=request.difficulty,
            language=request.language,
            provider=request.provider,
            model=request.model,
        )

        if not isinstance(items, list):
            raise ValueError("خروجی سرویس AI باید یک لیست باشد.")
        if not items:
            raise ValueError("سرویس AI هیچ سؤالی تولید نکرد.")
        if len(items) < request.number_of_questions:
            raise ValueError(
                f"تعداد سؤال تولیدشده کافی نیست. درخواست: {request.number_of_questions}، تولیدشده: {len(items)}"
            )

        validated_items = [validate_generated_item(item, question_type) for item in items[:request.number_of_questions]]
        logger.info(f"Successfully generated {len(validated_items)} valid questions")

        # ثبت لاگ موفق
        duration_ms = int((time.time() - start_time) * 1000)
        tokens_used = sum(len(str(item)) for item in items) // 4  # تخمین تقریبی
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="question_generation",
            success=True,
            tokens_used=tokens_used,
            request_duration_ms=duration_ms,
            topic_id=request.topic_id,
            question_count=len(items),
        )

        type_label = "چهارگزینه‌ای" if question_type == "multiple_choice" else "تشریحی"
        quiz = Quiz(title=f"آزمون {type_label}: {topic.title}", course_id=topic.course_id, topic_id=topic.id)
        db.add(quiz)
        db.flush()

        for item in validated_items:
            question = Question(
                quiz_id=quiz.id,
                content_id=content.id,
                question_text=item["question_text"],
                question_type=item["question_type"],
                option_a=item["option_a"],
                option_b=item["option_b"],
                option_c=item["option_c"],
                option_d=item["option_d"],
                correct_option=item["correct_option"],
                model_answer=item["model_answer"],
                explanation=item["explanation"],
            )
            db.add(question)

        db.commit()

        quiz = db.query(Quiz).options(selectinload(Quiz.questions)).filter(Quiz.id == quiz.id).first()
        logger.info(f"Quiz created with id: {quiz.id}")
        return quiz

    except HTTPException:
        db.rollback()
        raise
    except ValueError as error:
        db.rollback()
        # ثبت لاگ ناموفق
        duration_ms = int((time.time() - start_time) * 1000)
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="question_generation",
            success=False,
            error_message=str(error),
            request_duration_ms=duration_ms,
            topic_id=request.topic_id,
        )
        logger.warning("Validation error in quiz generation: %s", error)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"خطا در ساخت سؤال: {error}")
    except SQLAlchemyError as error:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="question_generation",
            success=False,
            error_message=f"Database error: {str(error)}",
            request_duration_ms=duration_ms,
            topic_id=request.topic_id,
        )
        logger.error("Database error while creating quiz: %s", error)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطا در ذخیره‌سازی آزمون در دیتابیس.")
    except Exception as error:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="question_generation",
            success=False,
            error_message=f"Unexpected error: {str(error)}",
            request_duration_ms=duration_ms,
            topic_id=request.topic_id,
        )
        logger.exception("Unexpected error in generate_quiz: %s", error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطای غیرمنتظره: {type(error).__name__} - {str(error)}",
        )


@router.get("/{quiz_id}", response_model=QuizResponse, status_code=status.HTTP_200_OK)
def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """دریافت یک آزمون به همراه سؤال‌های آن (بدون پاسخ صحیح) - برای دانشجو."""
    if quiz_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="شناسه آزمون نامعتبر است.")

    quiz = db.query(Quiz).options(selectinload(Quiz.questions)).filter(Quiz.id == quiz_id).first()
    if quiz is None:
        logger.warning(f"Quiz with id {quiz_id} not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"آزمون با شناسه {quiz_id} پیدا نشد.")

    logger.info(f"Quiz {quiz_id} retrieved successfully")
    return quiz


@router.get("/{quiz_id}/admin", response_model=QuizAdminResponse, status_code=status.HTTP_200_OK)
def get_quiz_admin(quiz_id: int, db: Session = Depends(get_db)):
    """دریافت یک آزمون با جزئیات کامل شامل پاسخ صحیح سؤال‌ها (برای مدیر/استاد)."""
    if quiz_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="شناسه آزمون نامعتبر است.")

    quiz = db.query(Quiz).options(selectinload(Quiz.questions)).filter(Quiz.id == quiz_id).first()
    if quiz is None:
        logger.warning(f"Quiz with id {quiz_id} not found (admin)")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"آزمون با شناسه {quiz_id} پیدا نشد.")

    return quiz


# ============================================================
# ثبت پاسخ دانشجو
# ============================================================

@router.post("/{quiz_id}/submit", response_model=QuizSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_quiz(quiz_id: int, request: QuizSubmitRequest, db: Session = Depends(get_db)):
    """
    ثبت پاسخ‌های دانشجو در آزمون و محاسبه نمره.
    """
    if quiz_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="شناسه آزمون نامعتبر است.")

    quiz = db.query(Quiz).options(selectinload(Quiz.questions)).filter(Quiz.id == quiz_id).first()
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="آزمون پیدا نشد.")

    questions = quiz.questions
    if not questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="این آزمون سؤالی ندارد.")

    # نگاشت شناسه سؤال به مدل
    question_map = {q.id: q for q in questions}

    # اعتبارسنجی اینکه همه سؤال‌ها پاسخ داده شده‌اند
    answered_question_ids = {ans.question_id for ans in request.answers}
    all_question_ids = set(question_map.keys())
    if answered_question_ids != all_question_ids:
        missing = all_question_ids - answered_question_ids
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"به سؤال‌های زیر پاسخ داده نشده است: {sorted(missing)}"
        )

    # محاسبه نتایج
    correct_count = 0
    total = len(questions)
    essay_count = 0
    has_essay = False
    answers_data = {}

    for ans in request.answers:
        qid = ans.question_id
        question = question_map[qid]
        if question.question_type == "essay":
            has_essay = True
            essay_count += 1
            essay_answer = ans.essay_answer or ""
            answers_data[str(qid)] = {"type": "essay", "answer": essay_answer}
        else:
            selected = ans.selected_option or ""
            is_correct = (selected == question.correct_option)
            if is_correct:
                correct_count += 1
            answers_data[str(qid)] = {"type": "multiple_choice", "selected": selected, "correct": question.correct_option}

    # محاسبه نمره (برای چهارگزینه‌ای)
    multiple_choice_count = total - essay_count
    if multiple_choice_count > 0:
        score = int((correct_count / multiple_choice_count) * 100)
    else:
        score = 0  # اگر همه تشریحی باشند، نمره موقت صفر است

    # ذخیره تلاش
    attempt = QuizAttempt(
        quiz_id=quiz_id,
        student_name=request.student_name.strip(),
        answers_data=json.dumps(answers_data, ensure_ascii=False),
        score=score,
        correct_answers=correct_count,
        total_questions=total,
        essay_answers=essay_count,
        pending_essay_review=has_essay,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    logger.info(f"Quiz attempt saved: id={attempt.id}, student={attempt.student_name}, score={score}")

    return QuizSubmitResponse(
        attempt_id=attempt.id,
        quiz_id=quiz_id,
        student_name=attempt.student_name,
        score=score,
        correct_answers=correct_count,
        total_questions=total,
        pending_essay_review=has_essay,
        message="پاسخ‌های شما ثبت شد." + (" پاسخ‌های تشریحی برای بررسی ارسال شد." if has_essay else ""),
    )


# ============================================================
# دریافت نتایج یک تلاش خاص
# ============================================================

@router.get("/attempts/{attempt_id}", response_model=AttemptDetailResponse, status_code=status.HTTP_200_OK)
def get_attempt(attempt_id: int, db: Session = Depends(get_db)):
    """دریافت جزئیات یک تلاش (نتایج کامل)."""
    if attempt_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="شناسه تلاش نامعتبر است.")

    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="تلاش پیدا نشد.")

    # تبدیل answers_data از JSON به دیکشنری
    answers_dict = None
    if attempt.answers_data:
        try:
            answers_dict = json.loads(attempt.answers_data)
        except json.JSONDecodeError:
            answers_dict = {}

    return AttemptDetailResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        student_name=attempt.student_name,
        score=attempt.score,
        correct_answers=attempt.correct_answers,
        total_questions=attempt.total_questions,
        pending_essay_review=attempt.pending_essay_review,
        answers_data=answers_dict,
        created_at=attempt.created_at,
    )


# ============================================================
# دریافت لیست تلاش‌های یک آزمون
# ============================================================

@router.get("/{quiz_id}/attempts", response_model=list[AttemptResponse], status_code=status.HTTP_200_OK)
def get_quiz_attempts(quiz_id: int, db: Session = Depends(get_db)):
    """دریافت لیست تمام تلاش‌های ثبت‌شده برای یک آزمون (برای استاد)."""
    if quiz_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="شناسه آزمون نامعتبر است.")

    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="آزمون پیدا نشد.")

    attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id).order_by(QuizAttempt.created_at.desc()).all()
    return attempts