"""مصرف‌کننده رویدادهای masterdata پایه‌یار۳۶۰ از RabbitMQ — قرارداد سند فنی.

- exchange: ``payehyar.events`` (topic, durable) — routing key: ``payehyar.masterdata.#``
- صف اختصاصی: ``smart-learning.masterdata.q`` (durable) با dead-letter به DLQ
  ``smart-learning.masterdata.q.dlq`` (via exchange ``payehyar.events.dlx``).
- پردازش idempotent: کلید اصلی event_id در جدول ``smart_learning_event_inbox``؛
  رویداد تکراری (PROCESSED) بدون اثر دومین نادیده گرفته می‌شود.
- شکست پردازش → exception → ``msg.process(requeue=False)`` پیام را reject می‌کند
  و به DLQ می‌رود؛ وضعیت FAILED + پیام خطا در inbox ثبت می‌ماند.
- قطعی RabbitMQ مانع همگام‌سازی HTTP نیست؛ حلقه اتصال با تأخیر ۳۰ ثانیه ادامه می‌یابد.

شکل رویداد پذیرفته‌شده (هر دو سطح پشتیبانی می‌شود):
``{"event_id": "...", "event": "updated", "domain": "unique-courses", "payload": {...}}``
یا routing key ``payehyar.masterdata.unique-course.updated.v1`` با بدنه رکورد.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.journey import PayehyarEventInbox
from app.core.database import utcnow
from app.services import payehyar_records, payehyar_scheduler

log = logging.getLogger("payehyar.events")

# دامنه‌های بومی (درس/سرفصل) — بقیه دامنه‌ها به مخزن عمومی رکوردها می‌روند
NATIVE_DOMAINS = ("unique-courses", "split-courses", "course-syllabi")

_DOMAIN_ALIASES = {
    "unique-course": "unique-courses", "unique_courses": "unique-courses",
    "unique-courses": "unique-courses",
    "split-course": "split-courses", "split_courses": "split-courses",
    "split-courses": "split-courses",
    "syllabus": "course-syllabi", "course-syllabus": "course-syllabi",
    "course-syllabi": "course-syllabi", "syllabi": "course-syllabi",
    "professor": "professors", "professors": "professors", "instructor": "professors",
    "classroom": "classrooms", "classrooms": "classrooms",
    "academic-group": "academic-groups", "academic-groups": "academic-groups",
    "reference-set": "reference-sets", "reference-sets": "reference-sets",
}

_OP_ALIASES = {
    "created": "upsert", "updated": "upsert", "upsert": "upsert",
    "changed": "upsert", "imported": "upsert",
    "deleted": "delete", "removed": "delete", "tombstone": "delete",
}

_ROUTING_RE = re.compile(r"^payehyar\.masterdata\.([^.]+)\.([^.]+)\.v\d+$")

_STATE: dict = {"connected": False, "processed": 0, "duplicates": 0,
                "failed": 0, "last_event_at": None}


def _resolve_domain_op(payload: dict, routing_key: str | None) -> tuple[str, str]:
    """استخراج دامنه و نوع عملیات از بدنه رویداد یا routing key — پیش‌فرض upsert."""
    domain_raw = str(payload.get("domain") or "").strip()
    op_raw = str(payload.get("event") or payload.get("op") or "").strip().lower()
    if routing_key and (not domain_raw or not op_raw):
        m = _ROUTING_RE.match(routing_key)
        if m:
            domain_raw = domain_raw or m.group(1)
            op_raw = op_raw or m.group(2)
    domain = _DOMAIN_ALIASES.get(domain_raw.lower().replace(" ", "_"),
                                 domain_raw.lower().replace(" ", "_"))
    if not domain:
        domain = "unique-courses"
    op = _OP_ALIASES.get(op_raw, "upsert")
    return domain, op


def _apply_event(db, payload: dict, domain: str, op: str) -> None:
    """اعمال محتوای رویداد به رونوشت محلی — دامنه بومی یا مخزن عمومی."""
    from app.models.courses import Course
    from app.services import payehyar_catalog

    item = payload.get("payload") or payload.get("data") or payload.get("record") \
        or payload.get("item") or {}
    if not isinstance(item, (dict, list)) or (isinstance(item, dict) and not item):
        # بدنه = خود رکورد (شکل بدون envelope)
        if any(k in payload for k in ("title", "name", "code", "full_name")):
            item = payload
        else:
            return  # رویداد بدون محتوا — فقط در inbox ثبت می‌شود

    if op == "delete":
        ext = payehyar_records.record_key(item) if isinstance(item, dict) else None
        if ext and not domain.startswith("course") and domain not in NATIVE_DOMAINS:
            payehyar_records.mark_record_deleted(db, domain, ext)
        # درس بومی: حذف مرجع = نشان STALE (حذف نهایی با تصمیم استاد در همگام‌سازی بعدی)
        if isinstance(item, dict):
            ref = ext or item.get("code")
            course = None
            if ref:
                course = db.query(Course).filter(
                    Course.reference_id == str(ref)).first() or \
                    db.query(Course).filter(Course.code == str(ref)).first()
            if course and course.sync_state == "VALID":
                course.sync_state = "STALE"
        return

    items = item if isinstance(item, list) else [item]
    if domain in NATIVE_DOMAINS:
        user = payehyar_scheduler.system_user(db)
        if user is None:
            raise RuntimeError("کاربر اجرای خودکار یافت نشد؛ رویداد اعمال نشد.")
        for it in items:
            if not isinstance(it, dict):
                continue
            normalized, warn = (
                payehyar_catalog.normalize_documented_course(it)
                if payehyar_catalog._is_documented_course(it)
                else payehyar_catalog.normalize_course(it))
            if normalized is None:
                raise ValueError(warn or "رکورد رویداد مرجع نگاشت نشد")
            stats = {"courses_created": 0, "courses_updated": 0, "up_to_date": 0,
                     "syllabus_drafts_created": 0, "review_required": 0}
            payehyar_catalog._upsert_course(db, user, normalized, stats)
    else:
        payehyar_records.upsert_domain_records(db, domain, items)


def handle_event_payload(db, payload: dict, routing_key: str | None = None) -> str:
    """اعمال idempotent یک رویداد مرجع — خروجی: PROCESSED یا DUPLICATE.

    شکست اعمال → وضعیت FAILED در inbox + باز-افرازن استثنا (پیام → DLQ).
    """
    event_id = str(payload.get("event_id") or payload.get("id") or uuid.uuid4())
    inbox = db.get(PayehyarEventInbox, event_id)
    if inbox is not None and inbox.status == "PROCESSED":
        _STATE["duplicates"] += 1
        return "DUPLICATE"
    if inbox is None:
        inbox = PayehyarEventInbox(event_id=event_id, routing_key=routing_key,
                                   payload=payload, status="PENDING")
        db.add(inbox)
    domain, op = _resolve_domain_op(payload, routing_key)
    try:
        _apply_event(db, payload, domain, op)
        inbox.status = "PROCESSED"
        inbox.processed_at = utcnow()
        inbox.error = None
        db.commit()
        _STATE["processed"] += 1
        _STATE["last_event_at"] = datetime.now(timezone.utc).isoformat()
        return "PROCESSED"
    except Exception as exc:
        db.rollback()
        failed = db.get(PayehyarEventInbox, event_id)
        if failed is None:
            failed = PayehyarEventInbox(event_id=event_id, routing_key=routing_key,
                                        payload=payload, status="FAILED")
            db.add(failed)
        failed.status = "FAILED"
        failed.error = str(exc)[:1000]
        db.commit()
        _STATE["failed"] += 1
        raise


async def _apply_in_thread(payload: dict, routing_key: str | None) -> str:
    def _run() -> str:
        db = SessionLocal()
        try:
            return handle_event_payload(db, payload, routing_key=routing_key)
        finally:
            db.close()

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run)


async def _process_message(msg) -> None:
    try:
        payload = json.loads(msg.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("بدنه رویداد باید شیء JSON باشد")
    except (ValueError, UnicodeDecodeError) as exc:
        log.warning("رویداد غیر JSON نادیده گرفته شد: %s", exc)
        return
    await _apply_in_thread(payload, getattr(msg, "routing_key", None))


async def consume_forever() -> None:
    """حلقه مصرف رویدادها — اتصال مقاوم (aio_pika.connect_robust) با تلاش مجدد."""
    s = get_settings()
    creds = ""
    if s.payehyar_rabbitmq_user:
        creds = (f"{quote(s.payehyar_rabbitmq_user)}:"
                 f"{quote(s.payehyar_rabbitmq_password or '')}@")
    url = f"amqp://{creds}{s.payehyar_rabbitmq_host}:{s.payehyar_rabbitmq_port}/"
    while True:
        try:
            import aio_pika

            conn = await aio_pika.connect_robust(url)
            async with conn:
                chan = await conn.channel()
                dlx = await chan.declare_exchange(
                    f"{s.payehyar_rabbitmq_exchange}.dlx",
                    aio_pika.ExchangeType.TOPIC, durable=True)
                dlq = await chan.declare_queue(s.payehyar_rabbitmq_dlq, durable=True)
                await dlq.bind(dlx, routing_key="payehyar.masterdata.#")
                ex = await chan.declare_exchange(
                    s.payehyar_rabbitmq_exchange,
                    aio_pika.ExchangeType.TOPIC, durable=True)
                q = await chan.declare_queue(
                    s.payehyar_rabbitmq_queue, durable=True,
                    arguments={"x-dead-letter-exchange":
                               f"{s.payehyar_rabbitmq_exchange}.dlx"})
                await q.bind(ex, routing_key=s.payehyar_rabbitmq_routing_key)
                _STATE["connected"] = True
                log.info("مصرف‌کننده رویدادهای پایه‌یار۳۶۰ متصل شد (صف: %s)",
                         s.payehyar_rabbitmq_queue)
                async with q.iterator() as it:
                    async for msg in it:
                        async with msg.process(requeue=False):
                            await _process_message(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — اتصال مقاوم با تلاش مجدد
            _STATE["connected"] = False
            log.warning("RabbitMQ در دسترس نیست (%s) — تلاش مجدد پس از ۳۰ ثانیه", exc)
            await asyncio.sleep(30)


def events_status() -> dict:
    s = get_settings()
    return {"enabled": bool(s.payehyar_events_enabled),
            "configured": bool(s.payehyar_rabbitmq_user),
            "exchange": s.payehyar_rabbitmq_exchange,
            "queue": s.payehyar_rabbitmq_queue,
            "dlq": s.payehyar_rabbitmq_dlq,
            "routing_key": s.payehyar_rabbitmq_routing_key,
            "connected": _STATE.get("connected", False),
            "processed": _STATE["processed"], "duplicates": _STATE["duplicates"],
            "failed": _STATE["failed"], "last_event_at": _STATE["last_event_at"]}
