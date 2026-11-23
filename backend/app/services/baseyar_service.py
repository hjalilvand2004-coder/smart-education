"""یکپارچگی با پایه‌یار۳۶۰ — مرجع حقیقت درس/سرفصل (بازخورد ۳.۱).

اصول:
- درس یکتا، کد درس و سرفصل مصوب «مالکیت» پایه‌یار۳۶۰ است؛ این سامانه فقط
  «رونوشت همگام‌شده» نگه می‌دارد (شناسه مرجع، نسخه، مالک، زمان همگام‌سازی،
  وضعیت اعتبار) و هرگز منبع حقیقت مستقل نمی‌شود.
- سه مسیر همگام‌سازی: واکشی اولیه، دریافت تغییرات (رویداد/API نسخه‌دار)،
  تطبیق دوره‌ای برای کشف تغییرات ازدست‌رفته.
- تغییر نسخه سرفصل هرگز بی‌صدا گراف مفاهیم/محتوا/شواهد را بازنویسی نمی‌کند:
  گزارش تغییر + نسخه پیش‌نویس + نگاشت‌های نیازمند بررسی استاد ساخته می‌شود و
  آزمون‌ها/محتوا/شواهد به نسخه زمان اجرای خود وفادار می‌مانند.
- انتقال: اگر S360_BASEYAR_BASE_URL تنظیم شده باشد از API واقعی خوانده می‌شود؛
  وگرنه داده نمونه قطعی (دو نسخه) برای توسعه و آزمون ارائه می‌شود.
"""
import hashlib
import json
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.errors import not_found, validation_error
from app.core.audit import audit
from app.models.courses import Course
from app.models.concepts import TopicConcept
from app.models.journey import ReferenceSyncLog
from app.models.syllabus import SyllabusTopic, SyllabusVersion

REFERENCE_SYSTEM = "baseyar360"
OWNER_SYSTEM = "پایه‌یار۳۶۰"

# داده نمونه توسعه/آزمون: {reference_id: {version: payload}} — رویداد نسخه‌دار را شبیه‌سازی می‌کند
SAMPLE_REFERENCES: dict[str, dict[str, dict]] = {}


def _sample_payload(reference_id: str) -> dict:
    ref = SAMPLE_REFERENCES.get(reference_id) or {}
    if not ref:  # نمونه عمومی قطعی
        ref = {"v1": {
            "reference_id": reference_id, "reference_version": "v1",
            "title": "درس مرجع نمونه",
            "chapters": [
                {"reference_id": f"{reference_id}:ch1", "title": "فصل اول",
                 "topics": [{"reference_id": f"{reference_id}:t1", "title": "موضوع اول",
                             "suggested_hours": 4},
                            {"reference_id": f"{reference_id}:t2", "title": "موضوع دوم",
                             "suggested_hours": 6}]},
            ],
        }}
    # آخرین نسخه (رویداد نسخه‌دار: کلیدهای v*)
    versions = sorted(ref.keys())
    return ref[versions[-1]]


def fetch_reference(course: Course) -> dict:
    """واکشی داده مرجع از پایه‌یار۳۶۰ (API واقعی یا نمونه توسعه)."""
    s = get_settings()
    ref_id = course.reference_id or course.code
    if not s.baseyar_base_url:
        return _sample_payload(ref_id)
    try:
        with httpx.Client(base_url=s.baseyar_base_url,
                          timeout=s.baseyar_timeout_seconds,
                          headers={"Authorization": f"Bearer {s.baseyar_api_key}"} if s.baseyar_api_key else {}) as client:
            resp = client.get(f"/api/v1/courses/{ref_id}/syllabus")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:  # همگام‌سازی تاب‌آور است؛ خطا منجر به sync_state نشکسته
        raise validation_error(f"واکشی از پایه‌یار۳۶۰ ناموفق بود: {exc}")


