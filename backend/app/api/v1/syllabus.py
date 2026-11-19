"""ورود سرفصل، تأیید نسخه‌ها و تفاوت نسخه‌ها (بخش ۳.۱)."""
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import schedule_job
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import not_found, validation_error
from app.core.permissions import (SYLLABUS_APPROVER_ROLES, Role,
                                  ensure_course_role)
from app.core.security import get_current_user
from app.core.storage import save_upload
from app.models.courses import Course
from app.models.identity import User
from app.models.syllabus import SyllabusVersion

router = APIRouter(tags=["syllabus"])


@router.post("/syllabus-imports", status_code=202)
def import_syllabus(
    background_tasks: BackgroundTasks,
    course_id: str = Form(...),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """ورود و استخراج اولیه ساختار سرفصل از متن/PDF/Word — خروجی پیش‌نویس است."""
    ensure_course_role(db, user, course_id,
                       {Role.PROFESSOR, Role.ASSISTANT, Role.GROUP_ADMIN, Role.EDUCATION_ADMIN})
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    content, file_name, file_path = "", None, None
    if file is not None:
        raw = file.file.read()
        if len(raw) > get_settings().max_upload_mb * 1024 * 1024:
            raise validation_error("حجم فایل بیش از حد مجاز است")
        info = save_upload(raw, file.filename or "syllabus", subdir="syllabus")
        file_path, file_name = info["path"], file.filename
        from app.services.rag import extract_file_text

        text = extract_file_text(raw, file.filename or "")
    if not (text or "").strip():
        raise validation_error("متن یا فایل سرفصل لازم است")
    payload = {
        "course_id": course_id, "text": text[:20000],
        "source_kind": ("DOCX" if (file_name or "").lower().endswith(".docx")
                        else "PDF" if (file_name or "").lower().endswith(".pdf") else "TEXT"),
        "file_name": file_name, "file_path": file_path,
    }
    return schedule_job(background_tasks, db, "syllabus_import", payload, user)


class ApproveIn(BaseModel):
    notes: str | None = None


@router.post("/syllabus-versions/{version_id}/approve")
def approve_syllabus(version_id: str, body: ApproveIn | None = None,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """تأیید انسانی ساختار — تنها مسیر اعتبار رسمی (AC-02)."""
    from app.services.syllabus_service import approve_version

    sv = db.get(SyllabusVersion, version_id)
    if sv is None:
        raise not_found("نسخه سرفصل یافت نشد")
    ensure_course_role(db, user, sv.course_id, SYLLABUS_APPROVER_ROLES)
    sv = approve_version(db, sv, user, (body.notes if body else None))
    db.commit()
    return {"id": str(sv.id), "status": sv.status, "version_number": sv.version_number}


@router.get("/syllabus-versions/{version_id}")
def get_syllabus_version(version_id: str, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    from app.api.v1.courses import syllabus_payload
    from app.core.permissions import ensure_staff

    sv = db.get(SyllabusVersion, version_id)
    if sv is None:
        raise not_found("نسخه سرفصل یافت نشد")
    ensure_staff(db, user, sv.course_id)
    return syllabus_payload(db, sv)


@router.get("/syllabus-versions/{version_id}/diff")
def diff_syllabus(version_id: str, against: str,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """گزارش اثر تغییر سرفصل (AC-06): فهرست موضوع‌ها/اهداف تغییر یافته."""
    from app.services.syllabus_service import diff_versions

    v1 = db.get(SyllabusVersion, version_id)
    v2 = db.get(SyllabusVersion, against)
    if v1 is None or v2 is None:
        raise not_found("نسخه سرفصل یافت نشد")
    from app.core.permissions import ensure_staff

    ensure_staff(db, user, v1.course_id)
    return diff_versions(db, v1, v2)
