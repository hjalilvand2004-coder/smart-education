"""مدل یادگیری: شواهد، تخمین تسلط و فرضیه‌های تشخیصی (بخش ۶).

- روش اولیه: قواعد وزنی با کاهش وزن زمانی (recency decay) و پسینه بتا؛
  مدل‌های دقیق‌تر (BKT) با داده واقعی جایگزین می‌شوند (model_version ثبت می‌شود).
- تخمین‌ها تابع خالص learning_events هستند → قابل بازتولید.
- نبود شواهد = UNKNOWN؛ هرگز «ضعف قطعی» نمایش داده نمی‌شود (AC-08).
- گفتگو با استاد هوشمند منبع قطعی تسلط نیست (وزن صفر در شواهد).
"""
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import ensure_utc, utcnow
from app.models.concepts import Concept, ConceptMisconception
from app.models.learning import (DiagnosticHypothesis, LearningEvent,
                                 MasteryEstimate)
from app.models.questions import Question, QuestionConcept, QuestionVersion
from app.models.assessment import Attempt, Response

MODEL_VERSION = "weighted-rules-v1"
_HALF_LIFE_DAYS = 14


def record_event(db: Session, learner_id, course_id, event_type: str,
                 concept_id=None, question_version_id=None, correctness=None,
                 time_spent_ms=None, hint_used=False, payload=None,
                 offering_id=None) -> LearningEvent:
    event = LearningEvent(
        learner_id=learner_id, course_id=course_id, offering_id=offering_id,
        event_type=event_type, concept_id=concept_id,
        question_version_id=question_version_id,
        correctness=correctness, time_spent_ms=time_spent_ms,
        hint_used=hint_used, payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def _event_weight(event: LearningEvent, now) -> float:
    """وزن شواهد: کاهش نمایی با زمان + کاهش برای پاسخ با راهنما."""
    created = ensure_utc(event.created_at)
    age_days = max(0.0, (now - created).total_seconds() / 86400)
    w = 0.5 ** (age_days / _HALF_LIFE_DAYS)
    if event.hint_used:
        w *= 0.6
    return w


def recompute_mastery(db: Session, learner_id, course_id) -> list[MasteryEstimate]:
    """محاسبه مجدد تسلط همه مفاهیم درس برای یک دانشجو (قابل بازتولید)."""
    from app.models.concepts import Concept as C

    now = utcnow()
    events = (
        db.query(LearningEvent)
        .filter(LearningEvent.learner_id == learner_id,
                LearningEvent.course_id == course_id,
                LearningEvent.correctness.isnot(None))
        .all()
    )
    by_concept: dict = {}
    for e in events:
        if not e.concept_id:
            continue
        by_concept.setdefault(e.concept_id, []).append(e)

    concepts = db.query(C).filter(C.course_id == course_id).all()
    estimates = []
    for c in concepts:
        evs = by_concept.get(c.id, [])
        n_eff = sum(_event_weight(e, now) for e in evs)
        s = sum(_event_weight(e, now) * float(e.correctness) for e in evs)
        raw_count = len(evs)
        min_evidence = get_settings().mastery_min_evidence
        if raw_count < min_evidence or n_eff <= 0:
            estimate_value, status = None, "UNKNOWN"
        else:
            # پسینه بتا با پیشین خنثی Beta(1.5, 1.5)
            estimate_value = (s + 1.5) / (n_eff + 3.0)
            estimate_value = round(min(1.0, max(0.0, estimate_value)), 4)
            status = ("WEAK" if estimate_value < 0.4
                      else "PARTIAL" if estimate_value < 0.75 else "KNOWN")
        row = (
            db.query(MasteryEstimate)
            .filter(MasteryEstimate.learner_id == learner_id,
                    MasteryEstimate.course_id == course_id,
                    MasteryEstimate.concept_id == c.id)
            .first()
        )
        if row is None:
            row = MasteryEstimate(learner_id=learner_id, course_id=course_id, concept_id=c.id)
            db.add(row)
        row.estimated_mastery = estimate_value
        row.status = status
        row.evidence_count = raw_count
        row.uncertainty = {
            "method": "weighted-beta-v1",
            "n_eff": round(n_eff, 3),
            "confidence": round(min(1.0, raw_count / get_settings().mastery_recommend_evidence), 3),
            "half_life_days": _HALF_LIFE_DAYS,
        }
        row.model_version = MODEL_VERSION
        row.last_evidence_at = max((e.created_at for e in evs), default=None)
        row.computed_at = now
        estimates.append(row)
    db.flush()
    return estimates


def build_diagnostics(db: Session, learner_id, course_id) -> list[dict]:
    """شناسایی ضعف و فرضیه ریشه احتمالی (بخش ۶.۲) — خروجی فرضیه آموزشی است،
    نه تشخیص پزشکی/روان‌شناختی؛ در صورت لزوم سؤال تشخیصی پیشنهاد می‌شود."""
    from app.services.concept_service import get_prerequisites

    estimates = (
        db.query(MasteryEstimate)
        .filter(MasteryEstimate.learner_id == learner_id,
                MasteryEstimate.course_id == course_id)
        .all()
    )
    concepts = {str(c.id): c for c in
                db.query(Concept).filter(Concept.course_id == course_id)}
    out = []
    db.query(DiagnosticHypothesis).filter(
        DiagnosticHypothesis.learner_id == learner_id,
        DiagnosticHypothesis.course_id == course_id,
    ).update({"status": "ARCHIVED"}, synchronize_session=False)

    for m in estimates:
        concept = concepts.get(str(m.concept_id))
        if concept is None:
            continue
        hypothesis, confidence, rationale, actions = None, 0.5, "", []

        if m.status == "UNKNOWN" or m.evidence_count < get_settings().mastery_min_evidence:
            hypothesis = "INSUFFICIENT_EVIDENCE"
            confidence = 0.9
            rationale = (f"برای مفهوم «{concept.name}» شواهد کافی وجود ندارد "
                         f"({m.evidence_count} شواهد)؛ وضعیت تسلط نامشخص است، نه ضعف.")
            actions = [{"type": "DIAGNOSTIC_QUIZ", "title": "کوییز کوتاه تشخیصی",
                        "target_id": str(concept.id),
                        "reason": "تعیین وضعیت با چند سؤال کوتاه"}]
        elif m.status == "WEAK":
            weak_prereq = None
            for p in get_prerequisites(db, concept.id):
                pm = db.query(MasteryEstimate).filter(
                    MasteryEstimate.learner_id == learner_id,
                    MasteryEstimate.concept_id == p.id).first()
                if pm and pm.status in ("WEAK", "UNKNOWN"):
                    weak_prereq = (p, pm)
                    break
            if weak_prereq is not None:
                p, pm = weak_prereq
                hypothesis = "PREREQ_WEAK"
                confidence = 0.75
                rationale = (f"ضعف «{concept.name}» احتمالاً از پیش‌نیاز «{p.name}» است؛ "
                             f"وضعیت پیش‌نیاز: {pm.status}.")
                actions = [{"type": "REVIEW", "title": f"مرور پیش‌نیاز: {p.name}",
                            "target_id": str(p.id),
                            "reason": "رفع ضعف پیش‌نیاز معمولاً ضعف مفهوم فعلی را هم برطرف می‌کند"}]
            else:
                misconceptions = db.query(ConceptMisconception).filter(
                    ConceptMisconception.concept_id == concept.id).all()
                mis_stats = _misconception_stats(db, learner_id, misconceptions)
                if mis_stats and mis_stats["wrong_ratio"] >= 0.5:
                    hypothesis = "MISCONCEPTION"
                    confidence = 0.7
                    rationale = (f"در سؤال‌های مرتبط با بدفهمی «{mis_stats['title']}»، "
                                 f"{mis_stats['wrong_ratio']:.0%} پاسخ‌ها نادرست بوده است.")
                    actions = [{"type": "REVIEW", "title": "مطالعه هشدار بدفهمی",
                                "target_id": str(concept.id),
                                "reason": mis_stats["title"]},
                               {"type": "DIAGNOSTIC_QUIZ", "title": "سؤال تشخیصی بدفهمی",
                                "target_id": str(concept.id),
                                "reason": "تأیید فرضیه با سؤال هدفمند"}]
                elif _has_near_miss_pattern(db, learner_id, concept.id):
                    hypothesis = "CALCULATION_ERROR"
                    confidence = 0.6
                    rationale = ("الگوی پاسخ‌ها نشان می‌دهد روش حل درست است اما خطای "
                                 "محاسباتی رخ می‌دهد.")
                    actions = [{"type": "PRACTICE", "title": "تمرین محاسباتی گام‌به‌گام",
                                "target_id": str(concept.id),
                                "reason": "تقویت دقت اجرای گام‌ها"}]
                elif _slow_wrong_pattern(db, learner_id, concept.id):
                    hypothesis = "COMPREHENSION"
                    confidence = 0.55
                    rationale = ("زمان پاسخ بالا همراه با نادرستی؛ احتمال مشکل در درک "
                                 "صورت سؤال یا مفهوم.")
                    actions = [{"type": "REVIEW", "title": "بازخوانی توضیح مفهوم",
                                "target_id": str(concept.id),
                                "reason": "تقویت درک قبل از تمرین"}]
                else:
                    hypothesis = "CURRENT_WEAK"
                    confidence = 0.65
                    rationale = f"شواهد یادگیری، تسلط ضعیف بر «{concept.name}» را نشان می‌دهد."
                    actions = [{"type": "PRACTICE", "title": "بسته تمرین جبرانی",
                                "target_id": str(concept.id),
                                "reason": "تمرین هدایت‌شده و مستقل با بازخورد"}]
        else:
            continue  # PARTIAL/KNOWN → فرضیه فعال لازم نیست

        row = DiagnosticHypothesis(
            learner_id=learner_id, course_id=course_id, concept_id=concept.id,
            hypothesis_type=hypothesis, confidence=confidence,
            rationale=rationale, recommended_actions=actions, status="ACTIVE",
        )
        db.add(row)
        out.append({
            "concept_id": str(concept.id), "concept_name": concept.name,
            "hypothesis_type": hypothesis, "confidence": confidence,
            "rationale": rationale, "recommended_actions": actions,
        })
    db.flush()
    return out


def _misconception_stats(db: Session, learner_id, misconceptions) -> dict | None:
    if not misconceptions:
        return None
    qids = [
        q.id for q in db.query(Question)
        .filter(Question.misconception_id.in_([m.id for m in misconceptions]))
        .all()
    ]
    if not qids:
        return None
    responses = (
        db.query(Response)
        .join(Attempt, Response.attempt_id == Attempt.id)
        .filter(Attempt.student_id == learner_id,
                Response.question_version_id.in_(
                    [qv.id for qv in db.query(QuestionVersion)
                     .filter(QuestionVersion.question_id.in_(qids))]))
        .all()
    )
    if len(responses) < 2:
        return None
    wrong = sum(1 for r in responses if (r.correctness or 0) < 1)
    return {"title": misconceptions[0].title,
            "wrong_ratio": wrong / len(responses), "count": len(responses)}


def _has_near_miss_pattern(db: Session, learner_id, concept_id) -> bool:
    rows = (
        db.query(Response)
        .join(Attempt, Response.attempt_id == Attempt.id)
        .filter(Attempt.student_id == learner_id)
        .all()
    )
    near = [r for r in rows if (r.ai_feedback or {}).get("near_miss")]
    return len(near) >= 2 and all((r.correctness or 0) < 1 for r in near)


def _slow_wrong_pattern(db: Session, learner_id, concept_id) -> bool:
    rows = (
        db.query(Response)
        .join(Attempt, Response.attempt_id == Attempt.id)
        .filter(Attempt.student_id == learner_id)
        .all()
    )
    slow_wrong = [r for r in rows
                  if (r.correctness or 0) < 1 and (r.time_spent_ms or 0) > 120_000]
    return len(slow_wrong) >= 2


def mastery_payload(db: Session, learner_id, course_id) -> list[dict]:
    from app.services.concept_service import get_prerequisites

    recompute_mastery(db, learner_id, course_id)
    estimates = db.query(MasteryEstimate).filter(
        MasteryEstimate.learner_id == learner_id,
        MasteryEstimate.course_id == course_id).all()
    concepts = {str(c.id): c for c in db.query(Concept).filter(Concept.course_id == course_id)}
    out = []
    for m in estimates:
        c = concepts.get(str(m.concept_id))
        if not c:
            continue
        prereqs = []
        for p in get_prerequisites(db, c.id):
            pm = db.query(MasteryEstimate).filter(
                MasteryEstimate.learner_id == learner_id,
                MasteryEstimate.concept_id == p.id).first()
            prereqs.append({"concept_id": str(p.id), "concept_name": p.name,
                            "status": pm.status if pm else "UNKNOWN"})
        out.append({
            "concept_id": str(c.id), "concept_key": c.key, "concept_name": c.name,
            "estimated_mastery": m.estimated_mastery,  # None یعنی نامشخص
            "status": m.status, "evidence_count": m.evidence_count,
            "confidence": (m.uncertainty or {}).get("confidence"),
            "uncertainty": m.uncertainty,
            "last_evidence_at": m.last_evidence_at.isoformat() if m.last_evidence_at else None,
            "model_version": m.model_version,
            "prerequisites": prereqs,
        })
    return out


def aggregate_mastery(db: Session, course_id) -> list[dict]:
    """نقشه ضعف کلاس — تجمیعی و بدون افشای داده فردی بدون مجوز."""
    from app.models.courses import CourseOffering, Enrollment
    from sqlalchemy import func

    student_ids = [
        e.student_id for e in db.query(Enrollment)
        .join(CourseOffering, Enrollment.offering_id == CourseOffering.id)
        .filter(CourseOffering.course_id == course_id).all()
    ]
    estimates = (
        db.query(MasteryEstimate)
        .filter(MasteryEstimate.course_id == course_id,
                MasteryEstimate.learner_id.in_(student_ids or [None]))
        .all()
    )
    by_concept: dict = {}
    for m in estimates:
        by_concept.setdefault(str(m.concept_id), []).append(m)
    concepts = db.query(Concept).filter(Concept.course_id == course_id).all()
    out = []
    for c in concepts:
        rows = by_concept.get(str(c.id), [])
        n = len(rows)
        known = sum(1 for m in rows if m.status == "KNOWN")
        weak = sum(1 for m in rows if m.status == "WEAK")
        unknown = sum(1 for m in rows if m.status == "UNKNOWN")
        values = [float(m.estimated_mastery) for m in rows if m.estimated_mastery is not None]
        out.append({
            "concept_id": str(c.id), "concept_name": c.name,
            "students_count": n,
            "avg_mastery": round(sum(values) / len(values), 3) if values else None,
            "known_ratio": round(known / n, 2) if n else None,
            "weak_ratio": round(weak / n, 2) if n else None,
            "unknown_ratio": round(unknown / n, 2) if n else None,
            "needs_reteach": bool(n and weak / n > 0.5),
        })
    return out
