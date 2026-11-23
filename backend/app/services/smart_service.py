"""سرویس‌های یادگیری هوشمند (بخش ۳ سند نیازمندی‌ها) — دسته کامل.

این ماژول حلقه‌های گمشده ۱۶ سرویس را کامل می‌کند؛ سرویس‌هایی که از قبل
موجودند (تسلط مفهومی، تشخیص ریشه، برنامه مطالعه، آزمون تطبیقی، استاد
هوشمند، یادگیری مشارکتی) از اینجا فراخوانی/تجمیع می‌شوند.

- همه تحلیل‌ها از داده‌های موجود (شواهد یادگیری، تسلط، مرور فاصله‌دار،
  بانک سؤال، محتوا و منابع) استخراج می‌شوند؛ هیچ جدول جدیدی لازم نیست.
- سرویس‌های تحلیلی deterministic و قابل بازتولید هستند.
- شواهد ناکافی = UNKNOWN؛ هرگز «ضعف قطعی» نمایش داده نمی‌شود (AC-08).
- منحنی فراموشی: مدل دوبنگاهی ساده روی فاصله‌های SM-2؛ خروجی «زمان
  پیشنهادی مرور» است نه ادعای اندازه‌گیری حافظه.
"""
import math
import uuid
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import ensure_utc, utcnow
from app.core.errors import not_found, validation_error
from app.models.assessment import Assessment, Attempt, Response
from app.models.concepts import Concept, ConceptMisconception, ConceptRelation
from app.models.content import ContentDocument, ContentVersion
from app.models.learning import LearningEvent, MasteryEstimate
from app.models.planning import ReviewSchedule
from app.models.questions import Question, QuestionConcept, QuestionVersion
from app.models.resources import Resource
from app.services import assessment_service, learning_service
from app.services.concept_service import get_prerequisites

RETENTION_TARGET = 0.70  # آستانه شروع فراموشی فعال
_HALF_LIFE_FACTOR = 3.2  # نیم‌عمر روز = فاصله SM-2 × این ضریب
_EXPECTED_MS = {"EASY": 45_000, "MEDIUM": 90_000, "HARD": 150_000}


# ---------------- ابزار مشترک ----------------

def _course_concepts(db: Session, course_id) -> list[Concept]:
    return db.query(Concept).filter(Concept.course_id == course_id).order_by(Concept.name).all()


def _estimates_map(db: Session, learner_id, course_id) -> dict[str, MasteryEstimate]:
    return {
        str(m.concept_id): m for m in db.query(MasteryEstimate)
        .filter(MasteryEstimate.learner_id == learner_id,
                MasteryEstimate.course_id == course_id).all()
    }


def _downstream_count(db: Session, concept_id) -> int:
    """تعداد مفاهیم وابسته (سرفصل‌هایی که این مفهوم پیش‌نیاز آن‌هاست)."""
    return db.query(ConceptRelation).filter(
        ConceptRelation.from_concept_id == concept_id,
        ConceptRelation.rel_type == "PREREQUISITE_OF").count()


# ---------------- سرویس ۲: شناسایی نقاط ضعف مفهومی ----------------

def weaknesses(db: Session, learner_id, course_id) -> dict:
    learning_service.recompute_mastery(db, learner_id, course_id)
    estimates = _estimates_map(db, learner_id, course_id)
    concepts = _course_concepts(db, course_id)
    out, unknown = [], 0
    for c in concepts:
        m = estimates.get(str(c.id))
        if m is None or m.status == "UNKNOWN":
            unknown += 1
            continue
        if m.status != "WEAK":
            continue
        mastery = float(m.estimated_mastery or 0.0)
        prereq_status = []
        for p in get_prerequisites(db, c.id):
            pm = estimates.get(str(p.id))
            prereq_status.append({"concept_id": str(p.id), "concept_name": p.name,
                                  "status": pm.status if pm else "UNKNOWN"})
        severity = round(1.0 - mastery, 3)
        impact = _downstream_count(db, c.id)
        out.append({
            "concept_id": str(c.id), "concept_name": c.name,
            "estimated_mastery": mastery, "severity": severity,
            "impact_downstream": impact,
            "evidence_count": m.evidence_count,
            "confidence": (m.uncertainty or {}).get("confidence"),
            "prerequisites": prereq_status,
            # هر «ضعف» یک فرضیه آموزشی است؛ سؤال تشخیصی کوتاه آن را تأیید/رد می‌کند
            "nature": "HYPOTHESIS",
            "probe": {"type": "DIAGNOSTIC_QUIZ", "label": "تأیید با کوییز تشخیصی کوتاه",
                      "ref": str(c.id)},
        })
    # شدت × اثر پایین‌دست — مفاهیمی که خراب‌کردنشان گران است اول
    out.sort(key=lambda w: (w["severity"] + 0.2 * w["impact_downstream"], w["severity"]),
             reverse=True)
    return {
        "weak_count": len(out), "unknown_count": unknown,
        "weaknesses": out,
        "summary": (f"{len(out)} مفهوم ضعیف و {unknown} مفهوم بدون شواهد کافی شناسایی شد؛ "
                    "وضعیت «نامشخص» ضعف نیست و با کوییز تشخیصی سنجیده می‌شود."),
    }


