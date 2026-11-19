"""موتور ارزیابی (بخش‌های ۵ و ۷): آزمون، تلاش، تطبیق آموزشی و ثبت پاسخ.

- تفکیک «تطبیق آموزشی» از «آزمون روان‌سنجی»: در این نسخه فقط تطبیق آموزشی
  (انتخاب سؤال بعدی بر اساس ضعف) پیاده شده و روان‌سنجی IRT نیست.
- نسخه سؤال هنگام آزمون ثابت می‌ماند و مسیر انتخاب سؤال ثبت می‌شود (AC-07).
- افشای بانک سؤال محدود می‌شود (سقف استفاده از هر سؤال در تلاش‌های دانشجو).
"""
import random

from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.errors import forbidden, not_found, validation_error
from app.models.assessment import (Assessment, Attempt, GradingReview,
                                   Response, ResponseDispute)
from app.models.questions import Question, QuestionConcept, QuestionVersion
from app.services import grading as grading_service
from app.services import learning_service

_ALLOWED_USAGES = {
    "EXAM": {"OFFICIAL_EXAM"},
    "QUIZ": {"QUIZ", "OFFICIAL_EXAM"},
    "PRACTICE": {"PRACTICE", "QUIZ", "OFFICIAL_EXAM"},
}


def create_assessment(db: Session, user, payload: dict) -> Assessment:
    blueprint = payload.get("blueprint") or {}
    sections = blueprint.get("sections") or []
    if not sections:
        raise validation_error("آزمون بدون بخش در Blueprint تعریف نمی‌شود")
    for s in sections:
        if not s.get("concept_ids"):
            raise validation_error("هر بخش Blueprint باید به مفاهیم نگاشت شود")
        if int(s.get("count", 0)) < 1:
            raise validation_error("تعداد سؤال هر بخش باید حداقل ۱ باشد")
    kind = payload.get("kind", "QUIZ")
    policy = payload.get("policy") or {}
    policy.setdefault("feedback", "IMMEDIATE" if kind == "PRACTICE" else "AFTER_FINISH")
    policy.setdefault("allow_hint", kind == "PRACTICE")
    policy.setdefault("shuffle", kind != "EXAM")
    assessment = Assessment(
        course_id=payload["course_id"],
        offering_id=payload.get("offering_id"),
        title=payload.get("title", "ارزیابی جدید"),
        kind=kind,
        mode=payload.get("mode", "FIXED"),
        blueprint={"sections": sections},
        policy=policy,
        duration_minutes=payload.get("duration_minutes"),
        created_by=user.id,
    )
    db.add(assessment)
    db.flush()
    audit(db, user.id, "ASSESSMENT_CREATE", "assessment", assessment.id,
          after={"title": assessment.title, "kind": kind})
    return assessment


def _pool(db: Session, assessment: Assessment):
    return (
        db.query(QuestionVersion)
        .join(Question, QuestionVersion.question_id == Question.id)
        .join(QuestionConcept, QuestionConcept.question_id == Question.id)
        .filter(
            Question.course_id == assessment.course_id,
            Question.status == "APPROVED",
            QuestionVersion.is_current == True,  # noqa: E712
            Question.usage.in_(_ALLOWED_USAGES.get(assessment.kind, {"PRACTICE"})),
        )
    )


def _pick_for_section(db: Session, assessment: Assessment, section: dict, rng: random.Random):
    qvs = (
        _pool(db, assessment)
        .filter(QuestionConcept.concept_id.in_(section["concept_ids"]))
        .all()
    )
    difficulty = section.get("difficulty")
    if difficulty in ("EASY", "MEDIUM", "HARD"):
        exact = [qv for qv in qvs if qv and _q_difficulty(db, qv) == difficulty]
        qvs = exact or qvs
    rng.shuffle(qvs)
    return qvs[: int(section.get("count", 1))]


def _q_difficulty(db: Session, qv: QuestionVersion) -> str:
    q = db.get(Question, qv.question_id)
    return q.difficulty_estimated if q else "MEDIUM"


