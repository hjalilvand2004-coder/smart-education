"""مدیریت Jobهای پس‌زمینه (بخش ۱۳ سند نیازمندی‌ها).

- وضعیت‌ها: QUEUED / RUNNING / SUCCEEDED / FAILED / CANCELLED
- پیشرفت مرحله‌ای و ثبت خطای قابل فهم
- Idempotency-Key: اجرای تکراری، Job جدید نساخته و تراکنش تکراری ایجاد نمی‌کند (AC-13)

MVP: اجرا با BackgroundTasks در همان فرایند API؛ در استقرار نهایی همین رابط
با Workerهای Celery (تفکیک Worker تولید فایل از Worker AI) جایگزین می‌شود.
"""
import traceback

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.errors import AppError


def create_job(
    db: Session,
    kind: str,
    payload: dict | None = None,
    created_by=None,
    idempotency_key: str | None = None,
) -> tuple["JobRun", bool]:
    """ساخت Job؛ در وجود کلید idempotency تکراری، همان Job قبلی بازگردانده می‌شود."""
    from app.models.ops import JobRun

    if idempotency_key:
        existing = (
            db.query(JobRun)
            .filter(JobRun.idempotency_key == idempotency_key, JobRun.kind == kind)
            .first()
        )
        if existing:
            return existing, True
    job = JobRun(
        kind=kind,
        payload=payload or {},
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    db.flush()
    return job, False


def add_step(db: Session, job, name: str, status: str = "DONE", note: str | None = None) -> None:
    steps = list(job.steps or [])
    steps.append({"name": name, "status": status, "note": note})
    job.steps = steps
    db.flush()


def set_progress(db: Session, job, pct: int) -> None:
    job.progress = max(0, min(100, int(pct)))
    db.flush()


def fail_job(db: Session, job, error_message: str) -> None:
    add_step(db, job, "خطا", status="FAILED", note=error_message[:500])
    job.status = "FAILED"
    job.error = error_message[:2000]
    db.flush()


def succeed_job(db: Session, job, result: dict | None = None) -> None:
    job.status = "SUCCEEDED"
    job.progress = 100
    if result:
        job.result = {**(job.result or {}), **result}
    elif not job.result:
        job.result = {}
    db.flush()


def cancel_job(db: Session, job) -> None:
    """لغو در نقاط امن: فقط Job در صف قابل لغو است."""
    if job.status == "QUEUED":
        job.status = "CANCELLED"
        db.flush()
        return True
    return False


def run_job(kind: str, job_id):
    """نقطه ورود اجرای پس‌زمینه؛ نشست مستقل خودش را می‌سازد.

   اجرای تکراری روی Job انجام‌شده اثری ندارد (idempotent در سطح وضعیت).
    """
    from app.models.ops import JobRun
    from app.workers.runner import get_handler

    db: Session = SessionLocal()
    try:
        job = db.get(JobRun, job_id)
        if job is None or job.status != "QUEUED":
            return
        job.status = "RUNNING"
        db.commit()
        handler = get_handler(kind)
        try:
            handler(db, job)
            if job.status == "RUNNING":
                succeed_job(db, job)
            db.commit()
        except AppError as exc:
            db.rollback()
            job = db.get(JobRun, job_id)
            fail_job(db, job, f"{exc.code}: {exc.message}")
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            job = db.get(JobRun, job_id)
            fail_job(db, job, f"INTERNAL: {exc}\n{traceback.format_exc(limit=3)}")
            db.commit()
    finally:
        db.close()
