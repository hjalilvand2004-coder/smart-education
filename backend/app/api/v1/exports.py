"""تولید خروجی‌ها و دریافت فایل (بخش‌های ۴.۳ و ۱۳.۲)."""
from fastapi import APIRouter, BackgroundTasks, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import schedule_job
from app.core.database import get_db
from app.core.errors import not_found, validation_error
from app.core.permissions import ensure_staff
from app.core.security import get_current_user
from app.core.storage import LocalStorage
from app.models.content import ContentDocument, ContentVersion
from app.models.exports import ExportArtifact, ExportJob
from app.models.identity import User

router = APIRouter(tags=["exports"])


class ExportIn(BaseModel):
    format: str = "PDF"
    options: dict | None = None


@router.post("/content-versions/{version_id}/exports", status_code=202)
def create_export(version_id: str, body: ExportIn, background_tasks: BackgroundTasks,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user),
                  idempotency_key: str | None = Header(default=None)):
    version = db.get(ContentVersion, version_id)
    if version is None:
        raise not_found("نسخه محتوا یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    ensure_staff(db, user, doc.course_id)
    fmt = body.format.upper()
    if fmt not in ("PDF", "PPTX", "HTML", "DOCX", "ZIP"):
        raise validation_error("قالب خروجی پشتیبانی نمی‌شود")
    export_job = ExportJob(
        content_version_id=version.id, format=fmt, options=body.options,
        created_by=user.id,
    )
    db.add(export_job)
    db.flush()
    payload = {"content_version_id": version_id, "format": fmt,
               "options": body.options or {}, "export_job_id": str(export_job.id)}
    resp = schedule_job(background_tasks, db, "export", payload, user, idempotency_key)
    export_job.job_run_id = resp.get("job_id")
    db.commit()
    resp["export_job_id"] = str(export_job.id)
    return resp


@router.get("/exports/{export_job_id}")
def export_status(export_job_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    export_job = db.get(ExportJob, export_job_id)
    if export_job is None:
        raise not_found("Job خروجی یافت نشد")
    version = db.get(ContentVersion, export_job.content_version_id)
    doc = db.get(ContentDocument, version.document_id)
    ensure_staff(db, user, doc.course_id)
    artifacts = (
        db.query(ExportArtifact)
        .filter(ExportArtifact.export_job_id == export_job.id)
        .all()
    )
    return {
        "id": str(export_job.id),
        "format": export_job.format,
        "status": export_job.status,
        "artifacts": [
            {"id": str(a.id), "file_name": a.file_name, "size": a.size_bytes,
             "sha256": a.sha256, "mime": a.mime, "template_version": a.template_version}
            for a in artifacts
        ],
    }


@router.get("/exports/{export_job_id}/download")
def download_export(export_job_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """دریافت فایل مجاز — کنترل دسترسی در سطح درس."""
    from fastapi import Response

    export_job = db.get(ExportJob, export_job_id)
    if export_job is None:
        raise not_found("Job خروجی یافت نشد")
    version = db.get(ContentVersion, export_job.content_version_id)
    doc = db.get(ContentDocument, version.document_id)
    ensure_staff(db, user, doc.course_id)
    artifact = (
        db.query(ExportArtifact)
        .filter(ExportArtifact.export_job_id == export_job.id)
        .order_by(ExportArtifact.created_at.desc())
        .first()
    )
    if artifact is None:
        raise not_found("فایل خروجی هنوز آماده نیست")
    path = LocalStorage().open_path(artifact.file_path)
    return Response(
        content=path.read_bytes(),
        media_type=artifact.mime,
        headers={"Content-Disposition": f'attachment; filename="{artifact.file_name}"'},
    )