# ---------------- سرویس ۳: تشخیص ریشه مشکلات یادگیری (زنجیره ریشه) ----------------

def root_causes(db: Session, learner_id, course_id, max_depth: int = 5) -> list[dict]:
    learning_service.recompute_mastery(db, learner_id, course_id)
    estimates = _estimates_map(db, learner_id, course_id)
    concepts = {str(c.id): c for c in _course_concepts(db, course_id)}

    def weak(cid: str) -> bool:
        m = estimates.get(cid)
        return bool(m and m.status == "WEAK")

    def chain_from(cid: str, seen: set) -> list[list[str]]:
        """همه مسیرهای ضعف از ریشه تا مفهوم هدف (فقط پیش‌نیازهای ضعیف)."""
        paths = []
        for p in get_prerequisites(db, cid):
            pid = str(p.id)
            if pid in seen or not weak(pid):
                continue
            if not get_prerequisites(db, p.id):
                paths.append([pid, cid])  # ریشه: پیش‌نیازی که خودش والد ضعیف ندارد
            else:
                for sub in chain_from(pid, seen | {pid}):
                    paths.append(sub + [cid])
            if len(paths) >= 3:
                break
        return paths

    out = []
    for cid, m in estimates.items():
        if m.status != "WEAK":
            continue
        c = concepts.get(cid)
        if not c:
            continue
        paths = chain_from(cid, {cid}) or [[cid]]
        named = [{"path": [concepts.get(x, Concept(id=uuid.UUID(x), name=x)).name
                           if x in concepts else "?" for x in p],
                  "ids": p}
                 for p in paths[:3]]
        root_id = named[0]["ids"][0]
        out.append({
            "concept_id": cid, "concept_name": c.name,
            "root_concept_id": root_id,
            "root_concept_name": concepts.get(root_id).name if root_id in concepts else None,
            "depth": len(named[0]["ids"]) - 1,
            "chains": named,
            "interpretation": ("ضعف از پیش‌نیازِ پایین‌دست نشأت گرفته؛ ریشه را اول درمان کنید."
                               if len(named[0]["ids"]) > 1 else
                               "ضعف در همین مفهوم است؛ پیش‌نیاز ضعیفی یافت نشد."),
        })
    out.sort(key=lambda r: (-r["depth"], r["concept_name"]))
    return out


# ---------------- سرویس ۵: پیشنهاد منابع آموزشی (Recommender) ----------------

def recommend_resources(db: Session, learner_id, course_id, limit: int = 8) -> list[dict]:
    weak = weaknesses(db, learner_id, course_id)["weaknesses"]
    weak_ids = {w["concept_id"] for w in weak}
    if not weak_ids:
        return []
    weak_names = {w["concept_id"]: w["concept_name"] for w in weak}
    out = []

    # ۱) محتوای منتشرشده مرتبط با مفاهیم ضعیف (نگاشت scope و TopicConcept)
    from app.models.concepts import TopicConcept

    topic_ids = [str(tc.topic_id) for tc in db.query(TopicConcept).filter(
        TopicConcept.concept_id.in_([uuid.UUID(x) for x in weak_ids])).all()]
    docs = db.query(ContentDocument).filter(ContentDocument.course_id == course_id).all()
    pub_versions = {v.document_id: v for v in db.query(ContentVersion).filter(
        ContentVersion.status == "PUBLISHED").all()}
    for d in docs:
        v = pub_versions.get(d.id)
        if v is None:
            continue
        scope = d.scope or {}
        matched = [x for x in (scope.get("concept_ids") or []) if str(x) in weak_ids]
        topic_hit = [t for t in (scope.get("topic_ids") or []) if str(t) in topic_ids]
        if matched or topic_hit:
            names = [weak_names[str(x)] for x in matched if str(x) in weak_names]
            out.append({
                "kind": "CONTENT", "title": d.title,
                "ref_id": str(v.id), "url": f"/course/{course_id}/content/{v.id}",
                "matched_concepts": names or weak_names.get(topic_hit[0] if topic_hit else "", ""),
                "reason": "محتوای منتشرشده مرتبط با مفاهیم ضعیف شما",
            })

    # ۲) منابع درس (کتاب/جزوه/ویدیو) با تطابق واژگانی عنوان با نام مفهوم ضعیف
    resources = db.query(Resource).filter(
        Resource.course_id == course_id,
        Resource.status == "AVAILABLE",
        Resource.contains_exam_material == False,  # noqa: E712 — AC-09
    ).all()
    for r in resources:
        hit = [name for name in weak_names.values()
               if name and any(part in (r.title or "") for part in name.split() if len(part) > 2)]
        if hit or not out:  # در نبود تطابق دقیق، منابع اصلی درس پیشنهاد می‌شوند
            out.append({
                "kind": r.kind, "title": r.title,
                "ref_id": str(r.id), "url": r.external_url,
                "matched_concepts": hit,
                "reason": ("منبع درس مرتبط با مفاهیم ضعیف" if hit
                           else "منبع اصلی درس برای مطالعه پایه"),
            })
    return out[:limit]


