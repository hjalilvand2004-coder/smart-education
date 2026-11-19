"""برنامه مطالعه شخصی (بخش ۶.۳) و مرور فاصله‌دار (بخش ۶.۷).

- برنامه پس از هر ارزیابی مجدد به‌روزرسانی می‌شود و از تحمیل حجم نامتناسب
  خودداری می‌کند (سقف روزانه)؛ هر فعالیت «دلیل انتخاب» دارد.
- مرور فاصله‌دار: SM-2 ساده‌شده؛ خروجی، زمان پیشنهادی مرور است نه ادعای
  اندازه‌گیری دقیق حافظه.
"""
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.database import ensure_utc, utcnow
from app.models.learning import MasteryEstimate
from app.models.planning import ReviewSchedule, StudyActivity, StudyPlan


# ---------------- مرور فاصله‌دار ----------------

def update_review_schedule(db: Session, learner_id, course_id, concept_id,
                           correctness: float, hint_used: bool) -> ReviewSchedule:
    if correctness >= 1 and not hint_used:
        quality = 5
    elif correctness >= 0.5:
        quality = 3
    else:
        quality = 1
    row = (
        db.query(ReviewSchedule)
        .filter(ReviewSchedule.learner_id == learner_id,
                ReviewSchedule.course_id == course_id,
                ReviewSchedule.concept_id == concept_id)
        .first()
    )
    if row is None:
        row = ReviewSchedule(learner_id=learner_id, course_id=course_id,
                             concept_id=concept_id, repetitions=0,
                             interval_days=1, ease=2.5)
        db.add(row)
    if quality >= 3:
        row.repetitions += 1
        if row.repetitions == 1:
            row.interval_days = 1
        elif row.repetitions == 2:
            row.interval_days = 6
        else:
            row.interval_days = round(row.interval_days * row.ease, 1)
        row.ease = round(min(3.0, max(1.3, row.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))), 2)
    else:
        row.repetitions = 0
        row.interval_days = 1
        row.ease = max(1.3, row.ease - 0.2)
    row.last_quality = quality
    row.last_review_at = utcnow()
    row.next_due_at = utcnow() + timedelta(days=row.interval_days)
    db.flush()
    return row


def get_due_reviews(db: Session, learner_id, course_id, horizon_days: int = 14) -> list[dict]:
    from app.models.concepts import Concept

    now = utcnow()
    rows = (
        db.query(ReviewSchedule, Concept)
        .join(Concept, ReviewSchedule.concept_id == Concept.id)
        .filter(ReviewSchedule.learner_id == learner_id,
                ReviewSchedule.course_id == course_id,
                ReviewSchedule.next_due_at <= now + timedelta(days=horizon_days))
        .order_by(ReviewSchedule.next_due_at)
        .all()
    )
    return [
        {
            "concept_id": str(c.id), "concept_name": c.name,
            "due_at": ensure_utc(rs.next_due_at).isoformat(),
            "overdue": ensure_utc(rs.next_due_at) < now,
            "interval_days": rs.interval_days,
            "repetitions": rs.repetitions,
            "ease": rs.ease,
            "algorithm": rs.algorithm,
        }
        for rs, c in rows
    ]


# ---------------- برنامه مطالعه ----------------