def start_attempt(db: Session, assessment: Assessment, student) -> Attempt:
    from app.core.permissions import is_enrolled

    if not is_enrolled(db, student.id, assessment.course_id):
        raise forbidden("فقط دانشجوی ثبت‌نام‌شده می‌تواند در ارزیابی شرکت کند")
    open_attempt = (
        db.query(Attempt)
        .filter(Attempt.assessment_id == assessment.id,
                Attempt.student_id == student.id,
                Attempt.status == "IN_PROGRESS")
        .first()
    )
    if open_attempt:
        return open_attempt  # مدیریت قطع اتصال: ادامه تلاش باز قبلی

    rng = random.Random(str(assessment.id))
    qv_ids: list = []
    selection_log: list = []
    if assessment.mode == "FIXED":
        for section in assessment.blueprint.get("sections", []):
            picked = _pick_for_section(db, assessment, section, rng)
            for qv in picked:
                qv_ids.append(str(qv.id))
                selection_log.append({
                    "question_version_id": str(qv.id),
                    "section_concepts": [str(c) for c in section["concept_ids"]],
                    "reason": "طبق Blueprint بخش",
                })
    else:  # ADAPTIVE_PRACTICE
        first = _next_adaptive_question(db, assessment, student.id, asked=set(),
                                        selection_log=selection_log)
        if first is not None:
            qv_ids.append(str(first.id))
    attempt = Attempt(
        assessment_id=assessment.id,
        student_id=student.id,
        question_version_ids=qv_ids,
        selection_log=selection_log,
        adaptive_state={"mode": assessment.mode},
    )
    db.add(attempt)
    db.flush()
    return attempt


def _concept_of_qv(db: Session, qv_id) -> str | None:
    row = db.query(QuestionConcept).filter(QuestionConcept.question_id == _qid(db, qv_id)).first()
    return str(row.concept_id) if row else None


def _qid(db: Session, qv_id):
    qv = db.get(QuestionVersion, qv_id)
    return qv.question_id if qv else None


def _next_adaptive_question(db: Session, assessment: Assessment, student_id,
                            asked: set[str], selection_log: list):
    """انتخاب سؤال بعدی در تطبیق آموزشی: مفهوم ضعیف‌تر اول؛ در صورت ضعف پیش‌نیاز،
    سؤال پیش‌نیاز با دلیل مشخص پیشنهاد می‌شود."""
    from app.models.learning import MasteryEstimate

    blueprint_concepts = [str(c) for s in assessment.blueprint.get("sections", [])
                          for c in s.get("concept_ids", [])]
    estimates = {
        str(m.concept_id): m
        for m in db.query(MasteryEstimate)
        .filter(MasteryEstimate.learner_id == student_id,
                MasteryEstimate.course_id == assessment.course_id,
                MasteryEstimate.concept_id.in_(blueprint_concepts or [None]))
        .all()
    }
    from app.services.concept_service import get_prerequisites

    def rank(cid: str):
        m = estimates.get(cid)
        if m is None or m.status == "UNKNOWN":
            return (2, 0.5, cid)  # شواهد ناکافی → سؤال تشخیصی ساده
        order = {"WEAK": 0, "PARTIAL": 1, "KNOWN": 3}
        return (order.get(m.status, 2), float(m.estimated_mastery or 0.5), cid)

    for cid in sorted(set(blueprint_concepts) - asked, key=rank):
        # اگر پیش‌نیاز این مفهوم ضعیف است، اول پیش‌نیاز تمرین شود
        prereqs = get_prerequisites(db, cid)
        for p in prereqs:
            pm = db.query(MasteryEstimate).filter(
                MasteryEstimate.learner_id == student_id,
                MasteryEstimate.concept_id == p.id).first()
            if pm and pm.status == "WEAK":
                qv = _find_question_for_concept(db, assessment, student_id, str(p.id), asked, easy=True)
                if qv is not None:
                    selection_log.append({"question_version_id": str(qv.id),
                                          "reason": f"مرور پیش‌نیاز «مفهوم هدف» — شواهد ضعف"})
                    return qv
        easy_first = estimates.get(cid) is None or estimates.get(cid).status == "UNKNOWN"
        qv = _find_question_for_concept(db, assessment, student_id, cid, asked, easy=easy_first)
        if qv is not None:
            m = estimates.get(cid)
            reason = ("سؤال تشخیصی — شواهد کافی نیست" if m is None or m.status == "UNKNOWN"
                      else f"تمرین مفهوم ضعیف (وضعیت {m.status})")
            selection_log.append({"question_version_id": str(qv.id), "reason": reason})
            return qv
    return None


def _find_question_for_concept(db: Session, assessment: Assessment, student_id,
                               concept_id: str, asked: set[str], easy: bool):
    qvs = (
        _pool(db, assessment)
        .filter(QuestionConcept.concept_id == concept_id)
        .all()
    )
    # جلوگیری از افشای بیش‌ازحد بانک: سقف تکرار هر سؤال برای دانشجو
    from sqlalchemy import func

    max_exposure = 3
    usage_rows = (
        db.query(Response.question_version_id, func.count(Response.id))
        .join(Attempt, Response.attempt_id == Attempt.id)
        .filter(Attempt.student_id == student_id)
        .group_by(Response.question_version_id)
        .all()
    )
    usage_counts = {str(r[0]): r[1] for r in usage_rows}
    candidates = [qv for qv in qvs
                  if str(qv.id) not in asked
                  and usage_counts.get(str(qv.id), 0) < max_exposure]
    if not candidates:
        return None
    order = {"EASY": 0, "MEDIUM": 1, "HARD": 2}
    candidates.sort(key=lambda qv: order.get(_q_difficulty(db, qv), 1))
    return candidates[0] if easy else candidates[min(1, len(candidates) - 1)]