# ---------------- سرویس ۶: کوییز هوشمند ----------------

def create_smart_quiz(db: Session, student, course_id) -> dict:
    """ساخت خودکار کوییز هدفمند: مفاهیم ضعیف (متوسط) و بدون شواهد (آسان/تشخیصی)."""
    from app.models.courses import Course

    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    learning_service.recompute_mastery(db, student.id, course_id)
    estimates = _estimates_map(db, student.id, course_id)
    concepts = _course_concepts(db, course_id)

    weak = [str(c.id) for c in concepts
            if (estimates.get(str(c.id)) and estimates[str(c.id)].status == "WEAK")]
    unknown = [str(c.id) for c in concepts
               if estimates.get(str(c.id)) is None or estimates[str(c.id)].status == "UNKNOWN"]

    sections = []
    for cid in weak[:4]:
        sections.append({"concept_ids": [cid], "count": 2, "difficulty": "MEDIUM"})
    for cid in (unknown[:3] if not weak else unknown[:2]):
        sections.append({"concept_ids": [cid], "count": 1, "difficulty": "EASY"})
    if not sections:  # همه مسلط‌اند → مرور تثبیتی سبک
        sections = [{"concept_ids": [str(c.id) for c in concepts[:3]],
                     "count": 1, "difficulty": "MEDIUM"}]

    assessment = assessment_service.create_assessment(db, student, {
        "course_id": str(course_id),
        "title": f"کوییز هوشمند — {course.title}",
        "kind": "PRACTICE", "mode": "ADAPTIVE_PRACTICE",
        "blueprint": {"sections": sections},
        "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": True},
    })
    attempt = assessment_service.start_attempt(db, assessment, student)
    qv_ids = attempt.question_version_ids or []
    first = None
    if qv_ids:
        qv = db.get(QuestionVersion, uuid.UUID(qv_ids[0]))
        first = assessment_service.question_for_student(db, qv, 1, assessment.policy or {})
    return {
        "assessment_id": str(assessment.id), "attempt_id": str(attempt.id),
        "mode": assessment.mode, "section_count": len(sections),
        "targeted": {"weak": weak[:4], "unknown": unknown[:3]},
        "first_question": first,
        "url": f"/quiz/{assessment.id}",
        "note": "سؤال بعدی بر اساس پاسخ‌ها و پیش‌نیازهای ضعیف انتخاب می‌شود.",
    }


# ---------------- سرویس ۸: تحلیل پاسخ دانشجو ----------------

