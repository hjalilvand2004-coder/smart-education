"""بانک سؤال و تولید سؤال هوشمند (بخش ۵)."""
from fastapi import APIRouter, BackgroundTasks, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import Pagination, schedule_job
from app.core.database import get_db
from app.core.errors import not_found
from app.core.permissions import Role, ensure_course_role, ensure_staff
from app.core.security import get_current_user
from app.models.identity import User
from app.models.questions import Question
from app.services import question_service

router = APIRouter(tags=["questions"])


class QuestionIn(BaseModel):
    course_id: str
    type: str
    body: str
    options: list[dict] | None = None
    answer: dict = {}
    explanation: str | None = None
    rubric: list | None = None
    concept_ids: list[str] = []
    difficulty_estimated: str = "MEDIUM"
    cognitive_level: str = "UNDERSTAND"
    usage: str = "PRACTICE"
    source_refs: list[str] = []


class GenerationIn(BaseModel):
    course_id: str
    syllabus_version_id: str
    concept_ids: list[str] = []
    types: list[str] = ["MCQ"]
    count: int = 5
    difficulty: str = "MEDIUM"
    usage: str = "PRACTICE"


@router.get("/questions")
def list_questions(course_id: str, status: str | None = None, type: str | None = None,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user),
                   page: int = 1, page_size: int = 20):
    ensure_staff(db, user, course_id)
    q = db.query(Question).filter(Question.course_id == course_id)
    if status:
        q = q.filter(Question.status == status)
    if type:
        q = q.filter(Question.type == type)
    q = q.order_by(Question.created_at.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [question_service.question_payload(db, r) for r in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/question-generation-jobs", status_code=202)
def generation_job(body: GenerationIn, background_tasks: BackgroundTasks,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user),
                   idempotency_key: str | None = Header(default=None)):
    ensure_course_role(db, user, body.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    payload = body.model_dump()
    if not payload["concept_ids"]:
        from app.models.concepts import Concept
        from app.models.syllabus import SyllabusTopic
        from app.models.concepts import TopicConcept

        topics = db.query(SyllabusTopic).filter(
            SyllabusTopic.syllabus_version_id == body.syllabus_version_id).all()
        payload["concept_ids"] = [str(c.id) for c in
                                  db.query(Concept).join(TopicConcept, TopicConcept.concept_id == Concept.id)
                                  .filter(TopicConcept.topic_id.in_([t.id for t in topics] or [None]))
                                  .all()]
    return schedule_job(background_tasks, db, "question_generation", payload, user,
                        idempotency_key)


@router.post("/questions")
def create_question(body: QuestionIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    ensure_course_role(db, user, body.course_id, {Role.PROFESSOR, Role.ASSISTANT})
    question = question_service.create_manual_question(db, user, body.model_dump())
    db.commit()
    return question_service.question_payload(db, question)


@router.get("/questions/{question_id}")
def get_question(question_id: str, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    question = db.get(Question, question_id)
    if question is None:
        raise not_found("سؤال یافت نشد")
    ensure_staff(db, user, question.course_id)
    return question_service.question_payload(db, question)


class ReviewIn(BaseModel):
    decision: str
    notes: str | None = None


@router.post("/questions/{question_id}/reviews")
def review_question(question_id: str, body: ReviewIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """تأیید سؤال — سؤال تأییدشده در آزمون‌ها استفاده می‌شود (gate رسمی)."""
    question = db.get(Question, question_id)
    if question is None:
        raise not_found("سؤال یافت نشد")
    question = question_service.review_question(db, user, question, body.decision, body.notes)
    db.commit()
    return {"id": str(question.id), "status": question.status}