def generate_study_plan(db: Session, student, course_id, payload: dict) -> StudyPlan:
    """ساخت برنامه روزانه از: ضعف‌ها، پیش‌نیازها، مرورهای سررسیدشده و موعد آزمون."""
    from app.models.courses import Course
    from datetime import date

    course = db.get(Course, course_id)
    weekly_hours = float(payload.get("weekly_hours") or 5)
    daily_budget = max(20, min(240, int(weekly_hours * 60 / 7)))
    exam_date = payload.get("exam_date")
    if exam_date:
        if isinstance(exam_date, str):
            exam_date = date.fromisoformat(exam_date)
        days = max(3, (exam_date - date.today()).days)
    else:
        days = 14

    # آرشیو برنامه قبلی
    db.query(StudyPlan).filter(
        StudyPlan.student_id == student.id, StudyPlan.course_id == course_id,
        StudyPlan.status == "ACTIVE").update({"status": "ARCHIVED"}, synchronize_session=False)

    estimates = db.query(MasteryEstimate).filter(
        MasteryEstimate.learner_id == student.id,
        MasteryEstimate.course_id == course_id).all()
    weak = [m for m in estimates if m.status == "WEAK"]
    partial = [m for m in estimates if m.status == "PARTIAL"]
    unknown = [m for m in estimates if m.status == "UNKNOWN"]

    from app.models.concepts import Concept

    concept_names = {c.id: c.name for c in
                     db.query(Concept).filter(Concept.course_id == course_id).all()}
    due = get_due_reviews(db, student.id, course_id, horizon_days=min(days, 14))

    plan = StudyPlan(
        student_id=student.id, course_id=course_id,
        exam_date=exam_date, weekly_hours=weekly_hours,
        goals=payload.get("goals"),
        inputs_snapshot={"daily_budget_minutes": daily_budget, "days": days,
                         "weak": len(weak), "partial": len(partial), "unknown": len(unknown),
                         "due_reviews": len(due)},
        status="ACTIVE",
    )
    db.add(plan)
    db.flush()

    # ترتیب مرور: سررسیدهای عقب‌افتاده → ضعف → پیش‌نیاز‌محور → جزئی → تشخیصی
    overdue = [d for d in due if d["overdue"]]
    upcoming = [d for d in due if not d["overdue"]]
    queue: list[tuple[str, str, str]] = []  # (type, concept_id, title)
    for d in overdue:
        queue.append(("REVIEW", d["concept_id"], f"مرور عقب‌افتاده: {d['concept_name']}"))
    for m in weak:
        nm = concept_names.get(m.concept_id, "مفهوم")
        queue.append(("REVIEW", str(m.concept_id), f"بازخوانی مفهوم: {nm}"))
        queue.append(("PRACTICE", str(m.concept_id), f"تمرین هدایت‌شده: {nm}"))
    for m in partial:
        nm = concept_names.get(m.concept_id, "مفهوم")
        queue.append(("PRACTICE", str(m.concept_id), f"تمرین مستقل: {nm}"))
    for d in upcoming:
        queue.append(("REVIEW", d["concept_id"], f"مرور فاصله‌دار: {d['concept_name']}"))
    for m in unknown:
        nm = concept_names.get(m.concept_id, "مفهوم")
        queue.append(("DIAGNOSTIC", str(m.concept_id), f"کوییز تشخیصی کوتاه: {nm}"))

    minutes_map = {"REVIEW": 30, "PRACTICE": 25, "DIAGNOSTIC": 15, "STUDY": 30}
    day = 0
    used_today = 0
    reasons = {
        "REVIEW": "مرور سررسیدشده/ضعف بر اساس شواهد یادگیری",
        "PRACTICE": "تثبیت مفهوم با تمرین متناسب با وضعیت تسلط",
        "DIAGNOSTIC": "شواهد ناکافی؛ وضعیت نامشخص است و باید سنجیده شود",
    }
    for item in queue:
        t, cid, title = item
        mins = minutes_map[t]
        if used_today + mins > daily_budget:
            day += 1
            used_today = 0
            if day >= days:
                break
        try:
            concept_uuid = uuid.UUID(cid) if cid else None
        except (ValueError, TypeError, AttributeError):
            concept_uuid = None
        db.add(StudyActivity(
            plan_id=plan.id, day_offset=day, title=title, activity_type=t,
            concept_id=concept_uuid,
            estimated_minutes=mins, rationale=reasons[t], status="PROPOSED",
        ))
        used_today += mins

    total = db.query(StudyActivity).filter(StudyActivity.plan_id == plan.id).count()
    plan.rationale_summary = (
        f"برنامه {min(day + 1, days)} روزه با سقف {daily_budget} دقیقه در روز بر اساس "
        f"{len(weak)} مفهوم ضعیف، {len(unknown)} مفهوم بدون شواهد و {len(due)} مرور سررسیدشده ساخته شد؛ "
        f"مجموع {total} فعالیت. پس از هر ارزیابی، برنامه به‌روزرسانی می‌شود."
    )
    db.flush()
    return plan


def plan_payload(db: Session, plan: StudyPlan) -> dict:
    activities = (
        db.query(StudyActivity)
        .filter(StudyActivity.plan_id == plan.id)
        .order_by(StudyActivity.day_offset)
        .all()
    )
    from app.models.concepts import Concept

    names = {str(c.id): c.name for c in
             db.query(Concept).filter(Concept.course_id == plan.course_id).all()}
    return {
        "id": str(plan.id),
        "course_id": str(plan.course_id),
        "exam_date": plan.exam_date.isoformat() if plan.exam_date else None,
        "weekly_hours": plan.weekly_hours,
        "rationale_summary": plan.rationale_summary,
        "inputs": plan.inputs_snapshot,
        "status": plan.status,
        "activities": [
            {
                "id": str(a.id), "day_offset": a.day_offset, "title": a.title,
                "type": a.activity_type,
                "concept_id": str(a.concept_id) if a.concept_id else None,
                "concept_name": names.get(str(a.concept_id)) if a.concept_id else None,
                "estimated_minutes": a.estimated_minutes,
                "rationale": a.rationale, "status": a.status,
            }
            for a in activities
        ],
    }