def answer_analysis(db: Session, learner_id, course_id) -> dict:
    rows = (
        db.query(Response, Question, QuestionVersion)
        .join(Attempt, Response.attempt_id == Attempt.id)
        .join(Assessment, Attempt.assessment_id == Assessment.id)
        .join(QuestionVersion, Response.question_version_id == QuestionVersion.id)
        .join(Question, QuestionVersion.question_id == Question.id)
        .filter(Attempt.student_id == learner_id, Assessment.course_id == course_id)
        .all()
    )
    graded = [(r, q, qv) for r, q, qv in rows if r.correctness is not None]
    if not graded:
        return {"status": "UNKNOWN", "total": 0,
                "note": "هنوز پاسخ نمره‌دار ثبت نشده؛ پس از کوییز/آزمون تحلیل ساخته می‌شود."}

    total = len(graded)
    correct = sum(1 for r, _, _ in graded if r.correctness >= 1)
    times = [r.time_spent_ms for r, _, _ in graded if r.time_spent_ms]
    by_diff, by_type, per_concept = {}, {}, {}
    fast_wrong = slow_correct = slow_wrong = hints = near_miss = 0
    for r, q, _ in graded:
        exp = _EXPECTED_MS.get(q.difficulty_estimated, 90_000)
        t = r.time_spent_ms or exp
        ok = r.correctness >= 1
        by_diff.setdefault(q.difficulty_estimated, [0, 0])
        by_diff[q.difficulty_estimated][0] += 1
        by_diff[q.difficulty_estimated][1] += 1 if ok else 0
        by_type.setdefault(q.type, [0, 0])
        by_type[q.type][0] += 1
        by_type[q.type][1] += 1 if ok else 0
        if t < exp / 2 and not ok:
            fast_wrong += 1
        elif t > exp * 1.5 and ok:
            slow_correct += 1
        elif t > exp * 1.5 and not ok:
            slow_wrong += 1
        hints += 1 if r.hint_used else 0
        near_miss += 1 if (r.ai_feedback or {}).get("near_miss") else 0

    # تجمیع مفهومی
    concepts_acc: dict[str, list[int]] = {}
    for r, q, qv in graded:
        row = db.query(QuestionConcept).filter(
            QuestionConcept.question_id == qv.question_id).first()
        if not row:
            continue
        agg = concepts_acc.setdefault(str(row.concept_id), [0, 0])
        agg[0] += 1
        agg[1] += 1 if r.correctness >= 1 else 0
    concept_names = {str(c.id): c.name for c in _course_concepts(db, course_id)}

    insights = []
    if fast_wrong >= 2:
        insights.append(f"{fast_wrong} پاسخ سریع‌و‌نادرست: احتمال بی‌دقتی در خواندن صورت سؤال.")
    if slow_wrong >= 2:
        insights.append(f"{slow_wrong} پاسخ کند‌و‌نادرست: نشانه مشکل در درک مفهوم، نه دقت.")
    if slow_correct >= 2:
        insights.append(f"{slow_correct} پاسخ صحیحِ کند: دانش وجود دارد اما اتوماسیون کم است؛ تمرین زمان‌دار توصیه می‌شود.")
    if near_miss >= 2:
        insights.append(f"{near_miss} پاسخ نزدیک‌به‌صحیح: روش حل درست است؛ روی گام آخر تمرین کنید.")
    if hints and correct / total < 0.5:
        insights.append("نرخ استفاده از راهنما همراه با دقت پایین: مرور محتوا پیش از تمرین لازم است.")
    if not insights:
        insights.append("الگوی پاسخ‌ها در محدوده طبیعی است؛ برای تثبیت، مرور فاصله‌دار را ادامه دهید.")

    return {
        "status": "OK", "total": total,
        "accuracy": round(correct / total, 3),
        "avg_time_ms": int(sum(times) / len(times)) if times else None,
        "by_difficulty": {k: {"total": v[0], "correct": v[1],
                              "accuracy": round(v[1] / v[0], 2)}
                          for k, v in by_diff.items()},
        "by_type": {k: {"total": v[0], "correct": v[1]} for k, v in by_type.items()},
        "patterns": {"fast_wrong": fast_wrong, "slow_correct": slow_correct,
                     "slow_wrong": slow_wrong, "hint_used": hints, "near_miss": near_miss},
        "per_concept": [{"concept_id": cid, "concept_name": concept_names.get(cid),
                         "total": v[0], "accuracy": round(v[1] / v[0], 2)}
                        for cid, v in concepts_acc.items()],
        "insights": insights,
    }


# ---------------- سرویس ۹: بسته تمرین جبرانی ----------------

def remedial_pack(db: Session, learner_id, course_id, per_concept: int = 3) -> dict:
    weak = weaknesses(db, learner_id, course_id)["weaknesses"][:5]
    if not weak:
        return {"status": "NONE", "note": "مفهوم ضعیفی برای تمرین جبرانی نیست — ادامه مرور فاصله‌دار."}

    usage_rows = (
        db.query(Response.question_version_id, func.count(Response.id))
        .join(Attempt, Response.attempt_id == Attempt.id)
        .filter(Attempt.student_id == learner_id)
        .group_by(Response.question_version_id).all()
    )
    exposure = {str(r[0]): r[1] for r in usage_rows}
    order = {"EASY": 0, "MEDIUM": 1, "HARD": 2}
    pack, total_minutes = [], 0
    for w in weak:
        qvs = (
            db.query(QuestionVersion)
            .join(Question, QuestionVersion.question_id == Question.id)
            .join(QuestionConcept, QuestionConcept.question_id == Question.id)
            .filter(Question.course_id == course_id,
                    Question.status == "APPROVED",
                    Question.usage.in_(("PRACTICE", "QUIZ")),
                    QuestionConcept.concept_id == uuid.UUID(w["concept_id"]),
                    QuestionVersion.is_current == True)  # noqa: E712
            .all()
        )
        picked = sorted([q for q in qvs if exposure.get(str(q.id), 0) < 3],
                        key=lambda q: order.get(_diff(db, q), 1))[:per_concept]
        misconceptions = db.query(ConceptMisconception).filter(
            ConceptMisconception.concept_id == uuid.UUID(w["concept_id"])).all()
        items = []
        for qv in picked:
            q = db.get(Question, qv.question_id)
            items.append({
                "question_version_id": str(qv.id), "type": q.type,
                "difficulty": q.difficulty_estimated, "body": qv.body,
                "options": [{"key": o.get("key"), "text": o.get("text")}
                            for o in (qv.options or [])],
                "explanation_after_answer": bool(qv.explanation),
            })
            total_minutes += 8
        hint = None
        if misconceptions:
            hint = (misconceptions[0].correction_hint
                    or f"هشدار بدفهمی: {misconceptions[0].title}")
        pack.append({
            "concept_id": w["concept_id"], "concept_name": w["concept_name"],
            "severity": w["severity"],
            "review_hint": hint or "ابتدا توضیح مفهوم را بازخوانی کنید، سپس تمرین کنید.",
            "misconception": misconceptions[0].title if misconceptions else None,
            "questions": items,
        })
        total_minutes += 12
    return {
        "status": "OK", "concepts": pack,
        "estimated_minutes": total_minutes,
        "note": ("هر مفهوم: بازخوانی کوتاه → تمرین آسان → تمرین متوسط. "
                 "پس از پایان، تسلط و برنامه مطالعه به‌روزرسانی می‌شود."),
    }


