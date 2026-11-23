"""استاد هوشمند گفتگو‌محور (بخش ۸).

خط پاسخ: پیام دانشجو → احراز دسترسی به درس → بازیابی منابع مجاز (پیش از
امتیازدهی مجوز اعمال می‌شود) → دریافت وضعیت یادگیری لازم → تولید پاسخ →
بررسی خروجی (اعتبار ارجاع‌ها) → نمایش پاسخ و منابع.

سیاست‌ها:
- کلید امتحان فعال (contains_exam_material) هرگز وارد بازیابی نمی‌شود (AC-09).
- حالت «یادگیری» از «آزمون» جدا است؛ در آزمون سطح کمک طبق سیاست محدود می‌شود.
- در نبود شواهد کافی، عدم اطمینان صادقانه اعلام می‌شود.
- گفتگو منبع قطعی تسلط نیست و در شواهد وزن ندارد.
"""
from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.schemas import TutorOut
from app.core.errors import forbidden, not_found
from app.models.tutor import TutorMessage, TutorSession
from app.services import rag as rag_service


def create_session(db: Session, student, course_id: str, mode: str = "LEARNING",
                   assessment_id=None) -> TutorSession:
    from app.core.permissions import ensure_enrolled_or_staff

    ensure_enrolled_or_staff(db, student, course_id)
    if mode not in ("LEARNING", "ASSESSMENT"):
        raise forbidden("حالت گفتگو نامعتبر است")
    if mode == "ASSESSMENT" and not assessment_id:
        raise forbidden("گفتگوی حالت آزمون باید به یک ارزیابی متصل باشد")
    session = TutorSession(
        student_id=student.id, course_id=course_id, mode=mode,
        assessment_id=assessment_id,
    )
    db.add(session)
    db.flush()
    return session


def _learner_state(db: Session, session: TutorSession) -> dict:
    from app.models.learning import MasteryEstimate
    from app.models.concepts import Concept

    rows = (
        db.query(MasteryEstimate, Concept)
        .join(Concept, MasteryEstimate.concept_id == Concept.id)
        .filter(MasteryEstimate.learner_id == session.student_id,
                MasteryEstimate.course_id == session.course_id)
        .all()
    )
    weak = [c.name for m, c in rows if m.status == "WEAK"]
    unknown = [c.name for m, c in rows if m.status == "UNKNOWN"]
    known = [c.name for m, c in rows if m.status == "KNOWN"]
    return {"weak_concepts": weak, "unknown_concepts": unknown,
            "known_concepts": known[:5]}


def _build_context(db: Session, session: TutorSession, question: str) -> list[dict]:
    """بازیابی مجاز: فیلتر مجوز قبل از امتیازدهی؛ کلید امتحان هرگز بازیابی نمی‌شود."""
    chunks = rag_service.retrieve_chunks(
        db, session.course_id, question, k=5, include_exam_material=False)
    chunks += rag_service.retrieve_published_content(db, session.course_id, question, k=3)
    return chunks


HELP_MODES = ("EXPLAIN", "GUIDE", "PRACTICE")


def _help_policy(session: TutorSession, help_mode: str | None) -> dict:
    """سیاست نردبان راهنمایی هر نشست: در آزمون فقط توضیح صورت سؤال و بالاترین
    سطح ۱ (سؤال راهنما) مجاز است؛ در یادگیری سه حالت کامل داریم."""
    if session.mode == "ASSESSMENT":
        return {"help_mode": "GUIDE", "max_ladder_level": 1,
                "note": "در حالت آزمون فقط سؤال راهنما و توضیح صورت سؤال مجاز است."}
    hm = help_mode or "EXPLAIN"
    if hm not in HELP_MODES:
        hm = "EXPLAIN"
    return {"help_mode": hm, "max_ladder_level": 5,
            "note": {"EXPLAIN": "توضیح کامل با مثال ساده‌تر.",
                     "GUIDE": "فقط سؤال راهنما و اشاره به مفهوم؛ پاسخ کامل با درخواست شما.",
                     "PRACTICE": "حل گام‌به‌گام مشترک؛ هر گام را شما می‌نویسید."}[hm]}