def advance_adaptive(db: Session, attempt: Attempt) -> str | None:
    """پس از هر پاسخ در حالت تطبیقی، سؤال بعدی انتخاب و ثبت می‌شود."""
    assessment = db.get(Assessment, attempt.assessment_id)
    if assessment.mode != "ADAPTIVE_PRACTICE":
        return None
    asked = set(attempt.question_version_ids or [])
    selection_log = list(attempt.selection_log or [])
    qv = _next_adaptive_question(db, assessment, attempt.student_id, asked, selection_log)
    attempt.selection_log = selection_log
    if qv is None:
        return None  # شرط پایان: پوشش اهداف کامل شد
    qv_ids = list(attempt.question_version_ids or [])
    qv_ids.append(str(qv.id))
    attempt.question_version_ids = qv_ids
    db.flush()
    return str(qv.id)


def record_response(db: Session, attempt: Attempt, qv: QuestionVersion, answer: dict,
                    time_spent_ms: int | None = None, hint_used: bool = False) -> Response:
    from app.models.questions import Question

    question = db.get(Question, qv.question_id)
    qtype = question.type
    if qtype in ("MCQ", "MULTI_SELECT", "TRUE_FALSE", "ORDERING", "MATCHING", "NUMERIC"):
        correctness, details = grading_service.grade_objective(qtype, qv, answer)
        grading, ai_feedback = "AUTO", (details or None)
    elif qtype == "SHORT_ANSWER":
        result = grading_service.grade_short_answer(db, qv, answer)
        correctness, grading, ai_feedback = result["correctness"], result["grading"], result["details"]
    elif qtype in ("ESSAY", "CASE"):
        result = grading_service.grade_essay(db, qv, answer)
        correctness = None
        grading, ai_feedback = result["grading"], result["details"]
        if grading == "AI_SUGGESTED" and result["details"].get("total_score") is not None:
            max_total = float(result["details"].get("max_total") or 1)
            correctness = float(result["details"]["total_score"]) / max_total
    elif qtype == "CODE":
        result = grading_service.grade_code(qv, answer)
        correctness, grading, ai_feedback = None, result["grading"], result["details"]
    else:
        raise validation_error("نوع سؤال پشتیبانی نمی‌شود")

    existing = (
        db.query(Response)
        .filter(Response.attempt_id == attempt.id,
                Response.question_version_id == qv.id)
        .first()
    )
    if existing:  # تلاش مجدد در حالت تمرینی — آخرین پاسخ ملاک
        response = existing
        response.answer = answer
    else:
        response = Response(attempt_id=attempt.id, question_version_id=qv.id)
        db.add(response)
    response.answer = answer
    response.correctness = correctness
    response.grading = grading
    response.ai_feedback = ai_feedback
    response.time_spent_ms = time_spent_ms
    response.hint_used = hint_used
    response.graded_at = utcnow() if grading in ("AUTO", "AI_SUGGESTED") else None
    db.flush()

    concept_id = _concept_of_qv(db, qv.id)
    learning_service.record_event(
        db, attempt.student_id,
        course_id=db.get(Assessment, attempt.assessment_id).course_id,
        event_type="RESPONSE_SUBMITTED",
        concept_id=concept_id,
        question_version_id=qv.id,
        correctness=correctness,
        time_spent_ms=time_spent_ms,
        hint_used=hint_used,
        payload={"question_type": qtype, "attempt_id": str(attempt.id)},
    )
    return response