def _diff(db: Session, qv: QuestionVersion) -> str:
    q = db.get(Question, qv.question_id)
    return q.difficulty_estimated if q else "MEDIUM"


# ---------------- سرویس ۱۰: الگوی تعامل و ترجیحات (بازطراحی علمی) ----------------

_STYLE_WEIGHTS = {
    "CONTENT_VIEWED": "VISUAL", "RESOURCE_VIEWED": "VISUAL",
    "PRACTICE_COMPLETED": "PRACTICAL", "RESPONSE_SUBMITTED": "PRACTICAL",
    "TUTOR_MESSAGE": "CONVERSATIONAL",
}
_STYLE_LABELS = {
    "VISUAL": "الگوی کنونی شما خوانشی است — بیشتر با متن و قطعه‌های آموزشی کار می‌کنید",
    "PRACTICAL": "الگوی کنونی شما تمرین‌محور است — یادگیری را با حل مسئله جلو می‌برید",
    "CONVERSATIONAL": "الگوی کنونی شما گفتگومحور است — با پرسش و بازگویی یاد می‌گیرید",
}
_STYLE_TIPS = {
    "VISUAL": "قطعه‌های آموزشی کوتاه و خلاصه‌نویسی پس از هر مطالعه.",
    "PRACTICAL": "کوییز هوشمند و بسته تمرین جبرانی را پیش از مرور محتوا شروع کنید.",
    "CONVERSATIONAL": "از استاد هوشمند بپرسید و توضیح‌ها را با کلام خود بازگو کنید («به من یاد بده»).",
}


def learning_style(db: Session, learner_id, course_id) -> dict:
    """الگوی تعامل و ترجیحات — «قابل تغییر»، نه برچسب ثابت یادگیری.

    این تحلیل فقط رفتار مشاهده‌شده را توصیف می‌کند و ادعا نمی‌کند دانشجو با چه
    رسانه‌ای «بهتر یاد می‌گیرد»؛ شخصی‌سازی بر پایه عملکرد، هدف، ترجیح اعلام‌شده
    (POST /me/interaction-preferences) و نیاز دسترس‌پذیری انجام می‌شود."""
    events = db.query(LearningEvent).filter(
        LearningEvent.learner_id == learner_id,
        LearningEvent.course_id == course_id).all()
    declared = None
    for e in reversed(events):
        if e.event_type == "PREFERENCE_SET" and e.payload:
            declared = e.payload
            break
    if len(events) < 5:
        return {"status": "UNKNOWN", "event_count": len(events),
                "model": "interaction-pattern-v2", "declared_preference": declared,
                "note": "شواهد تعامل ناکافی است؛ پس از چند جلسه مطالعه/تمرین تحلیل می‌شود."}
    scores = {"VISUAL": 0.0, "PRACTICAL": 0.0, "CONVERSATIONAL": 0.0}
    for e in events:
        style = _STYLE_WEIGHTS.get(e.event_type)
        if style:
            scores[style] += 1.0
    responses = [e for e in events if e.event_type == "RESPONSE_SUBMITTED"
                 and e.correctness is not None]
    if responses:
        acc = sum(float(e.correctness) for e in responses) / len(responses)
        avg_s = sum((e.time_spent_ms or 60_000) for e in responses) / len(responses) / 1000
        if avg_s < 60 and acc >= 0.6:
            scores["PRACTICAL"] += 2.0  # پردازش سریع و دقیق → تمرین‌محور
        elif avg_s > 120:
            scores["VISUAL"] += 1.0    # دقت و تأمل → خوانشی
    total = sum(scores.values()) or 1.0
    dist = {k: round(v / total, 3) for k, v in scores.items()}
    dominant = max(dist, key=dist.get)
    return {
        "status": "OK", "event_count": len(events),
        "model": "interaction-pattern-v2",
        "distribution": dist, "dominant_style": dominant,
        "label": _STYLE_LABELS[dominant],
        "recommendation": _STYLE_TIPS[dominant],
        "declared_preference": declared,
        "is_fixed_label": False,
        "changeable_note": ("این الگوی رفتار مشاهده‌شده است، نه توانایی ثابت شما؛ "
                            "با ترجیح اعلام‌شده یا نیاز دسترس‌پذیری، توصیه‌ها عوض می‌شود."),
        "note": "الگوی تعامل تخمین رفتاری است و با داده بیشتر به‌روزرسانی می‌شود.",
    }


# ---------------- سرویس ۱۱: پیش‌بینی فراموشی مطالب ----------------