def _topics_hash(payload: dict) -> str:
    canon = json.dumps(
        [[c["reference_id"], t["reference_id"], t["title"]]
         for c in payload.get("chapters", []) for t in c.get("topics", [])],
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def _iter_ref_topics(payload: dict):
    for ch in payload.get("chapters", []):
        for t in ch.get("topics", []):
            yield t


def _log(db: Session, course: Course, direction, status, user, reference_version,
         report=None, message=None, new_sv_id=None, commit=True) -> ReferenceSyncLog:
    row = ReferenceSyncLog(
        course_id=course.id, direction=direction, status=status,
        reference_system=REFERENCE_SYSTEM, reference_version=reference_version,
        report=report, message=message, new_syllabus_version_id=new_sv_id,
        synced_by=user.id, applied_at=utcnow() if status == "SYNCED" else None,
    )
    db.add(row)
    db.flush()
    audit(db, user.id, "BASEYAR_SYNC", "course", course.id,
          after={"direction": direction, "status": status,
                 "reference_version": reference_version, "report": report or {}})
    if commit:
        db.commit()
    return row


def sync_course(db: Session, user, course_id, mode: str) -> dict:
    """همگام‌سازی در سه مسیر: INITIAL_PULL / CHANGE_EVENT / RECONCILE."""
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    if mode not in ("INITIAL_PULL", "CHANGE_EVENT", "RECONCILE"):
        raise validation_error("حالت همگام‌سازی نامعتبر است")

    payload = fetch_reference(course)
    topics_new = {t["reference_id"]: t for t in _iter_ref_topics(payload)}

    if mode == "INITIAL_PULL" or course.reference_id is None:
        course.reference_system = REFERENCE_SYSTEM
        course.reference_id = payload.get("reference_id") or course.code
        course.owner_system = OWNER_SYSTEM
        course.reference_version = payload["reference_version"]
        course.last_synced_at = utcnow()
        course.sync_state = "VALID"
        # نگاشت شناسه مرجع به موضوع‌های نسخه مصوب فعلی (تطابق عنوان)
        approved = db.query(SyllabusVersion).filter(
            SyllabusVersion.course_id == course.id, SyllabusVersion.status == "APPROVED").all()
        mapped = 0
        titles = {t["title"].strip(): t["reference_id"] for t in topics_new.values()}
        for sv in approved:
            for t in db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == sv.id).all():
                ref = titles.get((t.title or "").strip())
                if ref:
                    t.reference_id = ref
                    mapped += 1
        row = _log(db, course, "INITIAL_PULL", "SYNCED", user, payload["reference_version"],
                   report={"mapped_topics": mapped, "reference_topics": len(topics_new)},
                   message=(f"واکشی اولیه انجام شد؛ نسخه مرجع {payload['reference_version']} با "
                            f"{len(topics_new)} موضوع ثبت و {mapped} موضوع موجود نگاشت شد."))
        return _payload(row, course)

    if mode in ("CHANGE_EVENT", "RECONCILE"):
        if payload["reference_version"] == course.reference_version and \
                not (mode == "RECONCILE" and _drift(db, course, topics_new)):
            row = _log(db, course, mode, "UP_TO_DATE", user, payload["reference_version"],
                       message="نسخه مرجع تغییری نکرده است.")
            return _payload(row, course)
        return _apply_change(db, user, course, mode, payload, topics_new)
    raise validation_error("حالت همگام‌سازی پشتیبانی نمی‌شود")


def _drift(db: Session, course: Course, topics_new: dict) -> bool:
    """تطبیق دوره‌ای: کشف تغییر ازدست‌رفته (نسخه یکسان اما محتوا متفاوت)."""
    ref_titles = {t["reference_id"]: t["title"].strip() for t in topics_new.values()}
    approved = db.query(SyllabusVersion).filter(
        SyllabusVersion.course_id == course.id, SyllabusVersion.status == "APPROVED").all()
    for sv in approved:
        for t in db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == sv.id).all():
            # مبنا مقایسه «موضوع»هاست؛ فصل‌ها ساختار محلی‌اند و مقایسه نمی‌شوند
            if t.kind == "CHAPTER" or not t.reference_id:
                continue
            if ref_titles.get(t.reference_id) != (t.title or "").strip():
                return True
    return False


