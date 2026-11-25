"""مخزن عمومی رکوردهای masterdata پایه‌یار۳۶۰ — دامنه‌های گسترش‌یافته سند فنی.

دامنه‌های درس/سرفصل (unique-courses / split-courses / course-syllabi) در مدل‌های
بومی (Course / SyllabusVersion) توسط payehyar_catalog نگهداری می‌شوند؛ دامنه‌های
گسترش‌یافته سند فنی (professors / classrooms / academic-groups / reference-sets)
این ماژول به‌صورت «یکتا و تفکیکی» در payehyar_masterdata_records ذخیره می‌کند:
- UNIQUE(domain, external_id): بدون رکورد تکراری، بدون ادغام دو موجودیت.
- تشخیص تغییر واقعی با content_hash (بدون تغییر → up_to_date، بدون بازنویسی).
- تاب‌آوری: شکست واکشی هر دامنه فقط هشدار است و بقیه دامنه‌ها ادامه می‌یابند.
- دلتا: پارامتر since طبق سند (دلتا بدون since در سرویس مرجع = کامل).
"""
import hashlib
import json
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.models.journey import MasterdataSyncLog, PayehyarRecord
from app.services import payehyar_connection
from app.services.payehyar_client import PayehyarClient, PayehyarError

EXTENDED_DOMAIN_LABELS = {
    "professors": "اساتید",
    "classrooms": "کلاس‌ها",
    "academic-groups": "گروه‌های آموزشی",
    "reference-sets": "مجموعه‌های مرجع",
}

_KEY_FIELDS = ("code", "id", "uuid", "external_id", "national_id", "set_code")
_TITLE_FIELDS = ("title", "name", "full_name", "label", "title_fa")


def _first(raw: dict, *keys):
    for k in keys:
        v = raw.get(k)
        if v not in (None, ""):
            return v
    return None


def record_key(item: dict) -> str | None:
    """شناسه یکتای رکورد مرجع — بدون آن، رکورد نگاشت نمی‌شود (هشدار می‌گیرد)."""
    for k in _KEY_FIELDS:
        v = item.get(k)
        if v not in (None, ""):
            return str(v).strip()[:120]
    return None