def forgetting_curve(db: Session, learner_id, course_id) -> dict:
    now = ensure_utc(utcnow())
    rows = (
        db.query(ReviewSchedule, Concept)
        .join(Concept, ReviewSchedule.concept_id == Concept.id)
        .filter(ReviewSchedule.learner_id == learner_id,
                ReviewSchedule.course_id == course_id).all()
    )
    estimates = _estimates_map(db, learner_id, course_id)
    out = []
    for rs, c in rows:
        half_life = max(0.5, float(rs.interval_days) * _HALF_LIFE_FACTOR)
        m = estimates.get(str(c.id))
        if rs.last_review_at:
            elapsed = max(0.0, (now - ensure_utc(rs.last_review_at)).total_seconds() / 86400)
            retention = 2 ** (-elapsed / half_life)
            days_to_target = half_life * math.log2(1 / RETENTION_TARGET)
            predicted_review = ensure_utc(rs.last_review_at) + timedelta(days=days_to_target)
        else:
            retention, predicted_review = None, rs.next_due_at
        out.append({
            "concept_id": str(c.id), "concept_name": c.name,
            "mastery_status": m.status if m else "UNKNOWN",
            "last_review_at": ensure_utc(rs.last_review_at).isoformat() if rs.last_review_at else None,
            "interval_days": rs.interval_days, "repetitions": rs.repetitions,
            "retention_now": round(retention, 3) if retention is not None else None,
            "retention_target": RETENTION_TARGET,
            "predicted_review_at": predicted_review.isoformat(),
            "overdue_for_review": bool(retention is not None and retention < RETENTION_TARGET)
                                  or ensure_utc(rs.next_due_at) < now,
            "algorithm": rs.algorithm,
        })
    out.sort(key=lambda x: (x["retention_now"] if x["retention_now"] is not None else 2.0))
    urgent = [x for x in out if x["overdue_for_review"]]
    return {
        "concepts": out, "urgent_count": len(urgent),
        "summary": (f"{len(urgent)} مفهوم به مرور فوری نیاز دارد؛ "
                    "پیش‌بینی بر پایه مدل فراموشی دوبنگاهی روی فاصله‌های SM-2 است."),
        "scheduling_vs_memory_note": ("این خروجی «زمان‌بندی پیشنهادی مرور» است؛ ادعای "
                                      "اندازه‌گیری حافظه واقعی نیست و با ارزیابی دوره‌ای "
                                      "کالیبره می‌شود."),
    }


# ---------------- سرویس ۱۲: نشانه‌های دشواری (بازطراحی علمی) ----------------

def cognitive_load(db: Session, learner_id, course_id) -> dict:
    """نشانه‌های دشواری فعالیت — شاخص غیرمستقیم از زمان/خطا/راهنما.

    زمان پاسخ معادل «فشار ذهنی» نیست (کندی اینترنت، وقفه محیطی، دشواری زبان یا
    نیاز دسترس‌پذیری زمان را بالا می‌برند)؛ بنابراین خروجی با نام‌گذاری محتاطانه
    «نشانه‌های دشواری» همراه با پرسش خودگزارش کوتاه ارائه می‌شود."""
    rows = (
        db.query(Response, Question)
        .join(Attempt, Response.attempt_id == Attempt.id)
        .join(Assessment, Attempt.assessment_id == Assessment.id)
        .join(QuestionVersion, Response.question_version_id == QuestionVersion.id)
        .join(Question, QuestionVersion.question_id == Question.id)
        .filter(Attempt.student_id == learner_id, Assessment.course_id == course_id,
                Response.correctness.isnot(None), Response.time_spent_ms.isnot(None))
        .order_by(Response.graded_at.desc())
        .limit(30).all()
    )
    if len(rows) < 3:
        return {"status": "UNKNOWN", "sample": len(rows),
                "model": "difficulty-signals-v2",
                "note": "برای تحلیل نشانه‌های دشواری به حداقل ۳ پاسخ زمان‌دار نیاز است."}
    ratios, wrong, hints = [], 0, 0
    for r, q in rows:
        exp = _EXPECTED_MS.get(q.difficulty_estimated, 90_000)
        ratios.append(min(2.5, r.time_spent_ms / exp))
        wrong += 1 if r.correctness < 1 else 0
        hints += 1 if r.hint_used else 0
    n = len(rows)
    temporal = sum(ratios) / n / 2.0                     # 0..1 (۲ برابر انتظار = بیشینه)
    error_p = (wrong / n) * 0.8                          # نرخ خطا
    hint_p = (hints / n) * 0.5
    index = int(round(100 * max(0.0, min(1.0, 0.5 * temporal + 0.3 * error_p + 0.2 * hint_p))))
    band = "LOW" if index < 35 else "MEDIUM" if index <= 65 else "HIGH"
    rec = {
        "LOW": ("نشانه‌های دشواری کم است؛ برای پیشگیری از افت انگیزه، دشواری تمرین‌ها "
                "را یک پله بالا ببرید.", "HARD"),
        "MEDIUM": ("نشانه‌های دشواری در محدوده متعادل است؛ همین روند ادامه دارد.", "MEDIUM"),
        "HIGH": ("نشانه‌های دشواری بالاست: یک مثال ساده‌تر یا قطعه‌های کوتاه‌تر را "
                 "امتحان کن؛ اگر مشکل از سرعت اینترنت یا شرایط محیطی بود، نادیده‌اش بگیر.", "EASY"),
    }[band]
    return {
        "status": "OK", "sample": n, "load_index": index, "band": band,
        "model": "difficulty-signals-v2",
        "components": {"time_pressure": round(temporal, 2),
                       "error_rate": round(wrong / n, 2),
                       "hint_rate": round(hints / n, 2)},
        "recommendation": rec[0], "suggested_difficulty": rec[1],
        "self_report_question": ("نشانه‌هایی از دشواری در این فعالیت دیده می‌شود؛ "
                                 "آیا ترجیح می‌دهی یک مثال ساده‌تر ببینی؟"),
        "confounds_note": ("زمان پاسخ می‌تواند از کندی اینترنت، وقفه محیطی، دشواری زبان "
                           "یا نیاز دسترس‌پذیری باشد و لزوماً «فشار ذهنی» نیست."),
        "note": "شاخص غیرمستقیم از زمان پاسخ نسبت به دشواری سؤال + نرخ خطا و راهنما ساخته می‌شود.",
    }


