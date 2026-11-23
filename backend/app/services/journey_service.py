"""سرویس «مسیر یادگیری» — تجربه منسجم روزمره دانشجو (بازخورد ۳.۱).

هدف: دانشجو بدون شناخت اصطلاحات فنی (گراف دانش، مدل شناختی و...) یک قدم
بعدی روشن داشته باشد. چرخه: هدف من → تشخیص کوتاه → یادگیری هدفمند → تمرین →
بازخورد → مرور → مشاهده پیشرفت.

قابلیت‌های این ماژول:
- تمرکز روزانه (پیشنهاد اصلی امروز + سه انتخاب + مرورها + ادامه جلسه)
- جلسه یادگیری با زمان انتخابی ۵/۱۵/۳۰ دقیقه (قابل توقف/ادامه)
- آمادگی آزمون با اولویت‌بندی صادقانه (پوشش و عدم‌قطعیت؛ بدون وعده نمره)
- نقشه مفاهیم دوحالته (مسیر ساده روزمره + نقشه گرافیکی کاوش)
- «اینجا گیر کردم» → ورود استاد هوشمند از همان نقطه محتوا
- کلینیک خطا (دفتر خطای آموزشی با برچسب قابل اصلاح دانشجو)
- «به من یاد بده» (بازگویی با روبرک AI — بازخورد یادگیری، نه نمره رسمی)
- داشبورد اقدام‌محور استاد (به اقدام آموزشی منتهی می‌شود، نه رتبه‌بندی)
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import ensure_utc, utcnow
from app.core.errors import forbidden, not_found, validation_error
from app.models.assessment import Assessment, Attempt, Response
from app.models.concepts import Concept, ConceptMisconception, ConceptRelation, TopicConcept
from app.models.content import ContentVersion
from app.models.journey import (ErrorNotebookEntry, ExamPrepPlan, LearningSession,
                                StuckMark, TeachBackSubmission)
from app.models.learning import LearningEvent, MasteryEstimate
from app.models.planning import ReviewSchedule, StudyActivity
from app.models.questions import Question, QuestionConcept, QuestionVersion
from app.services import learning_service, smart_service, tutor_service

STUCK_LABELS = {
    "NOT_UNDERSTOOD": "معنی این عبارت را نمی‌فهمم",
    "CONNECTION_UNCLEAR": "ارتباطش با مطلب قبلی روشن نیست",
    "STEP_UNCLEAR": "نمی‌دانم چرا این مرحله انجام شد",
    "KNOWS_BUT_CANT_SOLVE": "مفهوم را می‌دانم، اما نمی‌توانم حل کنم",
}
STUCK_QUESTIONS = {
    "NOT_UNDERSTOOD": "این عبارت برایم مبهم است و نمی‌فهمم چه می‌گوید: «{anchor}»",
    "CONNECTION_UNCLEAR": "ارتباط این بخش با مطلب قبلی را نمی‌بینم: «{anchor}»",
    "STEP_UNCLEAR": "دلیل این مرحله از حل را نمی‌فهمم: «{anchor}»",
    "KNOWS_BUT_CANT_SOLVE": "مفهوم را می‌دانم اما در این مسئله گیر کرده‌ام: «{anchor}»",
}
PATTERN_LABELS = {
    "RUSH_ERROR": "پاسخ سریع‌ونادرست — احتمال بی‌دقتی در خواندن صورت سؤال",
    "SIGN_OR_STEP_ERROR": "خطای نشانه/گام — روش کلی درست است اما جزئیات جا می‌افتد",
    "CONCEPT_GAP": "شکاف مفهومی — پیش‌زمینه این مفهوم تثبیت نشده است",
    "HINT_DEPENDENT": "وابستگی به راهنما — بدون راهنما پاسخ درست نیامده است",
}


# ---------------- تمرکز روزانه ----------------

def daily_focus(db: Session, learner, course_id: str) -> dict:
    from app.models.courses import Course
    from app.services.planning_service import get_due_reviews

    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    w = smart_service.weaknesses(db, learner.id, course_id)
    forget = smart_service.forgetting_curve(db, learner.id, course_id)
    mastery_rows = learning_service.mastery_payload(db, learner.id, course_id)
    due = get_due_reviews(db, learner.id, course_id, horizon_days=3)

    suggestion = None
    if forget["urgent_count"] and forget["concepts"]:
        c0 = forget["concepts"][0]
        suggestion = {
            "type": "REVIEW", "title": f"تثبیت {c0['concept_name']}",
            "minutes": 12, "concept_id": c0["concept_id"],
            "reason": "این مفهوم بر پایه زمان‌بندی مرور در آستانه فراموشی است.",
            "url": f"/course/{course_id}/learn?concept={c0['concept_id']}",
            "primary_action": "شروع یادگیری",
        }
    elif w["weaknesses"]:
        w0 = w["weaknesses"][0]
        nar = next((m["narrative"] for m in mastery_rows
                    if m["concept_id"] == w0["concept_id"]), {})
        suggestion = {
            "type": "PRACTICE", "title": f"یادگیری هدفمند {w0['concept_name']}",
            "minutes": 15, "concept_id": w0["concept_id"],
            "reason": (nar.get("why") or "شواهد یادگیری، نیاز به تمرین این مفهوم را نشان می‌دهد.")
            + (" (فرضیه — با کوییز کوتاه تأیید می‌شود)" if w0.get("nature") == "HYPOTHESIS" else ""),
            "url": f"/course/{course_id}/learn?concept={w0['concept_id']}",
            "primary_action": "شروع یادگیری",
        }
    elif w["unknown_count"]:
        c0 = mastery_rows[0] if mastery_rows else None
        suggestion = {
            "type": "DIAGNOSTIC", "title": "کوییز کوتاه تشخیصی",
            "minutes": 8,
            "concept_id": c0["concept_id"] if c0 else None,
            "reason": "برای چند مفهوم هنوز شواهد کافی نداریم؛ چند سؤال کوتاه وضعیت را روشن می‌کند.",
            "url": f"/course/{course_id}/smart", "primary_action": "شروع یادگیری",
        }
    else:
        lesson = (smart_service.micro_lessons(db, course_id, max_lessons=1) or [None])[0]
        suggestion = {
            "type": "CONSOLIDATE",
            "title": lesson["title"] if lesson else "مرور سبک تثبیتی",
            "minutes": 12, "concept_id": None,
            "reason": "وضعیت یادگیری پایدار است؛ یک تثبیت سبک برای حفظ روند کافی است.",
            "url": f"/course/{course_id}/learn",
            "primary_action": "شروع یادگیری",
        }

    known = sum(1 for m in mastery_rows if m["status"] == "KNOWN")
    partial = sum(1 for m in mastery_rows if m["status"] == "PARTIAL")
    active_session = get_active_session(db, learner.id, course_id)
    return {
        "greeting": "سلام! امروز از کجا شروع کنیم؟",
        "course": {"id": str(course.id), "title": course.title, "code": course.code},
        "today_suggestion": suggestion,
        "choices": [
            {"key": "LEARN", "label": "یک مفهوم را یاد بگیرم",
             "url": f"/course/{course_id}/learn",
             "hint": "محتوای منتشرشده + استاد هوشمند"},
            {"key": "FIX", "label": "اشکال پاسخ یا حل خودم را پیدا کنم",
             "url": "/me/error-clinic?course_id=" + course_id,
             "hint": "کلینیک خطا از پاسخ‌های اخیر شما"},
            {"key": "EXAM_PREP", "label": "برای آزمون آماده شوم",
             "url": f"/course/{course_id}/exam-prep",
             "hint": "اولویت‌بندی صادقانه بر اساس شواهد"},
        ],
        "my_progress": {"known": known, "partial": partial,
                        "weak": w["weak_count"], "unassessed": w["unknown_count"],
                        "total": len(mastery_rows)},
        "reviews_suggested": [
            {"concept_id": r["concept_id"], "concept_name": r["concept_name"],
             "due_at": r.get("due_at"), "note": "مرور فاصله‌دار امروز"}
            for r in due[:3]
        ] or [
            {"concept_id": c["concept_id"], "concept_name": c["concept_name"],
             "due_at": None, "note": "کاندیدای مرور بر اساس پیش‌بینی فراموشی"}
            for c in forget["concepts"][:2]
        ],
        "continue_session": active_session,
        "note": "همیشه فقط یک قدم بعدی روشن پیشنهاد می‌شود؛ ۱۶ ابزار تحلیلی در «ابزارهای هوشمند» در دسترس‌اند.",
    }


# ---------------- جلسه یادگیری با زمان انتخابی ----------------

_SESSION_PLANS = {
    5: [("REVIEW", 2, "مرور سریع مفهوم در آستانه فراموشی"),
        ("PRACTICE", 3, "دو تمرین کوتاه هدفمند")],
    15: [("REVIEW", 3, "مرور مفاهیم سررسیدشده"),
         ("MICRO_LESSON", 5, "آموزش کوتاه مرحله‌ای"),
         ("PRACTICE", 7, "بسته تمرین هدفمند")],
    30: [("REVIEW", 5, "مرور فاصله‌دار"),
         ("MICRO_LESSON", 8, "آموزش کوتاه با خودارزیابی"),
         ("PRACTICE", 10, "تمرین جبرانی هدفمند"),
         ("SMART_QUIZ", 7, "کوییز هوشمند تطبیقی")],
}


def start_session(db: Session, learner, course_id: str, minutes: int) -> dict:
    from app.models.courses import Course

    if minutes not in _SESSION_PLANS:
        raise validation_error("زمان جلسه باید یکی از ۵، ۱۵ یا ۳۰ دقیقه باشد")
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    active = get_active_session(db, learner.id, course_id)
    if active:
        return active  # جلسه باز از قبل هست — ادامه می‌دهیم

    forget = smart_service.forgetting_curve(db, learner.id, course_id)
    review_concept = next((c for c in forget["concepts"] if c["overdue_for_review"]),
                          (forget["concepts"][0] if forget["concepts"] else None))
    lessons = smart_service.micro_lessons(db, course_id, max_lessons=1)
    lesson = lessons[0] if lessons else None

    composition = []
    for i, (kind, mins, title) in enumerate(_SESSION_PLANS[minutes]):
        step = {"index": i, "kind": kind, "title": title, "minutes": mins, "done": False,
                "ref": None, "url": f"/course/{course_id}/learn"}
        if kind == "REVIEW" and review_concept:
            step["ref"] = review_concept["concept_id"]
            step["title"] = f"مرور {review_concept['concept_name']}"
            step["url"] = f"/course/{course_id}/learn?concept={review_concept['concept_id']}"
        elif kind == "MICRO_LESSON" and lesson:
            step["ref"] = lesson["version_id"]
            step["title"] = lesson["title"]
            step["url"] = f"/course/{course_id}/content/{lesson['version_id']}"
        elif kind == "PRACTICE":
            pack = smart_service.remedial_pack(db, learner.id, course_id, per_concept=1)
            if pack.get("status") == "OK" and pack["concepts"]:
                c0 = pack["concepts"][0]
                step["ref"] = c0["concept_id"]
                step["title"] = f"تمرین: {c0['concept_name']}"
            step["url"] = f"/course/{course_id}/smart"
        elif kind == "SMART_QUIZ":
            step["url"] = f"/course/{course_id}/smart"
        composition.append(step)

    session = LearningSession(
        learner_id=learner.id, course_id=course_id, minutes=minutes,
        composition=composition, state="ACTIVE",
        progress={"step_index": 0}, started_at=utcnow(),
    )
    db.add(session)
    db.flush()
    return session_payload(db, session)


def get_active_session(db: Session, learner_id, course_id) -> dict | None:
    s = db.query(LearningSession).filter(
        LearningSession.learner_id == learner_id,
        LearningSession.course_id == course_id,
        LearningSession.state.in_(("ACTIVE", "PAUSED"))).first()
    return session_payload(db, s) if s else None


def session_action(db: Session, learner, session_id: str, action: str,
                   step_index: int | None = None) -> dict:
    s = db.get(LearningSession, session_id)
    if s is None or str(s.learner_id) != str(learner.id):
        raise not_found("جلسه یافت نشد")
    if s.state == "DONE":
        raise validation_error("این جلسه کامل شده است")
    if action == "pause":
        s.state, s.paused_at = "PAUSED", utcnow()
    elif action == "resume":
        s.state, s.paused_at = "ACTIVE", None
    elif action == "advance":
        comp = list(s.composition or [])
        idx = (s.progress or {}).get("step_index", 0)
        idx = step_index if step_index is not None else idx
        if 0 <= idx < len(comp):
            comp[idx]["done"] = True
            s.composition = comp
            s.progress = {"step_index": min(idx + 1, len(comp) - 1)}
    elif action == "done":
        comp = list(s.composition or [])
        for c in comp:
            c["done"] = True
        s.composition = comp
        s.state, s.completed_at = "DONE", utcnow()
        learning_service.record_event(db, learner.id, s.course_id,
                                      "PRACTICE_COMPLETED", payload={"session_minutes": s.minutes})
    else:
        raise validation_error("عملیات نامعتبر است")
    db.flush()
    return session_payload(db, s)


def session_payload(db: Session, s: LearningSession) -> dict:
    return {
        "id": str(s.id), "course_id": str(s.course_id), "minutes": s.minutes,
        "state": s.state, "composition": s.composition, "progress": s.progress,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    }


# ---------------- آمادگی آزمون با اولویت‌بندی صادقانه ----------------

def exam_prep(db: Session, learner, course_id: str, payload: dict) -> dict:
    exam_date = payload.get("exam_date")
    available = payload.get("available_minutes")
    rows = learning_service.mastery_payload(db, learner.id, course_id)
    p1, p2, p3, insufficient = [], [], [], []
    for m in rows:
        nar = m["narrative"]
        if m["status"] == "WEAK":
            p1.append({"concept_id": m["concept_id"], "concept_name": m["concept_name"],
                       "action": "یادگیری هدفمند + تمرین جبرانی", "minutes_hint": 20,
                       "why": nar["why"],
                       "prereq_required": [p["concept_name"] for p in m["prerequisites"]
                                           if p["status"] == "WEAK"]})
        elif m["status"] == "UNKNOWN":
            p2.append({"concept_id": m["concept_id"], "concept_name": m["concept_name"],
                       "action": "کوییز کوتاه تشخیصی برای تعیین وضعیت", "minutes_hint": 8,
                       "why": nar["why"]})
        elif m["status"] == "PARTIAL":
            p3.append({"concept_id": m["concept_id"], "concept_name": m["concept_name"],
                       "action": "مرور + تمرین تثبیتی کوتاه", "minutes_hint": 12,
                       "why": nar["why"]})
    insufficient = [{"concept_id": m["concept_id"], "concept_name": m["concept_name"]}
                    for m in rows if m["status"] == "UNKNOWN"]
    total = len(rows)
    evidenced = total - len(insufficient)
    plan = {
        "exam_date": exam_date,
        "available_minutes": available,
        "priority_order": [
            {"tier": 1, "label": "ابتدا این‌ها (شواهد ضعف قطعی)", "concepts": p1},
            {"tier": 2, "label": "سپس وضعیت نامشخص را بسنجیم", "concepts": p2},
            {"tier": 3, "label": "مرور و تثبیت", "concepts": p3},
        ],
        "prereq_required": sorted({p for x in p1 for p in x["prereq_required"]}),
        "insufficient_evidence": insufficient,
        "coverage": {
            "total_concepts": total,
            "with_evidence": evidenced,
            "coverage_ratio": round(evidenced / total, 2) if total else None,
            "meaning": "سهم مفاهیمی که حداقل یک شواهد ارزیابی معتبر دارند.",
        },
        "allocated_minutes": _allocate(p1, p2, p3, available),
        "honesty_note": ("این برنامه پوشش یادگیری و عدم‌قطعیت را نشان می‌دهد؛ "
                         "هیچ وعده نمره یا قبولی ارائه نمی‌شود."),
        "programyar_note": "برای هماهنگی ساعت مطالعه با برنامه عمومی، برنامه‌یار۳۶۰ سرویس برنامه شما را مدیریت می‌کند.",
        "uncertainty_note": ("شواهد ناکافی یعنی «نامشخص»؛ کوییز تشخیصی کوتاه قبل از "
                             "زحمت طولانی، بهترین سرمایه‌گذاری است."),
    }
    db.query(ExamPrepPlan).filter(
        ExamPrepPlan.learner_id == learner.id,
        ExamPrepPlan.course_id == course_id,
        ExamPrepPlan.status == "ACTIVE").update({"status": "ARCHIVED"}, synchronize_session=False)
    row = ExamPrepPlan(learner_id=learner.id, course_id=course_id,
                       exam_date=exam_date, available_minutes=available, plan=plan)
    db.add(row)
    db.flush()
    return {"id": str(row.id), "plan": plan}


def _allocate(p1, p2, p3, available: int | None) -> dict | None:
    if not available:
        return None
    need = sum(x["minutes_hint"] for x in p1) + sum(x["minutes_hint"] for x in p2) \
        + sum(x["minutes_hint"] for x in p3)
    if need <= available:
        return {"total_needed": need, "fits": True,
                "message": "کل برنامه در زمان در دسترس شما جا می‌شود."}
    # اولویت صادقانه: تا جایی که زمان اجازه می‌دهد، طبق ترتیب تiers
    left, used = available, []
    for group in (p1, p2, p3):
        for x in group:
            if left >= x["minutes_hint"]:
                used.append(x["concept_name"])
                left -= x["minutes_hint"]
    return {"total_needed": need, "fits": False, "covered": used, "left_minutes": left,
            "message": "زمان کافی برای همه نیست؛ طبق اولویت، این‌ها را پوشش می‌دهیم."}


# ---------------- نقشه مفاهیم دوحالته ----------------

def concept_map(db: Session, learner, course_id: str, mode: str = "simple") -> dict:
    if mode not in ("simple", "full"):
        raise validation_error("حالت نقشه باید simple یا full باشد")
    concepts = db.query(Concept).filter(Concept.course_id == course_id).all()
    cnames = {str(c.id): c.name for c in concepts}
    mastery = {m["concept_id"]: m for m in learning_service.mastery_payload(db, learner.id, course_id)}
    edges = [{"from": str(r.from_concept_id), "to": str(r.to_concept_id), "type": r.rel_type}
             for r in db.query(ConceptRelation).filter(
                 ConceptRelation.from_concept_id.in_([c.id for c in concepts])).all()
             if str(r.from_concept_id) in cnames and str(r.to_concept_id) in cnames]

    # مسیر ساده: مرحله‌بندی بر پایه زنجیره پیش‌نیاز (ریشه‌ها اول)
    prereq_of: dict[str, list[str]] = {}
    for e in edges:
        if e["type"] == "PREREQUISITE_OF":
            prereq_of.setdefault(e["to"], []).append(e["from"])  # برای یادگیری «to» اول «from» لازم است
    stages, placed = [], set()
    pending = [str(c.id) for c in concepts]
    while pending:
        stage = [cid for cid in pending
                 if all(p in placed for p in prereq_of.get(cid, []))]
        if not stage:  # حلقه در گراف — باقی را یک مرحله می‌گذاریم
            stage = list(pending)
        stages.append([{"concept_id": cid, "concept_name": cnames[cid],
                        "status": mastery.get(cid, {}).get("status", "UNKNOWN"),
                        "state_label": mastery.get(cid, {}).get("narrative", {}).get("state_label"),
                        "next_step": mastery.get(cid, {}).get("narrative", {}).get("next_step")}
                       for cid in stage])
        placed |= set(stage)
        pending = [c for c in pending if c not in placed]

    out = {"mode": mode, "course_id": course_id, "stages": stages}
    if mode == "full":
        cards = []
        for c in concepts:
            m = mastery.get(str(c.id), {})
            misconceptions = [x.title for x in db.query(ConceptMisconception)
                              .filter(ConceptMisconception.concept_id == c.id).all()]
            cards.append({
                "concept_id": str(c.id), "concept_name": c.name,
                "status": m.get("status", "UNKNOWN"),
                "estimated_mastery": m.get("estimated_mastery"),
                "card": {
                    "simple_explanation": c.description or "توضیح ساده برای این مفهوم ثبت نشده است.",
                    "real_use": (c.examples or "").split(";;")[0].strip() or None,
                    "prerequisites": [p["concept_name"] for p in m.get("prerequisites", [])],
                    "common_pitfalls": misconceptions[:2],
                    "evidence": {"count": m.get("evidence_count", 0),
                                 "state_label": m.get("narrative", {}).get("state_label")},
                    "practice": {"label": "تمرین هدفمند همین مفهوم",
                                 "url": f"/course/{course_id}/learn?concept={c.id}"},
                    "ask_tutor": {"label": "از استاد هوشمند بپرس",
                                  "url": f"/course/{course_id}/tutor?concept={c.id}"},
                },
            })
        out["nodes"] = cards
        out["edges"] = edges
        out["legend_note"] = ("مسیر ساده برای استفاده روزمره؛ نمای گرافیکی برای کاوش "
                              "ارتباط‌ها — انتخاب هر نقطه، کارت کامل مفهوم را باز می‌کند.")
    return out


# ---------------- «اینجا گیر کردم» ----------------

def mark_stuck(db: Session, learner, course_id: str, payload: dict) -> dict:
    kind = payload.get("kind")
    if kind not in STUCK_LABELS:
        raise validation_error("نوع مشکل نامعتبر است")
    version_id = payload.get("content_version_id")
    anchor = (payload.get("block_anchor") or "").strip()
    if not anchor and payload.get("block_index") is None:
        raise validation_error("نقطه گیر (عبارت یا بلوک) مشخص نشده است")

    concept_id = payload.get("concept_id")
    if version_id:
        v = db.get(ContentVersion, uuid.UUID(version_id))
        if v is None:
            raise not_found("نسخه محتوا یافت نشد")
        blocks = (v.structured_content or {}).get("blocks") or []
        idx = payload.get("block_index")
        if idx is not None and 0 <= idx < len(blocks) and not concept_id:
            cids = blocks[idx].get("concept_ids") or []
            concept_id = str(cids[0]) if cids else None

    session = None
    if payload.get("start_tutor", True):
        session = tutor_service.create_session(db, learner, course_id, mode="LEARNING")
        q = STUCK_QUESTIONS[kind].format(anchor=anchor or "این بخش")
        tutor_service.answer(db, session, q, help_mode="EXPLAIN")

    mark = StuckMark(
        learner_id=learner.id, course_id=course_id,
        content_version_id=uuid.UUID(version_id) if version_id else None,
        block_index=payload.get("block_index"), block_anchor=anchor or None,
        kind=kind, note=payload.get("note"),
        tutor_session_id=session.id if session else None,
    )
    db.add(mark)
    db.flush()
    return {
        "id": str(mark.id), "kind": kind, "kind_label": STUCK_LABELS[kind],
        "tutor_session_id": str(session.id) if session else None,
        "message": ("علامت ثبت شد؛ استاد هوشمند از همین نقطه و فقط با منابع مجاز درس "
                    "با شما وارد گفتگو شده است."),
    }


# ---------------- کلینیک خطا ----------------

def error_clinic(db: Session, learner, course_id: str) -> dict:
    """دفتر خطای آموزشی: از پاسخ‌های نادرست، الگوی خطا ساخته می‌شود؛
    تفسیر «فرضیه» است و دانشجو می‌تواند برچسب را اصلاح/توضیح دهد."""
    now = ensure_utc(utcnow())
    rows = (
        db.query(Response, Question, QuestionVersion)
        .join(Attempt, Response.attempt_id == Attempt.id)
        .join(Assessment, Attempt.assessment_id == Assessment.id)
        .join(QuestionVersion, Response.question_version_id == QuestionVersion.id)
        .join(Question, QuestionVersion.question_id == Question.id)
        .filter(Attempt.student_id == learner.id, Assessment.course_id == course_id,
                Response.correctness.isnot(None))
        .order_by(Response.graded_at).all()
    )
    concept_names = {str(c.id): c.name for c in db.query(Concept).filter(Concept.course_id == course_id)}
    observed: dict[str, dict] = {}
    for r, q, qv in rows:
        if (r.correctness or 0) >= 1:
            continue
        row = db.query(QuestionConcept).filter(
            QuestionConcept.question_id == qv.question_id).first()
        cid = str(row.concept_id) if row else None
        if not cid:
            continue
        exp = smart_service._EXPECTED_MS.get(q.difficulty_estimated, 90_000)
        t = r.time_spent_ms or exp
        if t < exp / 2:
            kind = "RUSH_ERROR"
        elif (r.ai_feedback or {}).get("near_miss"):
            kind = "SIGN_OR_STEP_ERROR"
        elif r.hint_used:
            kind = "HINT_DEPENDENT"
        else:
            kind = "CONCEPT_GAP"
        key = f"{kind}:{cid}"
        entry = observed.setdefault(key, {"kind": kind, "concept_id": cid,
                                          "evidence": [], "last": r})
        entry["evidence"].append({"response_id": str(r.id),
                                  "at": r.graded_at.isoformat() if r.graded_at else None,
                                  "time_spent_ms": r.time_spent_ms,
                                  "hint_used": bool(r.hint_used)})
        entry["last"] = r

    changed = False
    for key, obs in observed.items():
        row = db.query(ErrorNotebookEntry).filter(
            ErrorNotebookEntry.learner_id == learner.id,
            ErrorNotebookEntry.course_id == course_id,
            ErrorNotebookEntry.concept_id == uuid.UUID(obs["concept_id"]),
            ErrorNotebookEntry.pattern_key == obs["kind"]).first()
        if row is None:
            row = ErrorNotebookEntry(
                learner_id=learner.id, course_id=course_id,
                concept_id=uuid.UUID(obs["concept_id"]), pattern_key=obs["kind"],
                title=PATTERN_LABELS[obs["kind"]], evidence=obs["evidence"],
                status="OPEN",
                suggested_practice={"label": "تمرین کوتاه همان الگوی خطا",
                                    "url": f"/course/{course_id}/learn?concept={obs['concept_id']}"},
                last_seen_at=obs["last"].graded_at,
            )
            db.add(row)
            changed = True
        else:
            last = ensure_utc(row.last_seen_at) if row.last_seen_at else None
            new_evidence = [e for e in obs["evidence"]
                            if last is None or (e["at"] and ensure_utc(datetime.fromisoformat(e["at"])) > last)]
            if new_evidence:
                row.recurrence_count += 1
                row.evidence = obs["evidence"][-6:]
                row.last_seen_at = obs["last"].graded_at
                if row.status == "RESOLVED":
                    row.status = "OPEN"  # بازگشت خطا پس از تصور رفع
                changed = True
    if changed:
        db.flush()

    entries = db.query(ErrorNotebookEntry).filter(
        ErrorNotebookEntry.learner_id == learner.id,
        ErrorNotebookEntry.course_id == course_id).all()
    out = []
    for e in sorted(entries, key=lambda x: (x.status != "OPEN", -(x.recurrence_count or 0))):
        out.append({
            "id": str(e.id), "pattern_key": e.pattern_key,
            "title": PATTERN_LABELS.get(e.pattern_key, e.title),
            "concept_id": str(e.concept_id) if e.concept_id else None,
            "concept_name": concept_names.get(str(e.concept_id) or "", None),
            "status": e.status, "recurrence_count": e.recurrence_count,
            "evidence_count": len(e.evidence or []),
            "student_explanation": e.student_explanation,
            "suggested_practice": e.suggested_practice,
            "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
            "question": "چه اشتباهی رخ داد؟ شواهد چه می‌گویند؟ راه درست تشخیص آن چیست؟",
        })
    return {
        "entries": out,
        "note": ("برچسب خطا فرضیه سامانه است؛ اگر عامل دیگری (خستگی، قطع اینترنت، "
                 "دسترس‌پذیری) علت بود، توضیح خود را ثبت کنید — برچسب اصلاح می‌شود."),
    }


def attribute_error(db: Session, learner, entry_id: str, explanation: str) -> dict:
    e = db.get(ErrorNotebookEntry, uuid.UUID(entry_id))
    if e is None or str(e.learner_id) != str(learner.id):
        raise not_found("رکورد خطا یافت نشد")
    if not explanation.strip():
        raise validation_error("توضیح خالی است")
    e.student_explanation = explanation.strip()
    e.status = "ATTRIBUTED"
    db.flush()
    return {"id": str(e.id), "status": e.status,
            "message": "توضیح شما ثبت شد؛ تحلیل‌های بعدی همین تفسیر را ملاک می‌گیرند."}


# ---------------- «به من یاد بده» ----------------

def teach_back(db: Session, learner, course_id: str, payload: dict) -> dict:
    from app.ai.gateway import AIGateway
    from app.ai.schemas import TeachBackFeedbackOut

    concept = db.get(Concept, uuid.UUID(payload["concept_id"]))
    if concept is None or str(concept.course_id) != str(course_id):
        raise not_found("مفهوم در این درس یافت نشد")
    modality = payload.get("modality", "TEXT")
    if modality not in ("TEXT", "AUDIO"):
        raise validation_error("قالب توضیح باید TEXT یا AUDIO باشد")
    content = (payload.get("content") or "").strip()
    if modality == "TEXT" and len(content) < 10:
        raise validation_error("توضیح کوتاه است؛ حداقل یک جمله کامل بنویس")

    gateway = AIGateway(db)
    out = gateway.run(
        "teach_back_feedback",
        {"concept_name": concept.name, "content": content,
         "concept_description": concept.description},
        schema=TeachBackFeedbackOut, created_by=learner.id,
    )
    sub = TeachBackSubmission(
        learner_id=learner.id, course_id=course_id, concept_id=concept.id,
        modality=modality, content=content or None,
        audio_path=payload.get("audio_path"),
        rubric=[c.model_dump() for c in out.rubric_scores],
        follow_up_question=out.follow_up_question or None,
    )
    db.add(sub)
    db.flush()
    return {
        "id": str(sub.id), "concept_name": concept.name,
        "rubric_scores": sub.rubric, "follow_up_question": sub.follow_up_question,
        "gaps": out.gaps, "encouragement": out.encouragement,
        "note": ("این بازخورد ابزار یادگیری است؛ نمره رسمی فقط با سیاست درس و "
                 "تأیید انسانی معنا دارد."),
    }


# ---------------- داشبورد اقدام‌محور استاد ----------------

def professor_actions(db: Session, user, course_id: str) -> dict:
    from app.core.permissions import Role, ensure_course_role
    from app.models.courses import CourseOffering, Enrollment

    ensure_course_role(db, user, course_id,
                       {Role.PROFESSOR, Role.ASSISTANT, Role.GROUP_ADMIN,
                        Role.EDUCATION_ADMIN, Role.TECH_ADMIN})
    cards = []
    # ۱) مفاهیم نیازمند بازتوضیح
    for a in learning_service.aggregate_mastery(db, course_id):
        if a["needs_reteach"]:
            cards.append({
                "type": "RETEACH", "title": f"بازتوضیح «{a['concept_name']}»",
                "detail": f"بیش از نیم کلاس در وضعیت ضعیف این مفهوم هستند ({int((a['weak_ratio'] or 0)*100)}٪).",
                "action_label": "گزارش مفهوم و تمرین مشترک",
                "action_url": f"/course/{course_id}/actions?concept={a['concept_id']}",
            })
    # ۲) سؤال‌های احتمالاً ابهام‌دار
    q_rows = (
        db.query(Question, func.avg(Response.correctness), func.count(Response.id))
        .join(QuestionVersion, QuestionVersion.question_id == Question.id)
        .join(Response, Response.question_version_id == QuestionVersion.id)
        .filter(Question.course_id == course_id)
        .group_by(Question.id).all()
    )
    for q, avg, n in q_rows:
        if n >= 3 and (avg is not None and avg < 0.3):
            cards.append({
                "type": "AMBIGUOUS_QUESTION",
                "title": f"سؤال با نرخ پاسخ صحیح بسیار پایین ({int((avg or 0)*100)}٪)",
                "detail": f"{n} پاسخ ثبت شده؛ احتمال ابهام صورت سؤال یا گزینه‌ها را بررسی کنید.",
                "action_label": "بازبینی سؤال در بانک",
                "action_url": f"/course/{course_id}/smart",
            })
    # ۳) دانشجوهای با شواهد ناکافی
    offering_ids = [o.id for o in db.query(CourseOffering).filter(
        CourseOffering.course_id == course_id).all()]
    student_ids = [e.student_id for e in db.query(Enrollment).filter(
        Enrollment.offering_id.in_(offering_ids or [None])).all()]
    low_evidence = 0
    for sid in student_ids:
        rows = db.query(MasteryEstimate).filter(
            MasteryEstimate.learner_id == sid,
            MasteryEstimate.course_id == course_id).all()
        if rows and sum(1 for r in rows if r.status == "UNKNOWN") > len(rows) / 2:
            low_evidence += 1
    if low_evidence:
        cards.append({
            "type": "INSUFFICIENT_EVIDENCE",
            "title": f"{low_evidence} دانشجو هنوز شواهد کافی ندارند",
            "detail": "برای این‌ها وضعیت «نامشخص» است، نه ضعف؛ کوییز تشخیصی کوتاه پیشنهاد می‌شود.",
            "action_label": "ارسال کوییز تشخیصی",
            "action_url": f"/course/{course_id}/smart",
        })
    # ۴) گروه کوچک نیازمند تمرین مشترک
    for a in learning_service.aggregate_mastery(db, course_id):
        if a["weak_ratio"] and 0.3 <= a["weak_ratio"] <= 0.6:
            cards.append({
                "type": "SMALL_GROUP_PRACTICE",
                "title": f"گروه کوچک برای تمرین مشترک «{a['concept_name']}»",
                "detail": "بخشی از کلاس ضعیف‌اند و بخشی مسلط — تمرین گروهی کوچک مؤثرتر است.",
                "action_label": "طراحی تمرین مشترک",
                "action_url": f"/course/{course_id}/smart",
            })
    return {
        "course_id": course_id, "cards": cards,
        "note": ("هر گزارش به یک اقدام آموزشی منتهی می‌شود؛ رتبه‌بندی دانشجویان "
                 "و نمایش میانگین‌های صرف در این داشبورد وجود ندارد."),
    }


# ---------------- ترجیح اعلام‌شده ----------------

def set_interaction_preference(db: Session, learner, course_id: str, payload: dict) -> dict:
    preference = (payload.get("preference") or "").strip()
    if preference not in ("VISUAL", "PRACTICAL", "CONVERSATIONAL", "NONE"):
        raise validation_error("ترجیح نامعتبر است")
    learning_service.record_event(
        db, learner.id, course_id, "PREFERENCE_SET",
        payload={"preference": preference,
                 "accessibility_needs": payload.get("accessibility_needs") or []},
    )
    db.flush()
    return {
        "preference": preference,
        "message": ("ترجیح شما ثبت شد؛ توصیه‌ها بر پایه عملکرد، هدف، همین ترجیح اعلام‌شده "
                    "و نیازهای دسترس‌پذیری تنظیم می‌شود — نه یک برچسب ثابت."),
    }
