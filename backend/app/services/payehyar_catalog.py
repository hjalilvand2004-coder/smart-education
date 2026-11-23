"""همگام‌سازی کاتالوگ دروس و سرفصل‌ها از پایه‌یار۳۶۰ (استقرار واقعی اکوسیستم).

تفاوت با baseyar_service (همگام‌سازی تک‌درس):
- این ماژول «کل کاتالوگ» را واکشی و جدول دروس + نسخه سرفصل هر درس را upsert می‌کند.
- کلید یکتایی، شناسه مرجع (reference_id) در سرویس مرجع است؛ درس محلیِ هم‌کد نیز
  به مرجع پیوند داده می‌شود (بدون ساخت رکورد تکراری).
- قاعده طلایی حفظ می‌شود: تغییر نسخه سرفصل مرجع هرگز بی‌صدا اعمال نمی‌شود؛
  نسخه پیش‌نویس (REFERENCE_SYNC) + وضعیت REVIEW_REQUIRED + پرچم بررسی نگاشت
  مفهومی ساخته می‌شود و نسخه مصوب/محتوا/شواهد به نسخه خود وفادار می‌مانند.
- شکل دقیق پاسخ سرویس مرجع در دسترس نیست (endpoint با کلید باز می‌شود)؛ بنابراین
  نرمال‌سازی دفاعی چند شکل رایج را پوشش می‌دهد و رکوردهای نگاشت‌نشدنی به‌جای
  کرش، در warnings گزارش اجرا ثبت می‌شوند.
"""
import time

from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.errors import validation_error
from app.models.concepts import TopicConcept
from app.models.courses import Course
from app.models.journey import MasterdataSyncLog
from app.models.syllabus import SyllabusTopic, SyllabusVersion
from app.services.payehyar_client import PayehyarClient, PayehyarError

REFERENCE_SYSTEM = "baseyar360"
OWNER_SYSTEM = "پایه‌یار۳۶۰"

_COURSE_FIELDS = ("title", "credits", "term", "department", "degree_level",
                  "field_of_study", "description")


# ---------- نرمال‌سازی دفاعی پاسخ مرجع ----------

def _first(raw: dict, *keys, default=None):
    for k in keys:
        v = raw.get(k)
        if v not in (None, ""):
            return v
    return default


def _as_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def normalize_topic(raw) -> dict | None:
    if isinstance(raw, str):
        return {"reference_id": None, "title": raw.strip(), "suggested_hours": None}
    if not isinstance(raw, dict):
        return None
    title = _first(raw, "title", "name", "topic", "topic_title")
    if not title:
        return None
    return {
        "reference_id": _first(raw, "reference_id", "id", "uuid", "topic_id"),
        "title": str(title).strip(),
        "suggested_hours": _as_int(_first(raw, "suggested_hours", "hours", "duration")),
    }


def normalize_chapter(raw) -> dict | None:
    if isinstance(raw, str):
        return {"title": raw.strip(), "topics": []}
    if not isinstance(raw, dict):
        return None
    title = _first(raw, "title", "name", "chapter", "chapter_title")
    if not title:
        return None
    topics_raw = _first(raw, "topics", "items", "subjects", default=[]) or []
    topics = [t for t in (normalize_topic(t) for t in topics_raw) if t]
    return {"title": str(title).strip(), "topics": topics}


def normalize_course(raw) -> tuple[dict | None, str | None]:
    """نگاشت یک رکورد درس مرجع به شکل داخلی — None + هشدار اگر نگاشت‌نشدنی."""
    if not isinstance(raw, dict):
        return None, "رکورد غیرشیءای نادیده گرفته شد"
    reference_id = _first(raw, "reference_id", "id", "uuid", "course_id")
    code = _first(raw, "code", "course_code")
    title = _first(raw, "title", "name", "course_name")
    if not title:
        return None, f"رکورد بدون عنوان نادیده گرفته شد (id={reference_id or code or '?'})"
    chapters_raw = _first(raw, "chapters", "syllabus", "outline", default=[]) or []
    chapters = [c for c in (normalize_chapter(c) for c in chapters_raw) if c]
    return {
        "reference_id": str(reference_id) if reference_id else None,
        "code": (str(code).strip()[:32] if code else None),
        "title": str(title).strip()[:200],
        "credits": _as_int(_first(raw, "credits", "units")),
        "term": _first(raw, "term", "semester"),
        "department": _first(raw, "department", "faculty"),
        "degree_level": _first(raw, "degree_level", "grade"),
        "field_of_study": _first(raw, "field_of_study", "major"),
        "description": _first(raw, "description", "summary"),
        "reference_version": str(_first(raw, "reference_version", "version",
                                        "syllabus_version", default="v1")),
        "chapters": chapters,
    }, None