# ---------------- سرویس ۱۳: تولید آموزش‌های کوتاه و مرحله‌ای ----------------

def micro_lessons(db: Session, course_id, document_id=None, max_lessons: int = 12) -> list[dict]:
    q = db.query(ContentDocument).filter(ContentDocument.course_id == course_id)
    if document_id:
        q = q.filter(ContentDocument.id == uuid.UUID(document_id))
    docs = q.all()
    versions = {v.id: v for v in db.query(ContentVersion).filter(
        ContentVersion.status == "PUBLISHED").all()}
    lessons = []
    for d in docs:
        v = versions.get(d.current_version_id) if d.current_version_id else None
        if v is None:
            continue
        blocks = (v.structured_content or {}).get("blocks") or []
        section = d.title
        for b in blocks:
            if b.get("type") == "heading":
                section = b.get("title") or section
                continue
            text = (b.get("body") or "").strip()
            if len(text) < 60:
                continue
            words = len(text.split())
            minutes = max(2, min(6, round(words / 180) or 3))
            # قطعه‌بندی متن طولانی به گام‌های ~۳ جمله‌ای
            sentences = [s.strip() for s in text.replace("؛", ".").split(".") if s.strip()]
            steps = []
            step_size = max(2, round(len(sentences) / max(1, round(minutes))))
            for i in range(0, len(sentences), step_size):
                steps.append(". ".join(sentences[i:i + step_size]) + ".")
            lessons.append({
                "document_id": str(d.id), "version_id": str(v.id),
                "title": b.get("title") or section,
                "section": section,
                "estimated_minutes": minutes,
                "word_count": words,
                "step_count": len(steps),
                "steps": steps[:6],
                "concepts": [str(x) for x in (b.get("concept_ids") or [])][:4],
                "self_check": ("خودتان در دو جمله بخش خوانده‌شده را بازگو کنید؛ سپس "
                               "کوییز هوشمند همان مفهوم را بسنجد."),
            })
            if len(lessons) >= max_lessons:
                return lessons
    return lessons


# ---------------- سرویس ۱۵: طراحی هوشمند سوال و ارزیابی ----------------

def exam_simulation(db: Session, teacher, course_id, payload: dict) -> dict:
    """شبیه‌سازی امتحان: Blueprint خودکار از گراف مفاهیم + نقشه ضعف کلاس.

    سیاست اعتبارسنجی: سؤال‌های تولیدی فقط با status=APPROVED وارد شبیه‌سازی
    می‌شوند (gate انسانی حفظ می‌شود).
    """
    from app.core.permissions import Role
    from app.core.permissions import ensure_course_role
    from app.models.courses import Course

    ensure_course_role(db, teacher, course_id, {Role.PROFESSOR, Role.ASSISTANT})
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    concepts = [c for c in _course_concepts(db, course_id) if c.status == "APPROVED"]
    if not concepts:
        raise validation_error("برای شبیه‌سازی امتحان، ابتدا گراف مفاهیم مصوب درس لازم است")
    aggregate = {a["concept_id"]: a for a in learning_service.aggregate_mastery(db, course_id)}
    sections = []
    for c in concepts[:8]:
        agg = aggregate.get(str(c.id)) or {}
        known = agg.get("known_ratio") or 0
        weak_ratio = agg.get("weak_ratio") or 0
        difficulty = ("HARD" if known >= 0.6
                      else "EASY" if weak_ratio > 0.5 else "MEDIUM")
        sections.append({"concept_ids": [str(c.id)], "count": 1,
                         "difficulty": difficulty})
    count = sum(s["count"] for s in sections)
    assessment = assessment_service.create_assessment(db, teacher, {
        "course_id": str(course_id),
        "title": payload.get("title") or f"شبیه‌سازی امتحان — {course.title}",
        "kind": "EXAM", "mode": "FIXED",
        "blueprint": {"sections": sections},
        "duration_minutes": payload.get("duration_minutes") or count * 2,
        "policy": {"feedback": "AFTER_FINISH", "allow_hint": False, "shuffle": False},
    })
    from app.services.assessment_service import assessment_payload
    return {"assessment": assessment_payload(db, assessment),
            "sections": len(sections), "total_questions": count,
            "note": ("سؤال‌ها فقط از بانک مصوب انتخاب می‌شوند؛ سؤال‌های تولیدی AI "
                     "پیش از ورود باید در صف اعتبارسنجی تأیید شوند.")}


