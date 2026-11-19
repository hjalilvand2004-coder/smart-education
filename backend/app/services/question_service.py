"""بانک سؤال و طراحی ارزیابی هوشمند (بخش ۵).

- سؤال تولیدی AI با status=AI_GENERATED وارد می‌شود و فقط پس از تأیید نقش مجاز
  APPROVED می‌شود؛ در آزمون رسمی فقط سؤال تأییدشده استفاده می‌شود.
- بررسی مشابهت با بانک موجود، تشخیص سؤال تکراری/ساختگی.
- اعتبارسنجی ساختاری: سازگاری پاسخ و گزینه‌ها، وجود توضیح، قالب متناسب با نوع.
"""
import hashlib

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.schemas import QuestionsOut
from app.core.audit import audit
from app.core.config import get_settings
from app.core.errors import validation_error
from app.models.concepts import Concept, ConceptMisconception
from app.models.questions import Question, QuestionConcept, QuestionVersion
from app.services.concept_service import get_prerequisites

ANSWER_KEYS_BY_TYPE = {
    "MCQ": ("correct",),
    "MULTI_SELECT": ("correct",),
    "TRUE_FALSE": ("correct",),
    "NUMERIC": ("value",),
    "SHORT_ANSWER": ("accepted",),
    "ESSAY": ("reference",),
    "CASE": ("reference",),
}


def validate_question_structure(qtype: str, body: str, options: list | None,
                                answer: dict, explanation: str | None,
                                rubric: list | None) -> list[str]:
    """بررسی ساختاری؛ خروجی: فهرست هشدارها."""
    issues = []
    if not (body or "").strip():
        issues.append("صورت سؤال خالی است")
    if qtype in ("MCQ", "MULTI_SELECT"):
        if not options or len(options) < 3:
            issues.append("تعداد گزینه‌ها کمتر از حد لازم است")
        else:
            keys = {o.get("key") for o in options}
            correct = answer.get("correct") or []
            if not correct:
                issues.append("پاسخ مرجع تعیین نشده است")
            elif not set(correct).issubset(keys):
                issues.append("کلید پاسخ با گزینه‌ها همخوانی ندارد")
            if qtype == "MCQ" and len(correct) != 1:
                issues.append("سؤال چندگزینه‌ای باید دقیقاً یک کلید داشته باشد")
    elif qtype == "TRUE_FALSE":
        if answer.get("correct") not in ("TRUE", "FALSE"):
            issues.append("پاسخ درست/نادرست باید TRUE یا FALSE باشد")
    elif qtype == "NUMERIC":
        if answer.get("value") is None:
            issues.append("مقدار عددی پاسخ تعریف نشده است")
    elif qtype in ("SHORT_ANSWER",):
        if not answer.get("accepted"):
            issues.append("پاسخ‌های معتبر تعریف نشده‌اند")
    elif qtype in ("ESSAY", "CASE"):
        if not rubric:
            issues.append("روبرک برای سؤال تشریحی الزامی است")
    if not (explanation or "").strip():
        issues.append("توضیح پاسخ وجود ندارد")
    return issues


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    for a, b in (("ي", "ی"), ("ك", "ک"), ("ة", "ه"), ("‌", " ")):
        text = text.replace(a, b)
    text = " ".join(text.split())
    return text


def similarity(body_a: str, body_b: str) -> float:
    """مشابهت ساده واژگانی برای بررسی تکراری‌بودن."""
    wa = set(_normalize(body_a).split()) - {"و", "در", "به", "از", "که", "این", "را", "است"}
    wb = set(_normalize(body_b).split()) - {"و", "در", "به", "از", "که", "این", "را", "است"}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def check_bank_similarity(db: Session, course_id, body: str, exclude_id=None) -> float:
    approved = (
        db.query(QuestionVersion)
        .join(Question, QuestionVersion.question_id == Question.id)
        .filter(Question.course_id == course_id,
                Question.status.in_(("APPROVED", "PENDING_REVIEW")))
    ).all()
    best = 0.0
    for qv in approved:
        if exclude_id and str(qv.question_id) == str(exclude_id):
            continue
        best = max(best, similarity(body, qv.body))
    return round(best, 3)