def _apply_change(db: Session, user, course: Course, mode: str, payload: dict,
                  topics_new: dict) -> dict:
    """تغییر نسخه مرجع → گزارش + نسخه پیش‌نویس + نگاشت‌های نیازمند بررسی.
    گراف مفاهیم، محتوای منتشرشده و شواهد یادگیری دست‌نخورده می‌مانند."""
    # اگر برای همین نسخه جدید یک بررسی باز داریم، همان را برمی‌گردانیم (idempotent)
    open_log = (
        db.query(ReferenceSyncLog)
        .filter(ReferenceSyncLog.course_id == course.id,
                ReferenceSyncLog.status == "REVIEW_REQUIRED",
                ReferenceSyncLog.reference_version == payload["reference_version"])
        .order_by(ReferenceSyncLog.created_at.desc()).first()
    )
    if open_log is not None:
        return _payload(open_log, course)

    ref_titles = {rid: t["title"].strip() for rid, t in topics_new.items()}
    approved = db.query(SyllabusVersion).filter(
        SyllabusVersion.course_id == course.id, SyllabusVersion.status == "APPROVED").all()
    old_topics: dict[str, SyllabusTopic] = {}
    for sv in approved:
        for t in db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == sv.id).all():
            if t.reference_id:
                old_topics[t.reference_id] = t

    added = [rid for rid in topics_new if rid not in old_topics]
    removed = [rid for rid in old_topics if rid not in topics_new]
    renamed = [rid for rid in topics_new if rid in old_topics and
               old_topics[rid].title.strip() != ref_titles[rid]]

    # نسخه پیش‌نویس جدید — نسخه مصوب فعلی و شواهد/محتوا به نسخه خود وفادار می‌مانند
    next_number = (db.query(SyllabusVersion.course_id)
                   .filter(SyllabusVersion.course_id == course.id).count()) + 1
    sv = SyllabusVersion(
        course_id=course.id, version_number=next_number,
        title=f"سرفصل همگام‌شده از پایه‌یار۳۶۰ ({payload['reference_version']})",
        status="DRAFT", source_kind="REFERENCE_SYNC",
        reference_version=payload["reference_version"], created_by=user.id,
        notes="ایجادشده از همگام‌سازی مرجع؛ نیازمند بررسی و تأیید استاد پیش از استفاده.",
    )
    db.add(sv)
    db.flush()
    for ch in payload.get("chapters", []):
        # فصل‌ها ساختار محلی‌اند؛ شناسه مرجع فقط روی موضوع‌ها نگهداری می‌شود
        db.add(SyllabusTopic(syllabus_version_id=sv.id, kind="CHAPTER",
                             title=ch["title"]))
        for t in ch.get("topics", []):
            db.add(SyllabusTopic(syllabus_version_id=sv.id, kind="TOPIC",
                                 title=t["title"], reference_id=t["reference_id"],
                                 suggested_hours=t.get("suggested_hours")))
    db.flush()

    # نگاشت‌های نیازمند بررسی استاد: موضوعِ دارای نگاشت که حذف/تغییرنام شده یا
    # موضوع جدیدی که هنوز به هیچ مفهومی نگاشت نشده است
    review_count = 0
    for rid in set(removed) | set(renamed):
        t = old_topics.get(rid)
        if t is None:
            continue
        for tc in db.query(TopicConcept).filter(TopicConcept.topic_id == t.id).all():
            if not tc.needs_review:
                tc.needs_review = True
                tc.review_reason = ("موضوع مرجع حذف/تغییرنام شده است؛ نگاشت مفهومی "
                                    "نیازمند بررسی استاد است.")
                review_count += 1
    for rid in added:
        review_count += 1  # موضوع جدید بدون نگاشت مفهومی

    report = {
        "reference_version_old": course.reference_version,
        "reference_version_new": payload["reference_version"],
        "topics_added": len(added),
        "topics_removed": len(removed),
        "topics_renamed": len(renamed),
        "mappings_needing_review": review_count,
        "added_titles": [ref_titles[r] for r in added][:10],
        "removed_titles": [old_topics[r].title for r in removed if r in old_topics][:10],
    }
    course.sync_state = "REVIEW_REQUIRED"
    course.last_synced_at = utcnow()
    message = (f"نسخه جدید سرفصل دریافت شد؛ {len(added) + len(removed) + len(renamed)} موضوع تغییر کرده و "
               f"{review_count} نگاشت مفهومی نیازمند بررسی استاد است.")
    row = _log(db, course, mode, "REVIEW_REQUIRED", user, payload["reference_version"],
               report=report, message=message, new_sv_id=sv.id)
    return _payload(row, course)