def validation_queue(db: Session, course_id) -> dict:
    """صف اعتبارسنجی انسانی: سؤال‌های AI_GENERATED/PENDING_REVIEW — دروازه ورود به بانک رسمی."""
    from app.core.permissions import Role
    from app.core.permissions import ensure_course_role

    rows = (
        db.query(Question, QuestionVersion)
        .join(QuestionVersion, QuestionVersion.question_id == Question.id)
        .filter(Question.course_id == course_id,
                Question.status.in_(("AI_GENERATED", "PENDING_REVIEW")),
                QuestionVersion.is_current == True)  # noqa: E712
        .order_by(Question.created_at.desc()).all()
    )
    concept_names = {str(c.id): c.name for c in _course_concepts(db, course_id)}
    items = []
    for q, qv in rows:
        qids = [str(qc.concept_id) for qc in db.query(QuestionConcept).filter(
            QuestionConcept.question_id == q.id).all()]
        items.append({
            "question_id": str(q.id), "question_version_id": str(qv.id),
            "status": q.status, "type": q.type, "source": q.source,
            "difficulty_estimated": q.difficulty_estimated,
            "difficulty_empirical": q.difficulty_empirical,
            "cognitive_level": q.cognitive_level,
            "similarity_score": q.similarity_score,
            "warnings": (q.notes or None),
            "body": qv.body,
            "concepts": [concept_names.get(x, x) for x in qids],
            "created_at": q.created_at.isoformat(),
        })
    dup_risk = [i["question_id"] for i in items if (i["similarity_score"] or 0) >= 0.8]
    return {
        "items": items,
        "pending_count": len(items),
        "duplicate_risk_count": len(dup_risk),
        "note": ("تأیید انسانی (استاد/دستیار) از طریق POST /questions/{id}/reviews "
                 "انجام می‌شود؛ سؤال تأییدنشده وارد آزمون رسمی نمی‌شود."),
    }


# ---------------- داشبورد یکپارچه ----------------

def overview(db: Session, learner_id, course_id) -> dict:
    w = weaknesses(db, learner_id, course_id)
    style = learning_style(db, learner_id, course_id)
    load = cognitive_load(db, learner_id, course_id)
    forget = forgetting_curve(db, learner_id, course_id)
    from app.services.planning_service import get_due_reviews

    due = get_due_reviews(db, learner_id, course_id, horizon_days=3)
    mastery_rows = learning_service.mastery_payload(db, learner_id, course_id)
    known = sum(1 for m in mastery_rows if m["status"] == "KNOWN")
    partial = sum(1 for m in mastery_rows if m["status"] == "PARTIAL")

    actions = []
    if w["weaknesses"]:
        w0 = w["weaknesses"][0]
        actions.append({"type": "REMEDIAL", "label": f"تمرین جبرانی: {w0['concept_name']}",
                        "ref": w0["concept_id"]})
    if forget["urgent_count"]:
        actions.append({"type": "REVIEW", "label": f"مرور فوری {forget['urgent_count']} مفهوم در آستانه فراموشی",
                        "ref": "forgetting"})
    if due:
        actions.append({"type": "REVIEW", "label": f"{len(due)} مرور سررسیدشده در برنامه مطالعه",
                        "ref": "plan"})
    if w["unknown_count"]:
        actions.append({"type": "DIAGNOSTIC", "label": f"کوییز تشخیصی برای {w['unknown_count']} مفهوم نامشخص",
                        "ref": "quiz"})
    if load.get("status") == "OK" and load["band"] == "HIGH":
        actions.append({"type": "MICRO", "label": "نشانه‌های دشواری بالا — قطعه‌های کوتاه امروز",
                        "ref": "micro"})
    if not actions:
        actions.append({"type": "KEEP_GOING", "label": "وضعیت یادگیری پایدار است؛ مرور فاصله‌دار را ادامه دهید.",
                        "ref": None})

    return {
        "mastery": {"known": known, "partial": partial,
                    "weak": w["weak_count"], "unknown": w["unknown_count"],
                    "total": len(mastery_rows)},
        "top_weaknesses": w["weaknesses"][:3],
        "cognitive_load": load,
        "learning_style": style,
        "forgetting": {"urgent_count": forget["urgent_count"],
                       "concepts": forget["concepts"][:4]},
        "due_reviews": due[:4],
        "next_actions": actions[:5],
    }