def generate_questions(db: Session, user, payload: dict, job_id=None) -> list[Question]:
    from app.models.syllabus import SyllabusVersion

    sv = db.get(SyllabusVersion, payload["syllabus_version_id"])
    if sv is None or str(sv.course_id) != str(payload["course_id"]):
        raise validation_error("نسخه سرفصل با درس همخوانی ندارد")
    concepts = db.query(Concept).filter(
        Concept.id.in_(payload["concept_ids"]), Concept.course_id == payload["course_id"]).all()
    if not concepts:
        raise validation_error("حداقل یک مفهوم از گراف درس لازم است")
    concept_inputs = []
    for c in concepts:
        prereqs = get_prerequisites(db, c.id)
        mcs = db.query(ConceptMisconception).filter(ConceptMisconception.concept_id == c.id).all()
        concept_inputs.append({
            "id": str(c.id), "key": c.key, "name": c.name,
            "description": c.description,
            "prerequisites": [p.name for p in prereqs if p],
            "misconceptions": [{"title": m.title} for m in mcs],
        })
    gateway = AIGateway(db)
    out: QuestionsOut = gateway.run(
        "question_generation",
        {
            "concepts": concept_inputs,
            "types": payload.get("types") or ["MCQ"],
            "count": payload.get("count", 5),
            "difficulty": payload.get("difficulty", "MEDIUM"),
            "usage": payload.get("usage", "PRACTICE"),
        },
        schema=QuestionsOut, created_by=user.id, job_id=job_id,
    )
    default_rubric = [{"criterion": "دقت مفهومی", "max_score": 5},
                      {"criterion": "کامل بودن استدلال", "max_score": 3},
                      {"criterion": "وضوح بیان", "max_score": 2}]
    questions = []
    for q in out.questions[: payload.get("count", 10)]:
        qtype = q.type if q.type in ANSWER_KEYS_BY_TYPE else "MCQ"
        rubric = q.model_dump().get("_rubric") or (default_rubric if qtype in ("ESSAY", "CASE") else None)
        qv_options = q.options if qtype in ("MCQ", "MULTI_SELECT") else None
        warnings = validate_question_structure(qtype, q.body, qv_options, q.answer, q.explanation, rubric)
        sim = check_bank_similarity(db, payload["course_id"], q.body)
        question = Question(
            course_id=payload["course_id"],
            type=qtype,
            difficulty_estimated=q.difficulty if q.difficulty in ("EASY", "MEDIUM", "HARD") else "MEDIUM",
            cognitive_level=q.cognitive_level,
            usage=payload.get("usage", "PRACTICE"),
            status="AI_GENERATED",
            source="AI",
            similarity_score=sim,
            created_by=user.id,
        )
        db.add(question)
        db.flush()
        version = QuestionVersion(
            question_id=question.id, version_number=1,
            body=q.body, options=qv_options, answer=q.answer,
            explanation=q.explanation,
            rubric=rubric,
            source_refs=[],
            generated_by_run_id=job_id, is_current=True,
        )
        db.add(version)
        db.flush()
        question.current_version_id = version.id
        concept = next((c for c in concepts if c.key == q.concept_key), concepts[0])
        db.add(QuestionConcept(question_id=question.id, concept_id=concept.id))
        if warnings or sim >= get_settings().similarity_warn_threshold:
            notes = []
            if warnings:
                notes.append("هشدارهای ساختاری: " + "؛ ".join(warnings))
            if sim >= get_settings().similarity_warn_threshold:
                notes.append(f"مشابهت {sim:.0%} با بانک موجود")
            question.notes = "؛ ".join(notes)
        db.flush()
        questions.append(question)
    db.flush()
    return questions


def create_manual_question(db: Session, user, payload: dict) -> Question:
    qtype = payload["type"]
    if qtype not in ANSWER_KEYS_BY_TYPE:
        raise validation_error("نوع سؤال نامعتبر است")
    rubric = payload.get("rubric") or ([{"criterion": "پاسخ", "max_score": 10}] if qtype == "ESSAY" else None)
    warnings = validate_question_structure(qtype, payload.get("body", ""), payload.get("options"),
                                           payload.get("answer") or {}, payload.get("explanation", ""), rubric)
    if warnings:
        raise validation_error("سؤال معتبر نیست: " + "؛ ".join(warnings))
    question = Question(
        course_id=payload["course_id"], type=qtype,
        difficulty_estimated=payload.get("difficulty_estimated", "MEDIUM"),
        cognitive_level=payload.get("cognitive_level", "UNDERSTAND"),
        usage=payload.get("usage", "PRACTICE"),
        status="DRAFT", source="HUMAN", created_by=user.id,
    )
    db.add(question)
    db.flush()
    version = QuestionVersion(
        question_id=question.id, version_number=1,
        body=payload["body"], options=payload.get("options"),
        answer=payload.get("answer") or {}, explanation=payload.get("explanation"),
        rubric=rubric, source_refs=payload.get("source_refs") or [], is_current=True,
    )
    db.add(version)
    db.flush()
    question.current_version_id = version.id
    for cid in payload.get("concept_ids", []):
        db.add(QuestionConcept(question_id=question.id, concept_id=cid))
    db.flush()
    return question


def review_question(db: Session, user, question: Question, decision: str, notes: str | None = None) -> Question:
    from app.core.permissions import QUESTION_APPROVER_ROLES, ensure_course_role

    ensure_course_role(db, user, question.course_id, QUESTION_APPROVER_ROLES)
    if question.status not in ("AI_GENERATED", "DRAFT", "PENDING_REVIEW"):
        raise validation_error("این وضعیت سؤال قابل تغییر نیست")
    if decision == "APPROVE":
        question.status = "APPROVED"
    elif decision == "REJECT":
        question.status = "REJECTED"
    else:
        raise validation_error("تصمیم نامعتبر است")
    audit(db, user.id, "QUESTION_REVIEW", "question", question.id,
          after={"decision": decision, "notes": (notes or "")[:200]})
    db.flush()
    return question


def question_payload(db: Session, question: Question, include_answer: bool = True) -> dict:
    from app.models.concepts import Concept as C

    qv = db.get(QuestionVersion, question.current_version_id) if question.current_version_id else None
    concept_ids = [str(qc.concept_id) for qc in
                   db.query(QuestionConcept).filter(QuestionConcept.question_id == question.id)]
    names = {str(c.id): c.name for c in db.query(C).filter(C.id.in_(concept_ids or [None]))} if concept_ids else {}
    return {
        "id": str(question.id),
        "type": question.type,
        "difficulty_estimated": question.difficulty_estimated,
        "difficulty_empirical": question.difficulty_empirical,
        "cognitive_level": question.cognitive_level,
        "usage": question.usage,
        "status": question.status,
        "similarity_score": question.similarity_score,
        "warnings": question.notes,
        "concepts": [{"id": cid, "name": names.get(cid)} for cid in concept_ids],
        "current_version": {
            "id": str(qv.id), "version_number": qv.version_number,
            "body": qv.body,
            "options": [dict(o) for o in (qv.options or [])],
            "answer": qv.answer if include_answer else None,
            "explanation": qv.explanation if include_answer else None,
            "rubric": qv.rubric,
        } if qv else None,
    }
