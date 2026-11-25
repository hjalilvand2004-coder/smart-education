"""API اساتید — واکشی از پایه‌یار۳۶۰ + مطلوبیات از درس‌یار۳۶۰ (v3.7.0).

قراردادها: هم‌قرارداد با integration.py — همهٔ مسیرها برای غیر دانشجوها باز است.
خطای سرویس مرجع هرگز صفحه را نمی‌شکند؛ وضعیت منبع (live/demo) در پاسخ می‌آید.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import not_found, validation_error
from app.core.security import get_current_user
from app.models.identity import User
from app.models.journey import PayehyarRecord
from app.services import darsyar_service, masterdata
from app.services.payehyar_client import PayehyarError

router = APIRouter(tags=["professors"])


def _staff(user: User) -> None:
    if user.role == "STUDENT":
        from app.core.errors import forbidden
        raise forbidden("این بخش فقط برای اساتید و کارکنان آموزش است")


def _professor_record(db: Session, ext_id: str) -> PayehyarRecord:
    rec = (db.query(PayehyarRecord)
           .filter(PayehyarRecord.domain == "professors",
                   PayehyarRecord.external_id == ext_id,
                   PayehyarRecord.is_deleted == False)  # noqa: E712
           .first())
    if rec is None:
        raise not_found("استاد یافت نشد؛ ابتدا اساتید را از پایه‌یار۳۶۰ همگام‌سازی کنید")
    return rec


@router.get("/integration/professors")
def list_professors(q: str | None = None, limit: int = 60, offset: int = 0,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """فهرست اساتید همگام‌شده از پایه‌یار۳۶۰ (رونوشت محلی)."""
    _staff(user)
    query = (db.query(PayehyarRecord)
             .filter(PayehyarRecord.domain == "professors",
                     PayehyarRecord.is_deleted == False))  # noqa: E712
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(PayehyarRecord.title.ilike(like))
    total = query.count()
    rows = (query.order_by(PayehyarRecord.title.is_(None), PayehyarRecord.title)
            .offset(max(0, offset)).limit(min(200, max(1, limit))).all())
    return {"ok": True, "total": total, "source_system": "پایه‌یار۳۶۰",
            "items": [darsyar_service.professor_summary(db, r) for r in rows]}


@router.post("/integration/professors/sync")
def sync_professors(db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """همگام‌سازی اساتید از پایه‌یار۳۶۰ (دامنهٔ گسترش‌یافتهٔ professors)."""
    _staff(user)
    try:
        result = masterdata.sync_domain(db, user, "professors")
    except PayehyarError as exc:
        raise validation_error(
            f"همگام‌سازی اساتید از پایه‌یار۳۶۰ ناموفق بود: {exc.message} "
            f"(راهنما: {exc.hint or 'اتصال و کلید API را بررسی کنید'})")
    return result


@router.get("/integration/professors/{ext_id}")
def professor_detail(ext_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    _staff(user)
    rec = _professor_record(db, ext_id)
    return {"ok": True, **darsyar_service.professor_summary(db, rec)}


@router.get("/integration/professors/{ext_id}/preferences")
def professor_preferences(ext_id: str, refresh: bool = False,
                          db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """مطلوبیات درسی/زمانی استاد از درس‌یار۳۶۰ (darsyar360.ir) با کش ۱۲ساعته."""
    _staff(user)
    rec = _professor_record(db, ext_id)
    prof = darsyar_service.professor_summary(db, rec)
    try:
        payload = darsyar_service.get_preferences(
            db, {"ext_id": ext_id, "name": prof["name"]}, refresh=refresh)
    except Exception as exc:  # noqa: BLE001 — صفحه نباید بخسبد
        raise validation_error(f"واکشی مطلوبیات از درس‌یار۳۶۰ ناموفق بود: {str(exc)[:180]}")
    return payload


@router.get("/integration/professors/{ext_id}/matching-courses")
def professor_matching_courses(ext_id: str, db: Session = Depends(get_db),
                               user: User = Depends(get_current_user)):
    """درس‌های متناسب با مطلوبیات استاد — ورودی مستقیم به استودیوی تولید محتوا."""
    _staff(user)
    rec = _professor_record(db, ext_id)
    prof = darsyar_service.professor_summary(db, rec)
    payload = darsyar_service.get_preferences(db, {"ext_id": ext_id, "name": prof["name"]})
    courses = darsyar_service.matching_courses(db, payload)
    return {"ok": True, "preferences_source": payload.get("source"), "items": courses}
