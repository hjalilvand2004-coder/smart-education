"""استاد هوشمند گفتگو‌محور — مسیرهای API با پشتیبانی SSE (بخش ۸)."""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden, not_found
from app.core.security import get_current_user
from app.models.identity import User
from app.models.tutor import TutorMessage, TutorSession
from app.services import tutor_service

router = APIRouter(prefix="/tutor", tags=["tutor"])


class SessionIn(BaseModel):
    course_id: str
    mode: str = "LEARNING"
    assessment_id: str | None = None


@router.post("/sessions")
def create_session(body: SessionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = tutor_service.create_session(db, user, body.course_id, body.mode, body.assessment_id)
    db.commit()
    return {"id": str(session.id), "mode": session.mode, "course_id": body.course_id}


class MessageIn(BaseModel):
    content: str
    stream: bool = False


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, body: MessageIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """ارسال پیام؛ با stream=true پاسخ به‌صورت SSE تدریجی ارسال می‌شود."""
    session = tutor_service.get_own_session(db, user, session_id)
    if not (body.content or "").strip():
        raise forbidden("متن پیام خالی است")
    if body.stream:
        db.commit()  # داده پیش از جریان باید ثبت شود
        def event_gen():
            for event in tutor_service.stream_answer(db, session, body.content):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        return StreamingResponse(event_gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    msg = tutor_service.answer(db, session, body.content)
    db.commit()
    return {
        "id": str(msg.id), "role": "assistant", "content": msg.content,
        "citations": msg.citations, "meta": msg.meta,
    }


@router.get("/sessions/{session_id}/messages")
def get_history(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = tutor_service.get_own_session(db, user, session_id)
    return tutor_service.history(db, session)


class ReportIn(BaseModel):
    issue: str


@router.post("/messages/{message_id}/report")
def report_message(message_id: str, body: ReportIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """گزارش پاسخ نادرست — استاد امکان اصلاح دارد (بخش ۸)."""
    msg = db.get(TutorMessage, message_id)
    if msg is None:
        raise not_found("پیام یافت نشد")
    session = db.get(TutorSession, msg.session_id)
    if str(session.student_id) != str(user.id):
        raise forbidden()
    tutor_service.report_message(db, msg, body.issue)
    db.commit()
    return {"id": str(msg.id), "reported": True}
