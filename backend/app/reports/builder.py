# -*- coding: utf-8 -*-
"""
=====================================================================
Report Builder — گردآوری داده و ساخت گزارش در چهار فرمت
=====================================================================
داده‌های سامانه (دروس، سرفصل‌ها، محتواها، آزمون‌ها) + وضعیت سرویس
برنامه‌ریزی درسی را جمع می‌کند و بسته به فرمت درخواستی، خروجی
گرافیکی HTML / PowerPoint / PDF / Word تولید می‌کند.
=====================================================================
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import (
    Course,
    CourseTopic,
    EducationalContent,
    Question,
    Quiz,
)
from ..services.scheduler_client import SchedulerClient
from .theme import jalali_today

REPORT_TITLE = "گزارش جامع سامانه هوشمند آموزش"
REPORT_SUBTITLE = "Smart Education — Comprehensive Report"


# ------------------------------------------------------------------
# گردآوری داده از دیتابیس محلی
# ------------------------------------------------------------------
def collect_data(db: Session, include_scheduler: bool = True) -> Dict[str, Any]:
    """
    تمام داده‌های لازم برای گزارش را جمع‌آوری می‌کند.
    بخش سرویس بیرونی اختیاری است و اگر در دسترس نباشد، گزارش
    همچنان با داده‌های محلی ساخته می‌شود.
    """
    courses: List[Course] = (
        db.query(Course).order_by(Course.created_at.asc()).all()
    )

    course_rows: List[Dict[str, Any]] = []
    total_topics = 0
    total_minutes = 0
    total_contents = 0

    for course in courses:
        topics = (
            db.query(CourseTopic)
            .filter(CourseTopic.course_id == course.id)
            .order_by(CourseTopic.sort_order.asc())
            .all()
        )
        topic_minutes = sum(t.session_minute or 0 for t in topics)
        content_count = 0
        for t in topics:
            content_count += (
                db.query(EducationalContent)
                .filter(EducationalContent.topic_id == t.id)
                .count()
            )

        quiz_ids = [
            q.id for q in db.query(Quiz.id).filter(Quiz.course_id == course.id)
        ]
        quiz_count = len(quiz_ids)
        question_count = 0
        if quiz_ids:
            question_count = (
                db.query(Question)
                .filter(Question.quiz_id.in_(quiz_ids))
                .count()
            )

        total_topics += len(topics)
        total_minutes += topic_minutes
        total_contents += content_count

        course_rows.append(
            {
                "id": course.id,
                "title": course.title or "—",
                "description": (course.description or "").strip(),
                "is_active": bool(course.is_active),
                "topic_count": len(topics),
                "minutes": topic_minutes,
                "content_count": content_count,
                "quiz_count": quiz_count,
                "question_count": question_count,
                "topics": [
                    {
                        "title": t.title or "—",
                        "minutes": t.session_minute or 0,
                        "order": t.sort_order or 1,
                        "is_active": bool(t.is_active),
                    }
                    for t in topics
                ],
            }
        )

    # ---- آزمون‌ها و سؤال‌ها ----
    quizzes: List[Quiz] = db.query(Quiz).all()
    quiz_rows: List[Dict[str, Any]] = []
    total_questions = 0
    mc_count = 0
    essay_count = 0

    course_title_map = {c.id: c.title for c in courses}

    for quiz in quizzes:
        questions: List[Question] = (
            db.query(Question).filter(Question.quiz_id == quiz.id).all()
        )
        for q in questions:
            if (q.question_type or "") == "multiple_choice":
                mc_count += 1
            elif (q.question_type or "") == "essay":
                essay_count += 1
        total_questions += len(questions)

        quiz_rows.append(
            {
                "id": quiz.id,
                "title": quiz.title or "—",
                "course": course_title_map.get(quiz.course_id, "—"),
                "question_count": len(questions),
            }
        )

    # ---- نمودارها ----
    top_courses = sorted(
        course_rows, key=lambda c: c["minutes"], reverse=True
    )[:8]

    question_split = [
        {"label": "چهارگزینه‌ای", "value": mc_count},
        {"label": "تشریحی", "value": essay_count},
    ]

    kpis = {
        "courses": len(course_rows),
        "active_courses": sum(1 for c in course_rows if c["is_active"]),
        "topics": total_topics,
        "minutes": total_minutes,
        "contents": total_contents,
        "quizzes": len(quiz_rows),
        "questions": total_questions,
    }

    # ---- وضعیت سرویس بیرونی ----
    scheduler: Optional[Dict[str, Any]] = None
    scheduler_courses: List[Dict[str, Any]] = []
    if include_scheduler:
        client = SchedulerClient()
        health = client.health()
        raw = client.fetch_unique_courses() or []
        scheduler = {
            **health,
            "course_count": len(raw),
        }
        scheduler_courses = [
            SchedulerClient.normalize_course(c) for c in raw[:12]
        ]

    return {
        "title": REPORT_TITLE,
        "subtitle": REPORT_SUBTITLE,
        "date_fa": jalali_today(),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kpis": kpis,
        "courses": course_rows,
        "quizzes": quiz_rows,
        "top_courses": top_courses,
        "question_split": question_split,
        "scheduler": scheduler,
        "scheduler_courses": scheduler_courses,
    }


# ------------------------------------------------------------------
# تولید خروجی بر اساس فرمت
# ------------------------------------------------------------------
def build_report(db: Session, fmt: str) -> tuple[bytes, str, str]:
    """
    گزارش را در فرمت خواسته‌شده می‌سازد.

    خروجی: (بایت‌های فایل, نام فایل, content-type)
    """
    fmt = (fmt or "").strip().lower()

    if fmt == "html":
        from .html_report import build_html
        data = collect_data(db)
        content, filename = build_html(data)
        return content.encode("utf-8"), filename, "text/html; charset=utf-8"

    if fmt == "pptx":
        from .pptx_report import build_pptx
        data = collect_data(db)
        return build_pptx(data)

    if fmt == "pdf":
        from .pdf_report import build_pdf
        data = collect_data(db)
        return build_pdf(data)

    if fmt == "docx":
        from .docx_report import build_docx
        data = collect_data(db)
        return build_docx(data)

    raise ValueError(f"فرمت پشتیبانی‌نشده: {fmt}")