def answer(db: Session, session: TutorSession, question: str,
           help_mode: str | None = None) -> TutorMessage:
    """پاسخ کامل (بدون جریان) — شامل ثبت پیام‌ها و ارجاع‌های معتبر؛
    بر پایه نردبان راهنمایی: سؤال راهنما → مفهوم مرتبط → مثال ساده‌تر →
    حل جزئی → راه‌حل کامل فقط با درخواست دانشجو."""
    chunks = _build_context(db, session, question)
    gateway = AIGateway(db)
    policy = _help_policy(session, help_mode)
    out: TutorOut = gateway.run(
        "tutor_answer",
        {"question": question, "mode": session.mode,
         "help_mode": policy["help_mode"],
         "max_ladder_level": policy["max_ladder_level"],
         "learner_state": _learner_state(db, session),
         "context_chunks": [
             {"id": ch["chunk_id"], "resource_id": ch["resource_id"],
              "resource_title": ch["resource_title"],
              "locator": ch["locator"], "text": ch["text"]}
             for ch in chunks
         ]},
        schema=TutorOut,
        created_by=session.student_id,
    )
    # بررسی خروجی: ارجاع فقط به منابع واقعاً بازیابی‌شده — نقل‌قول ساختگی حذف می‌شود
    valid_resources = {ch["resource_id"]: ch for ch in chunks}
    citations = [c for c in out.citations if c.resource_id in valid_resources]
    db.add(TutorMessage(session_id=session.id, role="user", content=question))
    msg = TutorMessage(
        session_id=session.id, role="assistant", content=out.answer,
        citations=[{"resource_id": c.resource_id, "locator": c.locator,
                    "quote": c.quote,
                    "resource_title": valid_resources[c.resource_id]["resource_title"]}
                   for c in citations],
        meta={"insufficient_evidence": out.insufficient_evidence,
              "needs_teacher": out.needs_teacher, "mode": session.mode,
              "help_mode": out.help_mode or policy["help_mode"],
              "ladder_level": out.ladder_level or 0,
              "policy_note": policy["note"]},
    )
    db.add(msg)
    db.flush()
    return msg


def stream_answer(db: Session, session: TutorSession, question: str):
    """پاسخ تدریجی (SSE). خروجی مدل در پایان اعتبارسنجی و ذخیره می‌شود.

    با ارائه‌دهنده mock، پاسخ کامل از قبل محاسبه و تکه‌تکه ارسال می‌شود؛
    با ارائه‌دهنده واقعی، توکن‌ها به‌صورت جریانی می‌آیند.
    """
    chunks = _build_context(db, session, question)
    inputs = {
        "question": question, "mode": session.mode,
        "learner_state": _learner_state(db, session),
        "context_chunks": [
            {"id": ch["chunk_id"], "resource_id": ch["resource_id"],
             "resource_title": ch["resource_title"],
             "locator": ch["locator"], "text": ch["text"]}
            for ch in chunks
        ],
    }
    db.add(TutorMessage(session_id=session.id, role="user", content=question))
    db.flush()

    valid_resources = {ch["resource_id"]: ch for ch in chunks}
    gateway = AIGateway(db)
    final_text, citations, meta = "", [], {}
    for event in gateway.stream("tutor_answer", inputs, schema=TutorOut):
        if event["type"] == "token":
            yield {"type": "token", "text": event["text"]}
        else:
            data = event["data"]
            final_text = data.get("answer", "")
            citations = [c for c in data.get("citations", [])
                         if c.get("resource_id") in valid_resources]
            meta = {"insufficient_evidence": data.get("insufficient_evidence", False),
                    "needs_teacher": data.get("needs_teacher", False), "mode": session.mode}
    msg = TutorMessage(
        session_id=session.id, role="assistant", content=final_text,
        citations=[{"resource_id": c["resource_id"], "locator": c.get("locator", ""),
                    "quote": c.get("quote", ""),
                    "resource_title": valid_resources[c["resource_id"]]["resource_title"]}
                   for c in citations],
        meta=meta,
    )
    db.add(msg)
    db.commit()
    yield {"type": "done", "message_id": str(msg.id),
           "citations": msg.citations, "meta": meta}


def history(db: Session, session: TutorSession) -> list[dict]:
    msgs = (
        db.query(TutorMessage)
        .filter(TutorMessage.session_id == session.id)
        .order_by(TutorMessage.created_at)
        .all()
    )
    out = []
    for m in msgs:
        out.append({
            "id": str(m.id), "role": m.role, "content": m.content,
            "citations": m.citations,
            "reported": m.reported,
            "created_at": m.created_at.isoformat(),
        })
    return out


def report_message(db: Session, message: TutorMessage, issue: str) -> None:
    message.reported = True
    message.report_note = issue
    from app.models.ops import OutboxEvent

    db.add(OutboxEvent(event_type="tutor.message_reported", payload={
        "message_id": str(message.id), "issue": issue[:500],
    }))
    db.flush()


def get_own_session(db: Session, user, session_id) -> TutorSession:
    session = db.get(TutorSession, session_id)
    if session is None:
        raise not_found("نشست گفتگو یافت نشد")
    if str(session.student_id) != str(user.id):
        raise forbidden("این نشست متعلق به شما نیست")
    return session