def normalize_catalog(raw) -> dict:
    """نرمال‌سازی پاسخ کاتالوگ — پوشش چند شکل رایج بدون فرض ساختار ثابت."""
    items: list = []
    raw_version = None
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        raw_version = raw.get("version") or raw.get("catalog_version")
        for key in ("courses", "items", "data", "records", "results"):
            if isinstance(raw.get(key), list):
                items = raw[key]
                break
        else:
            # شکل نگاشت کلید → فهرست (مثلاً {"CS101": {...}}) یا تک‌رکورد
            if all(isinstance(v, dict) for v in raw.values()) and raw:
                items = [{"code": k, **v} if "code" not in v else v
                         for k, v in raw.items()]
            elif raw:
                items = [raw]
    courses, warnings = [], []
    for r in items:
        c, warn = normalize_course(r)
        if c is None:
            if warn:
                warnings.append(warn)
        else:
            if c["reference_id"] is None and not c["code"]:
                warnings.append(f"درس «{c['title']}» بدون شناسه مرجع و بدون کد است؛ نادیده گرفته شد")
                continue
            if c["reference_id"] is None:
                c["reference_id"] = f"code:{c['code']}"
            courses.append(c)
    return {"courses": courses, "warnings": warnings, "raw_version": raw_version}


# ---------- همگام‌سازی ----------

def _stored_cursor(db: Session) -> str | None:
    last = (db.query(MasterdataSyncLog)
            .filter(MasterdataSyncLog.mode == "INCREMENTAL",
                    MasterdataSyncLog.status.in_(("OK", "PARTIAL")),
                    MasterdataSyncLog.cursor_after.isnot(None))
            .order_by(MasterdataSyncLog.created_at.desc()).first())
    return last.cursor_after if last else None


def _log_summary(log: MasterdataSyncLog, extra: dict | None = None) -> dict:
    data = {
        "log_id": str(log.id), "mode": log.mode, "status": log.status,
        "courses_created": log.courses_created, "courses_updated": log.courses_updated,
        "up_to_date": log.up_to_date, "syllabus_drafts_created": log.syllabus_drafts_created,
        "review_required": log.review_required, "warnings": log.warnings or [],
        "duration_ms": log.duration_ms, "remote_version": log.remote_version,
        "error_code": log.error_code, "error_message": log.error_message,
        "message": log.error_message or (
            f"همگام‌سازی {'کامل' if log.mode == 'FULL' else 'افزایشی'} انجام شد: "
            f"{log.courses_created} درس جدید، {log.courses_updated} به‌روزرسانی، "
            f"{log.up_to_date} بدون تغییر، {log.syllabus_drafts_created} نسخه پیش‌نویس سرفصل."
        ),
    }
    if extra:
        data.update(extra)
    return data


