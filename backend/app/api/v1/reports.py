"""گزارش جامع سامانه: خلاصه JSON، پیش‌نمایش HTML و خروجی چهارفرمتی."""
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import validation_error
from app.core.security import get_current_user
from app.models.identity import User
from app.services import report_builder

router = APIRouter(tags=["reports"])

STAFF_ROLES = ("PROFESSOR", "ASSISTANT", "GROUP_ADMIN",
               "EDUCATION_ADMIN", "TECH_ADMIN", "QUALITY_REVIEWER")


def _ensure_staff(user: User) -> None:
    if user.role not in STAFF_ROLES:
        from app.core.errors import forbidden
        raise forbidden("گزارش‌ها فقط برای اساتید و کارکنان آموزشی فعال است")


@router.get("/reports/summary")
def report_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_staff(user)
    return report_builder.collect_stats(db)


@router.get("/reports/preview")
def report_preview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_staff(user)
    content, _, _ = report_builder.build_report(db, "html")
    return HTMLResponse(content)


@router.get("/reports/export/{fmt}")
def report_export(fmt: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_staff(user)
    try:
        content, filename, media = report_builder.build_report(db, fmt)
    except ValueError:
        raise validation_error("فرمت خروجی پشتیبانی نمی‌شود؛ گزینه‌ها: pdf, docx, html, pptx")
    return Response(
        content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
