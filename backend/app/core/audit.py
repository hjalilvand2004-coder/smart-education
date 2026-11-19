"""ثبت رویدادهای حسابرسی — عملیات حساس (انتشار، نمره، دسترسی، تغییر مجوز) ثبت می‌شوند."""
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger("audit")


def audit(
    db: Session,
    actor_id,
    action: str,
    entity_type: str | None = None,
    entity_id=None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
    request_id: str | None = None,
) -> None:
    """ثبت حسابرسی؛ هرگز جریان اصلی را نمی‌شکند."""
    try:
        from app.models.ops import AuditLog

        db.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
                before=before,
                after=after,
                ip=ip,
                request_id=request_id,
            )
        )
        db.flush()
    except Exception:  # noqa: BLE001
        logger.exception("audit log failed for action=%s", action)