def _ensure_reference_syllabus(db: Session, user, course: Course, ref: dict,
                               stats: dict) -> None:
    """هم‌ترازسازی نسخه سرفصل با مرجع — با قاعده طلایی «بدون بازنویسی بی‌صدا»."""
    same = (db.query(SyllabusVersion)
            .filter(SyllabusVersion.course_id == course.id,
                    SyllabusVersion.reference_version == ref["reference_version"])
            .first())
    if same is not None:
        return  # این نسخه مرجع قبلاً همگام شده
    has_any_version = db.query(SyllabusVersion.course_id).filter(
        SyllabusVersion.course_id == course.id).count() > 0
    next_number = db.query(SyllabusVersion.course_id).filter(
        SyllabusVersion.course_id == course.id).count() + 1
    sv = SyllabusVersion(
        course_id=course.id, version_number=next_number,
        title=f"سرفصل مرجع پایه‌یار۳۶۰ ({ref['reference_version']})",
        status="DRAFT", source_kind="REFERENCE_SYNC",
        reference_version=ref["reference_version"], created_by=user.id,
        notes=("ساخته‌شده از همگام‌سازی کاتالوگ پایه‌یار۳۶۰؛ پیش از استفاده باید "
               "توسط استاد بررسی و تأیید شود."),
    )
    db.add(sv)
    db.flush()
    for idx, ch in enumerate(ref["chapters"]):
        db.add(SyllabusTopic(syllabus_version_id=sv.id, kind="CHAPTER",
                             title=ch["title"], order_index=idx))
        for t in ch["topics"]:
            db.add(SyllabusTopic(syllabus_version_id=sv.id, kind="TOPIC",
                                 title=t["title"], reference_id=t["reference_id"],
                                 suggested_hours=t["suggested_hours"]))
    db.flush()
    stats["syllabus_drafts_created"] += 1

    if has_any_version:
        # درس با سرفصل محلی موجود: تغییر مرجع نیازمند بررسی استاد است
        ref_ids = {t["reference_id"] for ch in ref["chapters"] for t in ch["topics"]
                   if t["reference_id"]}
        ref_titles = {t["reference_id"]: t["title"] for ch in ref["chapters"]
                      for t in ch["topics"] if t["reference_id"]}
        old_topics: dict[str, SyllabusTopic] = {}
        for t in db.query(SyllabusTopic).filter(
                SyllabusTopic.syllabus_version_id.in_(
                    [v.id for v in db.query(SyllabusVersion).filter(
                        SyllabusVersion.course_id == course.id).all()])).all():
            if t.reference_id and t.reference_id not in ref_ids:
                old_topics[t.reference_id] = t
        added = len(ref_ids - set(old_topics))
        removed_renamed = set(old_topics) - ref_ids
        review_count = added + len(removed_renamed)
        for rid in removed_renamed:
            for tc in db.query(TopicConcept).filter(
                    TopicConcept.topic_id == old_topics[rid].id).all():
                if not tc.needs_review:
                    tc.needs_review = True
                    tc.review_reason = ("موضوع مرجع حذف/تغییرنام شده است؛ نگاشت "
                                        "مفهومی نیازمند بررسی استاد است.")
                    review_count += 1
        stats["review_required"] += 1
        course.sync_state = "REVIEW_REQUIRED"


def _upsert_course(db: Session, user, ref: dict, stats: dict) -> None:
    course = None
    if ref["reference_id"]:
        course = (db.query(Course)
                  .filter(Course.reference_id == ref["reference_id"],
                          Course.reference_system == REFERENCE_SYSTEM).first())
    linked_existing = False
    if course is None and ref["code"]:
        course = db.query(Course).filter(Course.code == ref["code"]).first()
        linked_existing = course is not None
    if course is None:
        course = Course(
            code=ref["code"] or str(ref["reference_id"])[:32],
            title=ref["title"], credits=ref["credits"], term=ref["term"],
            department=ref["department"], degree_level=ref["degree_level"],
            field_of_study=ref["field_of_study"], description=ref["description"],
            created_by=user.id, reference_system=REFERENCE_SYSTEM,
            reference_id=ref["reference_id"], owner_system=OWNER_SYSTEM,
            reference_version=ref["reference_version"],
            last_synced_at=utcnow(), sync_state="VALID",
        )
        db.add(course)
        db.flush()
        stats["courses_created"] += 1
        _ensure_reference_syllabus(db, user, course, ref, stats)
        return

    changed = False
    for f in _COURSE_FIELDS:
        new = ref[f] if ref[f] not in ("", None) else None
        if new is not None and getattr(course, f) != new:
            setattr(course, f, new)
            changed = True
    if linked_existing or course.reference_id != ref["reference_id"]:
        course.reference_system = REFERENCE_SYSTEM
        course.reference_id = ref["reference_id"]
        course.owner_system = OWNER_SYSTEM
        changed = True
    course.last_synced_at = utcnow()
    if course.sync_state in (None, "STALE", "UNLINKED"):
        course.sync_state = "VALID"
    if changed:
        stats["courses_updated"] += 1
    else:
        stats["up_to_date"] += 1
    _ensure_reference_syllabus(db, user, course, ref, stats)