def apply_review(db: Session, user, log_id: str) -> dict:
    """پس از بررسی استاد (تأیید/اصلاح نگاشت‌ها)، رونوشت با نسخه جدید هم‌تراز می‌شود."""
    log = db.get(ReferenceSyncLog, log_id)
    if log is None:
        raise not_found("گزارش همگام‌سازی یافت نشد")
    if log.status != "REVIEW_REQUIRED":
        raise validation_error("این گزارش در وضعیت بررسی نیست")
    course = db.get(Course, log.course_id)
    course.reference_version = log.reference_version
    course.sync_state = "VALID"
    course.last_synced_at = utcnow()
    # پاک‌سازی پرچم‌های بررسی نگاشت‌های این درس (مفهوم‌ها بر پایه نسخه جدید تأیید شدند)
    topics = db.query(SyllabusTopic).filter(
        SyllabusTopic.syllabus_version_id.in_(
            [sv.id for sv in db.query(SyllabusVersion).filter(SyllabusVersion.course_id == course.id).all()]
        )).all()
    tmap = {t.id for t in topics}
    cleared = 0
    for tc in db.query(TopicConcept).filter(TopicConcept.topic_id.in_(tmap or [None])).all():
        if tc.needs_review:
            tc.needs_review = False
            tc.review_reason = None
            cleared += 1
    log.status = "SYNCED"
    log.applied_at = utcnow()
    audit(db, user.id, "BASEYAR_REVIEW_APPLIED", "course", course.id,
          after={"log_id": str(log.id), "cleared_mappings": cleared})
    db.commit()
    return {"status": "SYNCED", "cleared_mappings": cleared,
            "new_syllabus_version_id": str(log.new_syllabus_version_id) if log.new_syllabus_version_id else None,
            "message": "رونوشت محلی با نسخه مرجع هم‌تراز شد؛ نسخه پیش‌نویس سرفصل در انتظار تأیید شماست."}


def _payload(log: ReferenceSyncLog, course: Course) -> dict:
    return {
        "log_id": str(log.id), "status": log.status, "direction": log.direction,
        "course_id": str(course.id), "sync_state": course.sync_state,
        "reference_version": log.reference_version,
        "reference_version_applied": course.reference_version,
        "message": log.message,
        "report": log.report,
        "new_syllabus_version_id": str(log.new_syllabus_version_id) if log.new_syllabus_version_id else None,
    }


def status_for(db: Session, course_id: str) -> dict:
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("درس یافت نشد")
    last = (
        db.query(ReferenceSyncLog)
        .filter(ReferenceSyncLog.course_id == course.id)
        .order_by(ReferenceSyncLog.created_at.desc()).first()
    )
    open_reviews = db.query(ReferenceSyncLog).filter(
        ReferenceSyncLog.course_id == course.id,
        ReferenceSyncLog.status == "REVIEW_REQUIRED").count()
    return {
        "course_id": str(course.id),
        "reference_system": course.reference_system,
        "owner_system": course.owner_system or (OWNER_SYSTEM if course.reference_id else None),
        "reference_id": course.reference_id,
        "reference_version": course.reference_version,
        "last_synced_at": course.last_synced_at.isoformat() if course.last_synced_at else None,
        "sync_state": course.sync_state or ("UNLINKED" if not course.reference_id else "STALE"),
        "open_reviews": open_reviews,
        "last_log": _payload(last, course) if last else None,
        "note": "منبع حقیقت درس/سرفصل پایه‌یار۳۶۰ است؛ این نسخه فقط رونوشت همگام‌شده است.",
    }