def content_hash(item: dict) -> str:
    """هش پایدار محتوای رکورد برای تشخیص تغییر واقعی."""
    return hashlib.sha256(
        json.dumps(item, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def upsert_domain_records(db: Session, domain: str, items: list[dict],
                          source_route: str | None = None) -> dict:
    """upsert یکتا و تفکیکی رکوردهای یک دامنه — خروجی: آمار بدون تکرار."""
    created = updated = up_to_date = skipped = 0
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        ext_id = record_key(item)
        if not ext_id:
            skipped += 1
            continue
        if ext_id in seen:
            skipped += 1  # تکرار درون یک پاسخ — طبق اصل یکتایی حذف می‌شود
            continue
        seen.add(ext_id)
        h = content_hash(item)
        rec = (db.query(PayehyarRecord)
               .filter(PayehyarRecord.domain == domain,
                       PayehyarRecord.external_id == ext_id).first())
        if rec is None:
            rec = PayehyarRecord(domain=domain, external_id=ext_id)
            db.add(rec)
            created += 1
        elif rec.content_hash == h and not rec.is_deleted:
            up_to_date += 1
            continue
        else:
            updated += 1
        rec.payload = item
        rec.code = str(_first(item, "code", "set_code") or "")[:120] or None
        rec.title = str(_first(item, *_TITLE_FIELDS) or "")[:500] or None
        rec.content_hash = h
        rec.source = "payehyar360"
        rec.source_route = source_route
        rec.is_deleted = False
        rec.last_synced_at = utcnow()
    db.flush()
    return {"created": created, "updated": updated, "up_to_date": up_to_date,
            "skipped": skipped}


def mark_record_deleted(db: Session, domain: str, ext_id: str) -> bool:
    """تورنگاشت حذف (رویداد delete مرجع) — رکورد حفظ ولی بی‌اثر می‌شود."""
    rec = (db.query(PayehyarRecord)
           .filter(PayehyarRecord.domain == domain,
                   PayehyarRecord.external_id == str(ext_id)).first())
    if rec is None or rec.is_deleted:
        return False
    rec.is_deleted = True
    rec.last_synced_at = utcnow()
    db.flush()
    return True


def domain_counts(db: Session) -> dict[str, int]:
    """تعداد رکورد فعال هر دامنه گسترش‌یافته — برای کارت وضعیت صفحه همگام‌سازی."""
    out: dict[str, int] = {}
    for domain in extended_domains():
        out[domain] = (db.query(PayehyarRecord)
                       .filter(PayehyarRecord.domain == domain,
                               PayehyarRecord.is_deleted.is_(False)).count())
    return out


def extended_domains() -> list[str]:
    s = get_settings()
    return [d.strip() for d in s.payehyar_extended_domains.split(",") if d.strip()]


def records_list(db: Session, domain: str, limit: int = 50, offset: int = 0,
                 include_deleted: bool = False) -> dict:
    """فهرست رکوردهای همگام‌شده یک دامنه (برای endpoint مدیریتی)."""
    limit = max(1, min(limit, 200))
    q = db.query(PayehyarRecord).filter(PayehyarRecord.domain == domain)
    if not include_deleted:
        q = q.filter(PayehyarRecord.is_deleted.is_(False))
    total = q.count()
    rows = (q.order_by(PayehyarRecord.title.is_(None), PayehyarRecord.title)
            .offset(max(0, offset)).limit(limit).all())
    return {
        "domain": domain,
        "total": total,
        "items": [{
            "external_id": r.external_id, "code": r.code, "title": r.title,
            "is_deleted": r.is_deleted, "source_route": r.source_route,
            "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        } for r in rows],
    }


def sync_extended_domains(db: Session, user, domains: list[str] | None = None,
                          since: str | None = None) -> dict:
    """همگام‌سازی دامنه‌های گسترش‌یافته — هر دامنه مستقل؛ شکست = هشدار، نه توقف.

    گزارش در MasterdataSyncLog با حالت EXTENDED ثبت می‌شود؛ آمار کل در
    ستون‌های موجود لاگ نگه داشته می‌شود و جزئیات هر دامنه در warnings.
    """
    started = time.monotonic()
    targets = domains or extended_domains()
    log = MasterdataSyncLog(mode="EXTENDED", status="OK", triggered_by=user.id if user else None)
    db.add(log)
    db.flush()
    stats = {"courses_created": 0, "courses_updated": 0, "up_to_date": 0}
    details: list[dict] = []
    warnings: list[str] = []
    client = payehyar_connection.client_for(db)
    for domain in targets:
        label = EXTENDED_DOMAIN_LABELS.get(domain, domain)
        try:
            result = client.fetch_extended_domain(domain, since=since)
            res = upsert_domain_records(db, domain, result["items"],
                                        source_route=result.get("source"))
            stats["courses_created"] += res["created"]
            stats["courses_updated"] += res["updated"]
            stats["up_to_date"] += res["up_to_date"]
            details.append({"domain": domain, "label": label, "status": "OK",
                            "fetched": len(result["items"]), **res})
            warnings.extend(f"{domain}: {w}" for w in result.get("warnings", []))
        except PayehyarError as exc:
            details.append({"domain": domain, "label": label, "status": "SKIPPED",
                            "error": exc.code, "message": exc.message})
            warnings.append(f"{domain}: {exc.code} — {exc.message}")
    log.courses_created = stats["courses_created"]
    log.courses_updated = stats["courses_updated"]
    log.up_to_date = stats["up_to_date"]
    log.warnings = {"items": warnings[:30]} if warnings else None
    log.duration_ms = int((time.monotonic() - started) * 1000)
    log.error_message = (
        f"همگام‌سازی دامنه‌های گسترش‌یافته: "
        f"{stats['courses_created']} جدید، {stats['courses_updated']} به‌روزرسانی، "
        f"{stats['up_to_date']} بدون تغییر از {len(targets)} دامنه."
    )
    db.commit()
    return {
        "log_id": str(log.id), "mode": "EXTENDED", "status": log.status,
        "domains": details, **stats,
        "warnings": warnings[:30],
        "duration_ms": log.duration_ms,
        "message": log.error_message,
    }
