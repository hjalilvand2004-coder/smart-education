"""عملیات: وضعیت Job، حسابرسی و مصرف AI."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import forbidden, not_found
from app.core.permissions import ensure_global_role
from app.core.security import get_current_user
from app.core.permissions import Role
from app.models.identity import User
from app.models.ops import AIRun, AuditLog, JobRun

router = APIRouter(tags=["ops"])


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(JobRun, job_id)
    if job is None:
        raise not_found("Job یافت نشد")
    if job.created_by and str(job.created_by) != str(user.id) and \
            user.role not in ("EDUCATION_ADMIN", "TECH_ADMIN"):
        raise forbidden("این Job متعلق به شما نیست")
    return {
        "id": str(job.id), "kind": job.kind, "status": job.status,
        "progress": job.progress, "steps": job.steps,
        "error": job.error, "result": job.result,
        "created_at": job.created_at.isoformat(),
    }


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user),
              status: str | None = None, limit: int = 50):
    q = db.query(JobRun)
    if user.role not in ("EDUCATION_ADMIN", "TECH_ADMIN"):
        q = q.filter(JobRun.created_by == user.id)
    if status:
        q = q.filter(JobRun.status == status)
    rows = q.order_by(JobRun.created_at.desc()).limit(min(limit, 100)).all()
    return [
        {"id": str(j.id), "kind": j.kind, "status": j.status, "progress": j.progress,
         "error": (j.error or "")[:200], "created_at": j.created_at.isoformat()}
        for j in rows
    ]


@router.get("/audit-logs")
def audit_logs(action: str | None = None, entity_type: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(get_current_user),
               limit: int = 100):
    """حسابرسی فقط برای نقش‌های مدیریتی (بخش ۱۶)."""
    ensure_global_role(user, {Role.EDUCATION_ADMIN, Role.TECH_ADMIN})
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    rows = q.order_by(AuditLog.created_at.desc()).limit(min(limit, 200)).all()
    from app.models.identity import User as U

    users = {str(u.id): u.full_name for u in
             db.query(U).filter(U.id.in_([r.actor_id for r in rows if r.actor_id] or [None]))} if rows else {}
    return [
        {
            "id": str(r.id), "actor": users.get(str(r.actor_id)),
            "action": r.action, "entity_type": r.entity_type,
            "entity_id": r.entity_id, "after": r.after, "before": r.before,
            "request_id": r.request_id, "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/ai-runs")
def ai_runs(db: Session = Depends(get_db), user: User = Depends(get_current_user), limit: int = 100):
    """مصرف و وضعیت مدل‌ها — پایش هزینه و کیفیت (بخش ۱۴.۲)."""
    ensure_global_role(user, {Role.EDUCATION_ADMIN, Role.TECH_ADMIN})
    rows = db.query(AIRun).order_by(AIRun.created_at.desc()).limit(min(limit, 200)).all()
    total_out = sum(r.tokens_out or 0 for r in rows)
    return {
        "items": [
            {"id": str(r.id), "purpose": r.purpose, "provider": r.provider,
             "model": r.model, "prompt_version": r.prompt_version, "status": r.status,
             "latency_ms": r.latency_ms, "tokens_in": r.tokens_in,
             "tokens_out": r.tokens_out, "error": r.error,
             "created_at": r.created_at.isoformat()}
            for r in rows
        ],
        "total_tokens_out": total_out,
    }
