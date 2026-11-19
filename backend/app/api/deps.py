"""ابزارهای مشترک مسیرهای API: صفحه‌بندی، زمان‌بندی Job و پاسخ‌های استاندارد."""
import uuid

from fastapi import BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jobs import create_job, run_job
from app.core.security import get_current_user


class Pagination:
    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = max(1, page)
        self.page_size = max(1, min(100, page_size))

    def paginate(self, query):
        total = query.count()
        items = query.offset((self.page - 1) * self.page_size).limit(self.page_size).all()
        return {
            "items": items,
            "total": total,
            "page": self.page,
            "page_size": self.page_size,
        }


def schedule_job(background_tasks: BackgroundTasks, db: Session, kind: str,
                 payload: dict, user, idempotency_key: str | None = None) -> dict:
    """ثبت Job با پشتیبانی Idempotency-Key و زمان‌بندی اجرا؛ پاسخ 202."""
    job, existed = create_job(db, kind, payload, user.id, idempotency_key)
    if not existed:
        db.commit()  # اجرای پس‌زمینه با نشست مستقل، پس داده باید ثبت شود
        background_tasks.add_task(run_job, kind, job.id)
    else:
        db.commit()
    return {
        "job_id": str(job.id),
        "status": job.status,
        "idempotent_replay": existed,
        "message": "پردازش در پس‌زمینه آغاز شد؛ وضعیت با GET /jobs/{id} قابل پیگیری است.",
    }


def new_request_id() -> str:
    return uuid.uuid4().hex
