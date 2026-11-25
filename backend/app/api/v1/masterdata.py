"""API صفحه‌های MDM پایه‌یار۳۶۰ + امتیاز اساتید (v3.5.0).

قراردادها: همهٔ مسیرها برای غیر دانشجوها (اساتید/کارکنان) باز است — هم‌قرارداد
با integration.py. خطای سرویس مرجع با بدنهٔ {ok: False, error: {...}} برگردانده
می‌شود تا صفحه بتواند پیام فارسی و راهنما را نمایش دهد.
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import forbidden
from app.core.security import get_current_user
from app.models.identity import User
from app.services import masterdata
from app.services.payehyar_client import PayehyarError

router = APIRouter(tags=["masterdata"])


def _ensure_staff_user(user: User) -> None:
    """صفحه‌های MDM و امتیاز برای همهٔ غیر دانشجوها — هم‌قرارداد با integration."""
    if user.role == "STUDENT":
        raise forbidden("این بخش فقط برای اساتید و کارکنان آموزش است")


class GenerateIn(BaseModel):
    topic_seq: int | None = None  # None = تک‌سرفصلِ رکورد یا اولین سرفصل


# ---------- نمای کلی سه دامنه ----------

@router.get("/integration/payehyar/mdm/overview")
def mdm_overview(db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """آمار سه دامنهٔ MDM (دروس یکتا / تفکیکی / سرفصل) — سربرگ صفحه‌ها."""
    _ensure_staff_user(user)
    return masterdata.overview(db)


# ---------- لیست و همگام‌سازی تفکیکی هر دامنه ----------

@router.get("/integration/payehyar/mdm/{domain}")
def mdm_list(domain: str, q: str | None = None, parent_code: str | None = None,
             limit: int = 100, offset: int = 0,
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """لیست رکوردهای یک دامنه با جستجو — دادهٔ صفحه‌های مستقل ساید‌بار."""
    _ensure_staff_user(user)
    return masterdata.list_domain(db, domain, q=q, parent_code=parent_code,
                                  limit=min(limit, 500), offset=max(offset, 0))


@router.post("/integration/payehyar/mdm/{domain}/sync")
def mdm_sync(domain: str, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    """دکمهٔ «همگام‌سازی از پایه‌یار» در هر فرم — فقط همین دامنه به‌روز می‌شود."""
    _ensure_staff_user(user)
    try:
        return masterdata.sync_domain(db, user, domain)
    except PayehyarError as exc:
        return {"ok": False, "domain": domain,
                "error": {"code": exc.code, "message": exc.message, "hint": exc.hint}}


# ---------- سلسله‌مراتب: یکتا → تفکیکی → سرفصل ----------

@router.get("/integration/payehyar/hierarchy/{unique_code}")
def mdm_hierarchy(unique_code: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """درخت یک درس یکتا: درس‌های تفکیکی + سرفصل مصوب تطبیق‌یافته."""
    _ensure_staff_user(user)
    return masterdata.hierarchy(db, unique_code)


@router.get("/integration/payehyar/syllabus-records/{record_id}")
def mdm_record(record_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """جزئیات رکورد سرفصل + سرفصل‌های درسی با نسخهٔ محتوا و امتیاز هر کدام."""
    _ensure_staff_user(user)
    return masterdata.record_detail(db, record_id)


@router.post("/integration/payehyar/syllabus-records/{record_id}/generate")
def mdm_generate(record_id: str, body: GenerateIn | None = None,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """تولید محتوای کامل برای یک سرفصل درسی — پایپ‌لاین استاندارد + امتیاز استاد."""
    _ensure_staff_user(user)
    b = body or GenerateIn()
    try:
        return masterdata.generate_for_record(db, user, record_id, b.topic_seq)
    except Exception:
        db.rollback()
        raise


# ---------- خروجی‌های نسخهٔ محتوا ----------

@router.get("/integration/payehyar/content-versions/{version_id}/export/{fmt}")
def mdm_export(version_id: str, fmt: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """دانلود خروجی PDF/PPTX/HTML/DOCX — امتیاز خروجی خودکار ثبت می‌شود."""
    _ensure_staff_user(user)
    data, mime, filename = masterdata.export_content(db, user, version_id, fmt)
    return Response(
        content=data, media_type=mime,
        headers={"Content-Disposition":
                 f"attachment; filename=\"{filename.encode('ascii', 'ignore').decode() or 'content'}\"; "
                 f"filename*=UTF-8''{quote(filename)}"})


# ---------- امتیاز اساتید ----------

@router.get("/points/me")
def points_me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """جمع امتیاز من + رکوردهای اخیر — صفحهٔ «امتیاز اساتید»."""
    _ensure_staff_user(user)
    return masterdata.points_me(db, user)


@router.get("/points/leaderboard")
def points_leaderboard(db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """برترین مشارکت‌کنندگان تولید محتوا."""
    _ensure_staff_user(user)
    return masterdata.points_leaderboard(db, limit=10)