def finish_attempt(db: Session, attempt: Attempt) -> dict:
    from app.models.assessment import Assessment as A

    assessment = db.get(A, attempt.assessment_id)
    responses = db.query(Response).filter(Response.attempt_id == attempt.id).all()
    scored = [r for r in responses if r.correctness is not None]
    score = round(sum(r.correctness for r in scored), 3)
    max_score = len(attempt.question_version_ids or [])
    attempt.score = score
    attempt.max_score = max_score
    pending = [r for r in responses if r.grading in ("PENDING",)]
    attempt.status = "SUBMITTED" if pending else "GRADED"
    attempt.finished_at = utcnow()

    per_concept: dict = {}
    for r in responses:
        cid = _concept_of_qv(db, r.question_version_id)
        if not cid:
            continue
        agg = per_concept.setdefault(cid, {"correct": 0, "total": 0})
        agg["total"] += 1
        if (r.correctness or 0) >= 1:
            agg["correct"] += 1

    # به‌روزرسانی مدل یادگیری: تسلط، تشخیص و مرور فاصله‌دار
    concept_ids = [cid for cid in per_concept if cid]
    learning_service.recompute_mastery(db, attempt.student_id, assessment.course_id)
    learning_service.build_diagnostics(db, attempt.student_id, assessment.course_id)
    from app.services.planning_service import update_review_schedule

    for r in responses:
        cid = _concept_of_qv(db, r.question_version_id)
        if cid and r.correctness is not None:
            update_review_schedule(db, attempt.student_id, assessment.course_id,
                                   cid, r.correctness, r.hint_used)

    # دشواری تجربی سؤال‌ها (جدا از دشواری تخمینی)
    from sqlalchemy import func

    for qv_id in set(attempt.question_version_ids or []):
        qid = _qid(db, qv_id)
        if not qid:
            continue
        rows = (
            db.query(func.avg(Response.correctness))
            .join(Attempt, Response.attempt_id == Attempt.id)
            .filter(Response.question_version_id == qv_id,
                    Response.correctness.isnot(None))
            .first()
        )
        if rows and rows[0] is not None:
            q = db.get(Question, qid)
            if q:
                q.difficulty_empirical = round(1.0 - float(rows[0]), 3)
    db.flush()
    return {"score": score, "max_score": max_score,
            "per_concept": per_concept, "pending_count": len(pending)}


def human_grading_review(db: Session, response: Response, reviewer, payload: dict) -> Response:
    from app.models.assessment import Assessment, Attempt

    attempt = db.get(Attempt, response.attempt_id)
    assessment = db.get(Assessment, attempt.assessment_id)
    from app.core.permissions import ensure_course_role
    from app.core.permissions import Role

    ensure_course_role(db, reviewer, assessment.course_id,
                       {Role.PROFESSOR, Role.ASSISTANT})
    review = GradingReview(
        response_id=response.id, reviewer_id=reviewer.id,
        rubric_scores=payload.get("scores"),
        final_score=payload.get("final_score"),
        comment=payload.get("comment"),
    )
    db.add(review)
    response.final_score = payload.get("final_score")
    response.grading = "HUMAN"
    audit(db, reviewer.id, "GRADE_REVIEW", "response", response.id,
          before={"grading": response.grading, "ai_feedback": bool(response.ai_feedback)},
          after={"final_score": payload.get("final_score")})
    db.flush()
    return response


def dispute_response(db: Session, response: Response, student, comment: str) -> ResponseDispute:
    dispute = ResponseDispute(response_id=response.id, student_id=student.id, comment=comment)
    db.add(dispute)
    db.flush()
    return dispute


def assessment_payload(db: Session, assessment: Assessment) -> dict:
    creator = assessment.created_by
    return {
        "id": str(assessment.id),
        "course_id": str(assessment.course_id),
        "title": assessment.title,
        "kind": assessment.kind,
        "mode": assessment.mode,
        "blueprint": assessment.blueprint,
        "policy": assessment.policy,
        "duration_minutes": assessment.duration_minutes,
        "status": assessment.status,
        "created_by": str(creator) if creator else None,
        "created_at": assessment.created_at.isoformat(),
    }


def question_for_student(db: Session, qv: QuestionVersion, number: int, policy: dict) -> dict:
    from app.models.questions import Question

    q = db.get(Question, qv.question_id)
    options = [dict(o) for o in (qv.options or [])]
    if policy.get("shuffle") and options:
        options = sorted(options, key=lambda o: str(o.get("key")))
    return {
        "question_version_id": str(qv.id),
        "number": number,
        "type": q.type,
        "body": qv.body,
        "options": [{"key": o.get("key"), "text": o.get("text")} for o in options],
        "policy_help": "راهنمایی مجاز است" if policy.get("allow_hint") else "در این آزمون راهنمایی مجاز نیست",
    }


def aggregate_results(db: Session, assessment: Assessment) -> list[dict]:
    attempts = db.query(Attempt).filter(Attempt.assessment_id == assessment.id).all()
    out = []
    for a in attempts:
        responses = db.query(Response).filter(Response.attempt_id == a.id).all()
        out.append({
            "attempt_id": str(a.id),
            "student_id": str(a.student_id),
            "status": a.status,
            "score": a.score,
            "max_score": a.max_score,
            "responses": len(responses),
            "pending_human": sum(1 for r in responses if r.grading in ("PENDING", "AI_SUGGESTED")),
            "disputes": db.query(ResponseDispute).filter(
                ResponseDispute.response_id.in_([r.id for r in responses] or [None])).count(),
        })
    return out
