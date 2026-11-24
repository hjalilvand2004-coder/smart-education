"""همگام‌سازی زمان‌بندی‌شده پایه‌یار۳۶۰ — سند فنی: cron «0 */30 * * * *» (هر ۳۰ دقیقه).

حلقه async با اجرای همگام‌سازی در executor (کلاینت و DB همگام‌اند)؛ هرگز crash
نمی‌کند و خطای هر چرخه فقط لاگ/وضعیت می‌شود. کاربر اجرای خودکار: اولین کاربر
فعال آموزشی (PROFESSOR / ASSISTANT / GROUP_ADMIN / EDUCATION_ADMIN / TECH_ADMIN /
QUALITY_REVIEWER) تا گزارش‌ها و نسخه‌های پیش‌نویس با هویت واقعی ثبت شوند.
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.identity import User

log = logging.getLogger("payehyar.scheduler")

STAFF_ROLES = ("PROFESSOR", "ASSISTANT", "GROUP_ADMIN", "EDUCATION_ADMIN",
               "TECH_ADMIN", "QUALITY_REVIEWER")

_STATE: dict = {"last_run_at": None, "last_status": None, "last_message": None,
                "running": False, "cycles": 0}


def system_user(db: Session) -> User | None:
    """کاربر اجرای خودکار (زمان‌بند/رویدادها) — اولین کاربر فعال آموزشی."""
    return (db.query(User)
            .filter(User.is_active.is_(True), User.role.in_(STAFF_ROLES))
            .order_by(User.created_at.asc(), User.id.asc()).first())


def run_cycle() -> dict:
    """یک چرخه کامل همگام‌سازی خودکار: کاتالوگ (کامل) + دامنه‌های گسترش‌یافته."""
    from app.services import payehyar_catalog, payehyar_records

    db = SessionLocal()
    try:
        user = system_user(db)
        if user is None:
            return {"status": "SKIPPED",
                    "message": "کاربر اجرای خودکار یافت نشد؛ ابتدا یک کاربر آموزشی فعال بسازید."}
        cat = payehyar_catalog.sync_catalog(db, user, "FULL")
        ext = payehyar_records.sync_extended_domains(db, user)
        return {"status": cat.get("status"),
                "message": cat.get("message"),
                "extended": {"status": ext.get("status"),
                             "created": ext.get("courses_created"),
                             "message": ext.get("message")}}
    finally:
        db.close()


async def scheduler_loop() -> None:
    """حلقه همگام‌سازی خودکار — معادل cron سند فنی؛ با فاصله حداقل ۶۰ ثانیه."""
    s = get_settings()
    interval = max(60, int(s.payehyar_sync_interval_seconds))
    log.info("زمان‌بند پایه‌یار۳۶۰ فعال شد — فاصله: %s ثانیه", interval)
    while True:
        _STATE["running"] = True
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, run_cycle)
            _STATE["cycles"] += 1
            _STATE["last_run_at"] = datetime.now(timezone.utc).isoformat()
            _STATE["last_status"] = result.get("status")
            _STATE["last_message"] = result.get("message")
            log.info("چرخه همگام‌سازی خودکار: %s", result.get("message") or result.get("status"))
        except Exception:  # noqa: BLE001 — حلقه هرگز نباید بمیرد
            log.exception("خطا در چرخه همگام‌سازی خودکار پایه‌یار۳۶۰")
            _STATE["last_status"] = "FAILED"
        finally:
            _STATE["running"] = False
        await asyncio.sleep(interval)


def scheduler_status() -> dict:
    s = get_settings()
    return {"enabled": bool(s.payehyar_auto_sync),
            "interval_seconds": s.payehyar_sync_interval_seconds,
            "running": _STATE["running"], "cycles": _STATE["cycles"],
            "last_run_at": _STATE["last_run_at"],
            "last_status": _STATE["last_status"],
            "last_message": _STATE["last_message"]}