def sync_catalog(db: Session, user, mode: str = "FULL") -> dict:
    """اجرای همگام‌سازی کاتالوگ — FULL (کاتالوگ کامل) یا INCREMENTAL (فید تغییرات)."""
    if mode not in ("FULL", "INCREMENTAL"):
        raise validation_error("حالت همگام‌سازی باید FULL یا INCREMENTAL باشد")
    started = time.monotonic()
    log = MasterdataSyncLog(mode=mode, status="OK", triggered_by=user.id,
                            cursor_before=_stored_cursor(db) if mode == "INCREMENTAL" else None)
    db.add(log)
    db.flush()
    stats: dict = {"courses_created": 0, "courses_updated": 0, "up_to_date": 0,
                   "syllabus_drafts_created": 0, "review_required": 0}
    client = PayehyarClient()
    probe: dict = {}
    try:
        probe = client.probe()
        log.remote_version = probe.get("service_version")
        if probe["status"] != "OK":
            log.status = "FAILED"
            log.error_code = probe["status"]
            log.error_message = probe.get("detail") or probe.get("hint") or \
                "اتصال به سرویس مرجع احراز هویت نشد."
            audit(db, user.id, "PAYEHYAR_CATALOG_SYNC", "system", None,
                  after={"mode": mode, "status": "FAILED", "probe": probe["status"]})
            db.commit()
            return _log_summary(log, {"probe": probe, "probe_status": probe["status"]})

        if mode == "INCREMENTAL":
            raw = client.fetch_changes(cursor=log.cursor_before, limit=200)
            # فید تغییرات ممکن است payload کامل درس‌ها را بدهد؛ در غیر این صورت
            # به کاتالوگ کامل برمی‌گردیم (همیشه درست‌تر از اعمال جزئی ناقص).
            norm = normalize_catalog(raw if isinstance(raw, (list, dict)) else {})
            if not norm["courses"]:
                raw = client.fetch_catalog()
                norm = normalize_catalog(raw)
        else:
            raw = client.fetch_catalog()
            norm = normalize_catalog(raw)

        log.warnings = {"items": norm["warnings"][:20]} if norm["warnings"] else None
        if norm.get("raw_version"):
            log.remote_version = str(norm["raw_version"])[:32]
        for ref in norm["courses"]:
            _upsert_course(db, user, ref, stats)
        for k, v in stats.items():
            setattr(log, k, v)
        if stats["review_required"]:
            log.status = "PARTIAL"  # داده واکشی شد اما نیازمند بررسی استاد است
        log.duration_ms = int((time.monotonic() - started) * 1000)
        audit(db, user.id, "PAYEHYAR_CATALOG_SYNC", "system", None,
              after={"mode": mode, "status": log.status, **stats,
                     "remote_version": log.remote_version})
        db.commit()
        return _log_summary(log, {"probe_status": probe["status"]})
    except PayehyarError as exc:
        db.rollback()
        log.status = "FAILED"
        log.error_code = exc.code
        log.error_message = exc.hint or exc.message
        log.duration_ms = int((time.monotonic() - started) * 1000)
        db.add(log)
        db.commit()
        return _log_summary(log)


def catalog_status(db: Session) -> dict:
    """وضعیت اتصال + آمار رونوشت مرجع + آخرین اجرا — برای صفحه همگام‌سازی."""
    s = get_settings()
    client = PayehyarClient()
    probe = client.probe()
    ref_courses = db.query(Course).filter(Course.reference_system == REFERENCE_SYSTEM).count()
    linked = db.query(Course).filter(Course.reference_id.isnot(None)).count()
    drafts = db.query(SyllabusVersion).filter(
        SyllabusVersion.source_kind == "REFERENCE_SYNC",
        SyllabusVersion.status == "DRAFT").count()
    review = db.query(Course).filter(Course.sync_state == "REVIEW_REQUIRED").count()
    last = (db.query(MasterdataSyncLog)
            .order_by(MasterdataSyncLog.created_at.desc()).first())
    return {
        "probe": probe,
        "config": {
            "base_url": client.base_url,
            "api_key_set": bool(s.payehyar_api_key),
            "dev_user_set": bool(s.payehyar_dev_user),
            "timeout_seconds": s.payehyar_timeout_seconds,
        },
        "counts": {
            "reference_courses": ref_courses,
            "linked_courses": linked,
            "pending_drafts": drafts,
            "review_required_courses": review,
        },
        "last_log": _log_summary(last) if last else None,
        "note": ("منبع حقیقت دروس و سرفصل‌ها پایه‌یار۳۶۰ است؛ این سامانه فقط "
                 "رونوشت همگام‌شده نگه می‌دارد و تغییر مرجع نیازمند بررسی استاد است."),
    }


def recent_logs(db: Session, limit: int = 20) -> list[dict]:
    rows = (db.query(MasterdataSyncLog)
            .order_by(MasterdataSyncLog.created_at.desc()).limit(min(limit, 100)).all())
    return [_log_summary(r) for r in rows]
