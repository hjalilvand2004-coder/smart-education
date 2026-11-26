"""یکپارچه‌سازی با سامانه‌های ۳۶۰ (v3.9.0):

  • برنامه‌یار۳۶۰ — فقط «برنامهٔ ترم جاری متناسب با استاد»؛ دروس یکتا و سرفصل‌ها
    از پایه‌یار۳۶۰ می‌آیند (نه از برنامه‌یار).
  • درس‌یار۳۶۰ (darsyar360.ir) — مطلوبیات درسی/زمانی اساتید: تنظیمات اتصال،
    تست گام‌به‌گام، همگام‌سازی گروهی و رونوشت محلی.
  • پایه‌یار۳۶۰ — مرجع حقیقت درس/سرفصل/اساتید (همگام‌سازی کاتالوگ و دامنه‌ها).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import forbidden
from app.core.security import get_current_user
from app.models.identity import User
from app.models.journey import PayehyarRecord
from app.core.audit import audit
from app.services.programyar import DEFAULT_BASE_URL, ProgramyarClient

router = APIRouter(tags=["integration"])

STAFF_GLOBAL_ROLES = ("PROFESSOR", "ASSISTANT", "GROUP_ADMIN",
                      "EDUCATION_ADMIN", "TECH_ADMIN", "QUALITY_REVIEWER")


def _ensure_staff_user(user: User) -> None:
    if user.role not in STAFF_GLOBAL_ROLES:
        raise forbidden("این بخش فقط برای اساتید و کارکنان آموزشی فعال است")


@router.get("/integration/programyar/status")
def programyar_status(user: User = Depends(get_current_user)):
    """وضعیت اتصال به برنامه‌یار۳۶۰ — سرویس «برنامهٔ ترم جاری»."""
    import httpx

    s = get_settings()
    base = (s.programyar_base_url or DEFAULT_BASE_URL).rstrip("/")
    reachable, auth_required = False, False
    try:
        with httpx.Client(base_url=base, timeout=8.0) as client:
            resp = client.get("/api/auth/me")
            if resp.status_code == 404:
                resp = client.get("/")
            reachable = resp.status_code < 500
            auth_required = resp.status_code in (401, 403) or "وارد شوید" in resp.text
    except httpx.HTTPError:
        reachable = False
    return {
        "base_url": base,
        "reachable": reachable,
        "auth_required": auth_required,
        "credentials_configured": bool(s.programyar_username and s.programyar_password),
        "scope": "فقط برنامهٔ ترم جاری متناسب با استاد — دروس یکتا و سرفصل‌ها از پایه‌یار۳۶۰ می‌آیند.",
        "message": ("برنامه‌یار۳۶۰ در دسترس است" if reachable
                    else "اتصال به برنامه‌یار۳۶۰ برقرار نشد؛ برنامه در «نمونهٔ قطعی» نمایش داده می‌شود."),
    }


@router.get("/integration/programyar/schedule")
def programyar_schedule(professor_ext_id: str | None = None, refresh: bool = False,
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """برنامهٔ ترم جاری متناسب با استاد — از برنامه‌یار۳۶۰ با نمونهٔ قطعی در نبود سرویس.

    استادِ واردشده به‌طور پیش‌فرض برنامهٔ خودش را می‌بیند (تطبیق ایمیل/نام با
    رونوشت اساتید پایه‌یار)؛ کارکنان آموزشی می‌توانند ext_id استاد دلخواه را
    بدهند تا برنامهٔ او نمایش داده شود."""
    _ensure_staff_user(user)
    from app.services import programyar as py

    prof, matched = _resolve_professor(db, user, professor_ext_id)
    entries, source = None, "demo"
    if prof.get("ext_id"):
        client = ProgramyarClient()
        live = client.fetch_schedule(str(prof["ext_id"]))
        if live:
            entries, source = live["entries"], "live"
    if entries is None:
        demo = py.demo_schedule(prof, py.course_pool_for(db))
        entries = demo["entries"]
    audit(db, user.id, "PROGRAMYAR_SCHEDULE_VIEW", "professor", prof.get("ext_id") or "-",
          after={"source": source, "entries": len(entries), "refresh": bool(refresh)})
    db.commit()
    return {
        "ok": True, "source": source,
        "term": py.current_term_label(),
        "professor": prof,
        "matched_profile": matched,
        "entries": entries,
        "days": list(py.DAYS),
        "slots": [{"start": s, "end": e} for s, e in py.SLOTS],
        "total_weekly_hours": round(len(entries) * 1.5),
        "message": ("برنامه به‌صورت زنده از برنامه‌یار۳۶۰ واکشی شد." if source == "live" else
                    "سرویس برنامهٔ ترم برنامه‌یار۳۶۰ در دسترس/پیکربندی نیست؛ نمونهٔ قطعی "
                    "بر پایهٔ درس‌های همین سامانه نمایش داده می‌شود."),
    }


def _resolve_professor(db: Session, user: User,
                       ext_id: str | None) -> tuple[dict, bool]:
    """انتخاب استادِ هدف برنامه: درخواست صریح کارکنان > تطبیق خود استاد > جانشین."""
    def _rec_summary(rec: PayehyarRecord) -> dict:
        from app.services import darsyar_service
        return darsyar_service.professor_summary(db, rec)

    if ext_id:
        rec = (db.query(PayehyarRecord)
               .filter(PayehyarRecord.domain == "professors",
                       PayehyarRecord.external_id == ext_id,
                       PayehyarRecord.is_deleted == False)  # noqa: E712
               .first())
        if rec is not None:
            return _rec_summary(rec), True
        return {"ext_id": ext_id, "name": "استاد", "department": ""}, False

    # تطبیق خود کاربر با رونوشت اساتید (ایمیل دقیق > نام)
    query = (db.query(PayehyarRecord)
             .filter(PayehyarRecord.domain == "professors",
                     PayehyarRecord.is_deleted == False))  # noqa: E712
    for rec in query.all():
        p = rec.payload or {}
        if user.email and p.get("email") and str(p["email"]).lower() == user.email.lower():
            return _rec_summary(rec), True
    for rec in query.all():
        p = rec.payload or {}
        name = (p.get("full_name") or p.get("name") or rec.title or "")
        if name and user.full_name and str(name).strip() == user.full_name.strip():
            return _rec_summary(rec), True
    # بدون رونوشتِ هم‌نام: استاد با شناسهٔ کاربری خودش برنامه می‌بیند (نمونهٔ قطعی)
    return {"ext_id": user.username, "name": user.full_name, "department": ""}, False


# ---------- پایه‌یار۳۶۰: مرجع حقیقت درس/سرفصل (بازخورد ۳.۱) ----------

class BaseyarSyncIn(BaseModel):
    course_id: str
    mode: str = "INITIAL_PULL"  # INITIAL_PULL / CHANGE_EVENT / RECONCILE


@router.post("/integration/baseyar/sync")
def baseyar_sync(body: BaseyarSyncIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """همگام‌سازی رونوشت درس/سرفصل با مرجع پایه‌یار۳۶۰ (سه مسیر).

    تغییر نسخه سرفصل هرگز بی‌صدا اعمال نمی‌شود؛ گزارش تغییر و نگاشت‌های
    نیازمند بررسی استاد تولید می‌شود و شواهد/محتوا به نسخه خود وفادار می‌مانند."""
    _ensure_staff_user(user)
    from app.services import baseyar_service

    return baseyar_service.sync_course(db, user, body.course_id, body.mode)


@router.get("/integration/baseyar/status")
def baseyar_status(course_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _ensure_staff_user(user)
    from app.services import baseyar_service

    return baseyar_service.status_for(db, course_id)


@router.post("/integration/baseyar/reviews/{log_id}/apply")
def baseyar_apply_review(log_id: str, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """پس از بررسی استاد: هم‌ترازکردن رونوشت با نسخه مرجع + پاک‌سازی پرچم‌های بررسی."""
    _ensure_staff_user(user)
    from app.services import baseyar_service

    return baseyar_service.apply_review(db, user, log_id)


# ---------- پایه‌یار۳۶۰: همگام‌سازی کاتالوگ دروس + سرفصل‌ها (استقرار واقعی) ----------

class PayehyarSyncIn(BaseModel):
    mode: str = "FULL"  # FULL / INCREMENTAL


@router.post("/integration/payehyar/sync")
def payehyar_sync(body: PayehyarSyncIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """همگام‌سازی جدول دروس و سرفصل‌ها از پایه‌یار۳۶۰.

    FULL: واکشی کاتالوگ کامل و upsert همه درس‌ها (با پیوند درس محلی هم‌کد).
    تغییر نسخه سرفصل مرجع → نسخه پیش‌نویس REFERENCE_SYNC + وضعیت
    REVIEW_REQUIRED؛ هرگز بی‌صدا اعمال نمی‌شود. خطای احراز هویت با راهنمای
    دقیق تنظیم (کلید API / کاربر توسعه) برگردانده می‌شود."""
    _ensure_staff_user(user)
    from app.services import payehyar_catalog

    return payehyar_catalog.sync_catalog(db, user, body.mode)


@router.get("/integration/payehyar/status")
def payehyar_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """وضعیت اتصال به پایه‌یار۳۶۰ + آمار رونوشت مرجع + آخرین اجرا."""
    _ensure_staff_user(user)
    from app.services import payehyar_catalog

    return payehyar_catalog.catalog_status(db)


@router.get("/integration/payehyar/logs")
def payehyar_logs(limit: int = 20, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """تاریخچه اجراهای همگام‌سازی کاتالوگ."""
    _ensure_staff_user(user)
    from app.services import payehyar_catalog

    return {"items": payehyar_catalog.recent_logs(db, limit)}


# ---------- پایه‌یار۳۶۰: یکپارچگی کامل طبق سند فنی (v3.4.0) ----------

class PayehyarExtendedSyncIn(BaseModel):
    domains: list[str] | None = None  # خالی = همه دامنه‌های پیکربندی‌شده
    since: str | None = None          # دلتا طبق سند (بدون since = کامل)


@router.post("/integration/payehyar/sync-extended")
def payehyar_sync_extended(body: PayehyarExtendedSyncIn | None = None,
                           db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """همگام‌سازی دامنه‌های گسترش‌یافته (اساتید/کلاس‌ها/گروه‌های آموزشی/مجموعه‌های مرجع).

    هر دامنه مستقل واکشی می‌شود؛ شکست هر دامنه فقط هشدار است و بقیه ادامه
    می‌یابند. رکوردها «یکتا و تفکیکی» در payehyar_masterdata_records نگه داشته
    می‌شوند (UNIQUE(domain, external_id) + تشخیص تغییر واقعی با content_hash)."""
    _ensure_staff_user(user)
    from app.services import payehyar_records

    b = body or PayehyarExtendedSyncIn()
    return payehyar_records.sync_extended_domains(db, user, domains=b.domains,
                                                  since=b.since)


@router.get("/integration/payehyar/records/{domain}")
def payehyar_records_view(domain: str, limit: int = 50, offset: int = 0,
                          include_deleted: bool = False,
                          db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    """فهرست رکوردهای همگام‌شده یک دامنه گسترش‌یافته (صفحه‌بندی limit/offset)."""
    _ensure_staff_user(user)
    from app.services import payehyar_records

    return payehyar_records.records_list(db, domain, limit=limit, offset=offset,
                                         include_deleted=include_deleted)


@router.get("/integration/payehyar/system-status")
def payehyar_system_status(db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """وضعیت زیرساخت خودکار یکپارچگی: زمان‌بند، رویدادهای RabbitMQ و آمار رکوردها."""
    _ensure_staff_user(user)
    from app.services import payehyar_events, payehyar_records, payehyar_scheduler

    return {
        "scheduler": payehyar_scheduler.scheduler_status(),
        "events": payehyar_events.events_status(),
        "records_counts": payehyar_records.domain_counts(db),
        "extended_domains": payehyar_records.extended_domains(),
    }

# ---------- پایه‌یار۳۶۰: تنظیمات و تست اتصال (v3.4.2 — بدون نیاز به .env) ----------

class PayehyarConnectionIn(BaseModel):
    base_url: str | None = None  # None=بدون تغییر، ""=بازگشت به پیش‌فرض کد
    api_key: str | None = None   # None=بدون تغییر، ""=پاک کردن کلید


class PayehyarTestIn(BaseModel):
    base_url: str | None = None  # override فقط برای «تست پیش از ذخیره»
    api_key: str | None = None


@router.get("/integration/payehyar/connection")
def payehyar_connection_view(db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    """تنظیمات مؤثر اتصال — کلید فقط ماسک‌شده (pyk_XXXX…XXXX) برگردانده می‌شود."""
    _ensure_staff_user(user)
    from app.services import payehyar_connection

    return payehyar_connection.connection_view(db)


@router.put("/integration/payehyar/connection")
def payehyar_connection_save(body: PayehyarConnectionIn,
                             db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    """ذخیرهٔ آدرس/کلید اتصال در دیتابیس محلی — بلافاصله در همگام‌سازی بعدی اعمال می‌شود.

    کلید در دیتابیس همین دستگاه نگه داشته می‌شود؛ جایگزین تنظیم S360_PAYEHYAR_API_KEY
    در .env است (متغیر محیطی همچنان کار می‌کند و دیتابیس بر آن اولویت دارد)."""
    _ensure_staff_user(user)
    from app.core.errors import validation_error
    from app.services import payehyar_connection

    try:
        return payehyar_connection.save_connection(db, base_url=body.base_url,
                                                   api_key=body.api_key)
    except ValueError as exc:
        raise validation_error(str(exc)) from exc


@router.post("/integration/payehyar/test-connection")
def payehyar_test_connection(body: PayehyarTestIn | None = None,
                             db: Session = Depends(get_db),
                             user: User = Depends(get_current_user)):
    """تست گام‌به‌گام اتصال: دسترسی شبکه → احراز هویت کلید → پیش‌نمایش داده.

    اگر body داده شود (تست پیش از ذخیره) با همان مقادیر تست می‌گیرد؛ در غیر این
    صورت با تنظیمات مؤثر فعلی (دیتابیس/متغیر محیطی)."""
    _ensure_staff_user(user)
    from app.services import payehyar_connection

    b = body or PayehyarTestIn()
    return payehyar_connection.test_connection(db, base_url=b.base_url,
                                               api_key=b.api_key)


# ---------- درس‌یار۳۶۰ (darsyar360.ir): تنظیمات + تست + همگام‌سازی مطلوبیات (v3.9.0) ----------

class DarsyarConnectionIn(BaseModel):
    base_url: str | None = None        # None=بدون تغییر، ""=بازگشت به پیش‌فرض کد
    api_key: str | None = None         # None=بدون تغییر، ""=پاک کردن کلید
    timeout_seconds: int | None = None


class DarsyarTestIn(BaseModel):
    base_url: str | None = None  # override فقط برای «تست پیش از ذخیره»
    api_key: str | None = None


class DarsyarSyncIn(BaseModel):
    refresh: bool = True       # با کش ۱۲ساعته مخالفت و واکشی تازه
    limit: int = 100


@router.get("/integration/darsyar/connection")
def darsyar_connection_view(db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """تنظیمات مؤثر اتصال به درس‌یار۳۶۰ — کلید فقط ماسک‌شده برمی‌گردد."""
    _ensure_staff_user(user)
    from app.services import darsyar_connection

    return darsyar_connection.connection_view(db)


@router.put("/integration/darsyar/connection")
def darsyar_connection_save(body: DarsyarConnectionIn,
                            db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """ذخیرهٔ آدرس/کلید/تایم‌اوت درس‌یار۳۶۰ در دیتابیس محلی — بی‌نیاز از .env."""
    _ensure_staff_user(user)
    from app.core.errors import validation_error
    from app.services import darsyar_connection

    try:
        return darsyar_connection.save_connection(db, base_url=body.base_url,
                                                  api_key=body.api_key,
                                                  timeout_seconds=body.timeout_seconds)
    except ValueError as exc:
        raise validation_error(str(exc)) from exc


@router.post("/integration/darsyar/test-connection")
def darsyar_test_connection(body: DarsyarTestIn | None = None,
                            db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """تست گام‌به‌گام اتصال به درس‌یار۳۶۰: دسترسی شبکه → احراز هویت کلید."""
    _ensure_staff_user(user)
    from app.services import darsyar_connection

    b = body or DarsyarTestIn()
    return darsyar_connection.test_connection(db, base_url=b.base_url,
                                              api_key=b.api_key)


@router.post("/integration/darsyar/sync")
def darsyar_sync(body: DarsyarSyncIn | None = None,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """همگام‌سازی گروهی مطلوبیات درسی/زمانی همهٔ اساتید از درس‌یار۳۶۰.

    مالک داده سامانهٔ درس‌یار است؛ این مسیر فقط «رونوشت همگام‌شده» را به‌روز
    می‌کند. اساتید باید ابتدا از پایه‌یار۳۶۰ همگام شده باشند."""
    _ensure_staff_user(user)
    from app.services import darsyar_service

    b = body or DarsyarSyncIn()
    result = darsyar_service.sync_all_preferences(db, refresh=b.refresh, limit=b.limit)
    if result.get("ok"):
        audit(db, user.id, "DARSYAR_PREFERENCES_SYNC", "integration", "darsyar360",
              after={"total": result.get("total"), "live": result.get("live"),
                     "demo": result.get("demo")})
        db.commit()
    return result


@router.get("/integration/darsyar/preferences")
def darsyar_preferences_overview(db: Session = Depends(get_db),
                                 user: User = Depends(get_current_user)):
    """رونوشت‌های ذخیره‌شدهٔ مطلوبیات برای جدول صفحهٔ درس‌یار۳۶۰."""
    _ensure_staff_user(user)
    from app.services import darsyar_service

    return darsyar_service.preferences_overview(db)
