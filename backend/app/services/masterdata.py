"""صفحه‌های MDM پایه‌یار۳۶۰ (v3.5.0) — دروس یکتا، دروس تفکیکی، سرفصل دروس.

پایه‌یار۳۶۰ سامانهٔ MDM (مدیریت داده مرجع) است؛ این سرویس برای هر دامنهٔ مستند
(unique-courses / split-courses / course-syllabi) سه قابلیت می‌دهد:
1) همگام‌سازی تفکیکی از داخل اپ (دکمهٔ همگام‌سازی هر فرم) — رونوشت خام رکوردها
   در PayehyarRecord با content_hash و بدون تکرار.
2) لیست/جستجو/سلسله‌مراتب (درس یکتا → درس‌های تفکیکی → سرفصل‌ها) برای صفحه‌های
   مستقل ساید‌بار.
3) تولید محتوا برای هر «سرفصل درسی» با پایپ‌لاین استاندارد محتوا
   (سند ← طرح ← تولید ← QC) + خروجی PDF/PPTX/HTML/DOCX + امتیاز خودکار استاد.

سلسله‌مراتب مستند: هر درس یکتا می‌تواند چند درس تفکیکی داشته باشد (پیوند
unique_course_code) و هر سرفصل مصوب با تطبیق عنوان نرمال‌شده به درس یکتا
می‌چسبد (همان قاعدهٔ merge_syllabi در همگام‌سازی کاتالوگ).
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.errors import not_found, validation_error
from app.models.content import ContentDocument, ContentVersion
from app.models.courses import Course
from app.models.identity import User
from app.models.journey import PayehyarRecord
from app.models.points import ContributionPoint
from app.models.syllabus import SyllabusTopic, SyllabusVersion
from app.services import payehyar_connection
from app.services.payehyar_catalog import REFERENCE_SYSTEM, _norm_title
from app.services.payehyar_client import PayehyarError, _extract_items
from app.services.payehyar_records import record_key, upsert_domain_records

DOMAIN_LABELS = {
    "unique-courses": "دروس یکتا",
    "split-courses": "دروس تفکیکی",
    "course-syllabi": "سرفصل دروس",
}
POINTS = {"CONTENT_GENERATE": 25, "CONTENT_EXPORT": 5}
EXPORT_EXT = {"PDF": "pdf", "PPTX": "pptx", "HTML": "html", "DOCX": "docx"}


# ---------- کلید یکتای رکورد هر دامنه ----------

def domain_key(domain: str, item: dict) -> str | None:
    """شناسه یکتای رکورد برای UNIQUE(domain, external_id) — طبق مستند هر دامنه."""
    attrs = item.get("attrs") or {}
    if domain == "unique-courses":
        code = item.get("code")
        return str(code).strip()[:120] if code not in (None, "") else None
    if domain == "split-courses":
        uniq = item.get("unique_course_code") or item.get("parent_code")
        ext = attrs.get("external_id") or attrs.get("year_label") or item.get("title")
        if uniq in (None, "") and ext in (None, ""):
            return None
        return f"{uniq or '?'}|{ext}"[:120]
    if domain == "course-syllabi":
        key = item.get("source_set") and item.get("source_file")
        if key:
            return f"{item.get('source_set')}:{item.get('source_file')}"[:120]
        title = item.get("title_fa") or item.get("title")
        return str(title).strip()[:120] if title else None
    return None


def _view(rec: PayehyarRecord, topics: bool = False) -> dict:
    """نمای فارسی/صفحه‌ای رکورد — فیلدهای پرکاربرد از payload استخراج می‌شود."""
    p = rec.payload or {}
    a = p.get("attrs") or {}
    units = None
    if a.get("unit_theory") is not None or a.get("unit_practice") is not None:
        units = (a.get("unit_theory") or 0) + (a.get("unit_practice") or 0)
    out = {
        "id": str(rec.id), "domain": rec.domain,
        "external_id": rec.external_id, "code": rec.code, "title": rec.title,
        "units": units, "section": a.get("section"), "capacity": a.get("capacity"),
        "prerequisite": a.get("prerequisite"), "status": p.get("status"),
        "updated_at": str(p.get("updated_at") or "") or None,
        "last_synced_at": rec.last_synced_at.isoformat() if rec.last_synced_at else None,
        "unique_course_code": p.get("unique_course_code") or p.get("parent_code"),
        "year_label": a.get("year_label"),
        "topic_count": len(p.get("topics") or []),
        "source_set": p.get("source_set"), "source_file": p.get("source_file"),
    }
    if topics:
        out["topics"] = [
            {"seq": t.get("seq"), "title": t.get("title"), "hours": t.get("hours")}
            for t in (p.get("topics") or []) if isinstance(t, dict) and t.get("title")
        ]
    return out


# ---------- همگام‌سازی تفکیکی هر دامنه ----------

def sync_domain(db: Session, user: User, domain: str) -> dict:
    """واکشی یک دامنه از پایه‌یار۳۶۰ و upsert رکوردها — دکمهٔ همگام‌سازی هر فرم."""
    if domain not in DOMAIN_LABELS:
        raise validation_error(
            f"دامنهٔ پشتیبانی‌شده: {', '.join(DOMAIN_LABELS)}")
    client = payehyar_connection.client_for(db)
    body = client.fetch_domain(domain)
    if body.get("_not_modified"):
        return {"ok": True, "domain": domain, "label": DOMAIN_LABELS[domain],
                "not_modified": True, "message": "بدون تغییر از آخرین همگام‌سازی (کش ETag)"}
    items = _extract_items(body)
    # دامنه‌های split-courses/course-syllabi ممکن است کلید یکتای سطح بالا نداشته باشند؛
    # کلید محاسبه‌شدهٔ دامنه به‌عنوان external_id تزریق می‌شود تا رکورد skip نشود.
    for it in items:
        if isinstance(it, dict) and record_key(it) is None:
            ext = domain_key(domain, it)
            if ext:
                it["external_id"] = ext
    stats = upsert_domain_records(db, domain, items, source_route="services")
    db.commit()
    return {"ok": True, "domain": domain, "label": DOMAIN_LABELS[domain],
            "fetched": len(items), **stats,
            "message": (f"همگام‌سازی {DOMAIN_LABELS[domain]} انجام شد: "
                        f"{stats['created']} جدید، {stats['updated']} به‌روزرسانی، "
                        f"{stats['up_to_date']} بدون تغییر")}


# ---------- لیست / جستجو / نمای کلی ----------

def _domain_query(db: Session, domain: str):
    return (db.query(PayehyarRecord)
            .filter(PayehyarRecord.domain == domain,
                    PayehyarRecord.is_deleted == False)  # noqa: E712
            .order_by(PayehyarRecord.title.is_(None), PayehyarRecord.title))


def list_domain(db: Session, domain: str, q: str | None = None,
                parent_code: str | None = None,
                limit: int = 100, offset: int = 0) -> dict:
    """لیست رکوردهای یک دامنه برای صفحهٔ مستقل — با جستجو و فیلتر والد."""
    if domain not in DOMAIN_LABELS:
        raise validation_error("دامنهٔ نامعتبر")
    recs = _domain_query(db, domain).all()
    if q:
        qn = q.strip().lower()
        recs = [r for r in recs
                if qn in (r.title or "").lower() or qn in (r.code or "").lower()
                or qn in (r.external_id or "").lower()]
    if parent_code and domain == "split-courses":
        recs = [r for r in recs
                if (r.payload or {}).get("unique_course_code") == parent_code
                or (r.payload or {}).get("parent_code") == parent_code]
    total = len(recs)
    recs = recs[offset:offset + limit]
    return {"domain": domain, "label": DOMAIN_LABELS[domain], "total": total,
            "limit": limit, "offset": offset,
            "items": [_view(r, topics=(domain == "course-syllabi")) for r in recs]}


def overview(db: Session) -> dict:
    """آمار هر سه دامنه + جمع سرفصل‌ها — سربرگ صفحه‌های MDM."""
    out: dict = {"domains": {}, "topic_total": 0}
    for domain in DOMAIN_LABELS:
        rows = _domain_query(db, domain).all()
        last = max((r.last_synced_at for r in rows if r.last_synced_at), default=None)
        out["domains"][domain] = {"count": len(rows),
                                  "last_synced_at": last.isoformat() if last else None}
        if domain == "course-syllabi":
            out["topic_total"] = sum(len((r.payload or {}).get("topics") or [])
                                     for r in rows)
    return out


def hierarchy(db: Session, unique_code: str) -> dict:
    """درخت یک درس یکتا: درس‌های تفکیکی + سرفصل مصوب (تطبیق عنوان نرمال‌شده)."""
    rec = (_domain_query(db, "unique-courses")
           .filter(PayehyarRecord.external_id == unique_code).first())
    if rec is None:
        raise not_found("درس یکتای موردنظر در رونوشت محلی یافت نشد؛ "
                        "ابتدا دکمهٔ همگام‌سازی «دروس یکتا» را بزنید")
    splits = [r for r in _domain_query(db, "split-courses").all()
              if (r.payload or {}).get("unique_course_code") == unique_code
              or (r.payload or {}).get("parent_code") == unique_code]
    key = _norm_title(rec.title)
    syllabi = []
    if key:
        syllabi = [r for r in _domain_query(db, "course-syllabi").all()
                   if _norm_title((r.payload or {}).get("title_fa")) == key]
    return {"unique": _view(rec), "split_courses": [_view(r) for r in splits],
            "syllabi": [_view(r, topics=True) for r in syllabi]}


def record_detail(db: Session, record_id: str) -> dict:
    """جزئیات رکورد سرفصل + هر سرفصل درسی با نسخهٔ محتوای موجود و امتیاز."""
    rec = db.get(PayehyarRecord, record_id)
    if rec is None or rec.domain != "course-syllabi":
        raise not_found("رکورد سرفصل یافت نشد")
    course = _resolve_course(db, rec)
    topics = []
    for t in (rec.payload or {}).get("topics") or []:
        if not isinstance(t, dict) or not t.get("title"):
            continue
        doc = version_id = None
        points = 0
        if course is not None:
            doc = (db.query(ContentDocument)
                   .filter(ContentDocument.course_id == course.id,
                           ContentDocument.title == str(t["title"]).strip())
                   .order_by(ContentDocument.created_at.desc()).first())
            if doc is not None and doc.current_version_id:
                version_id = str(doc.current_version_id)
                points = (db.query(func.sum(ContributionPoint.points))
                          .filter(ContributionPoint.document_id == doc.id).scalar()) or 0
        topics.append({"seq": t.get("seq"), "title": str(t["title"]).strip(),
                       "hours": t.get("hours"), "document_id": str(doc.id) if doc else None,
                       "version_id": version_id, "points": points})
    return {"record": _view(rec, topics=False), "topics": topics,
            "course": {"id": str(course.id), "code": course.code,
                       "title": course.title} if course else None}


# ---------- تولید محتوا برای سرفصل درسی ----------

def _resolve_course(db: Session, rec: PayehyarRecord,
                    retried: bool = False) -> Course | None:
    """درس یکتای متناظر با رکورد سرفصل — با تطبیق عنوان نرمال‌شده."""
    title = (rec.payload or {}).get("title_fa") or rec.title
    key = _norm_title(title)
    if not key:
        return None
    course = (db.query(Course)
              .filter(func.lower(func.trim(Course.title)) == key.lower()).first())
    if course is not None:
        return course
    if not retried:
        # کاتالوگ هنوز همگام نشده — یک‌بار همگام‌سازی کامل و تلاش دوباره
        from app.services.payehyar_catalog import sync_catalog
        from app.models.identity import User as U

        sys_user = (db.query(U).filter(U.role == "TECH_ADMIN").first()
                    or db.query(U).filter(U.role == "EDUCATION_ADMIN").first())
        actor = sys_user or type("_SyncActor", (), {"id": rec.id})()
        try:
            sync_catalog(db, actor, "FULL")
        except Exception:  # noqa: BLE001 — همگام‌سازی خودکار بحرانی نیست
            db.rollback()
        return _resolve_course(db, rec, retried=True)
    return None


def _ensure_topic_version(db: Session, user: User, course: Course,
                          rec: PayehyarRecord, topic: dict) -> tuple[SyllabusVersion, SyllabusTopic]:
    """نسخهٔ سرفصل «مصوبِ» حامل این سرفصل درسی + ردیف SyllabusTopic.

    اولویت: نسخهٔ مصوب موجود درس → پیدا شدن موضوع با reference_id یا عنوان.
    در نبودِ آن، یک نسخهٔ موضوع‌محور REFERENCE_SYNC ساخته و با «اقدام استاد»
    (فشردن دکمهٔ تولید محتوا) مصوب تلقی می‌شود — بدون دست‌زدن به نسخه‌های
    محلی موجود (قاعدهٔ طلایی: بدون بازنویسی بی‌صدا)."""
    for sv in (db.query(SyllabusVersion)
               .filter(SyllabusVersion.course_id == course.id,
                       SyllabusVersion.status == "APPROVED")
               .order_by(SyllabusVersion.version_number.desc()).all()):
        payload = rec.payload or {}
        ref = (f"{payload.get('source_set')}:{payload.get('source_file')}:{topic.get('seq')}"
               if payload.get("source_file") else None)
        row = None
        if ref:
            row = (db.query(SyllabusTopic)
                   .filter(SyllabusTopic.syllabus_version_id == sv.id,
                           SyllabusTopic.reference_id == ref[:64]).first())
        if row is None:
            tkey = _norm_title(topic.get("title"))
            row = (db.query(SyllabusTopic)
                   .filter(SyllabusTopic.syllabus_version_id == sv.id,
                           func.lower(SyllabusTopic.title) == tkey.lower()
                           ).first()) if tkey else None
        if row is not None:
            return sv, row
    # نسخهٔ موضوع‌محور جدید — مصوبه با اقدام استاد ثبت می‌شود
    n = db.query(SyllabusVersion.course_id).filter(
        SyllabusVersion.course_id == course.id).count()
    digest = (rec.content_hash or str(rec.id))[:28]
    sv = SyllabusVersion(
        course_id=course.id, version_number=n + 1,
        title=f"سرفصل پایه‌یار۳۶۰ — {str(topic.get('title'))[:120]}",
        status="APPROVED", source_kind="REFERENCE_SYNC",
        reference_version=f"mdm:{digest}", approved_by=user.id,
        approved_at=utcnow(), approval_reference="پایه‌یار۳۶۰ (اقدام استاد)",
        created_by=user.id,
        notes=("نسخهٔ موضوع‌محور برای تولید محتوا از رکورد سرفصل پایه‌یار۳۶۰؛ "
               "مصوبه با فشردن دکمهٔ تولید محتوا توسط استاد ثبت شده است."),
    )
    db.add(sv)
    db.flush()
    ref = f"{(rec.payload or {}).get('source_set')}:{(rec.payload or {}).get('source_file')}:{topic.get('seq')}"
    row = SyllabusTopic(syllabus_version_id=sv.id, kind="TOPIC",
                        title=str(topic.get("title")).strip()[:300],
                        reference_id=ref[:64],
                        suggested_hours=topic.get("hours"), order_index=0)
    db.add(row)
    db.flush()
    return sv, row


def generate_for_record(db: Session, user: User, record_id: str,
                        topic_seq: int | None = None) -> dict:
    """تولید محتوای کامل برای یک «سرفصل درسی» رکورد سرفصل مصوب پایه‌یار۳۶۰.

    پایپ‌لاین استاندارد محتوا: سند ← طرح (AI) ← تأیید ← تولید (AI) ← QC.
    امتیاز استاد به‌صورت خودکار ثبت می‌شود (۲۵ امتیاز برای هر نسخهٔ جدید)."""
    from app.services import content_service

    rec = db.get(PayehyarRecord, record_id)
    if rec is None or rec.domain != "course-syllabi":
        raise not_found("رکورد سرفصل یافت نشد")
    topics = [t for t in (rec.payload or {}).get("topics") or []
              if isinstance(t, dict) and t.get("title")]
    if not topics:
        topics = [{"seq": 0, "title": rec.title or "سرفصل", "hours": None}]
    topic = topics[0] if topic_seq is None else next(
        (t for t in topics if t.get("seq") == topic_seq), None)
    if topic is None:
        raise validation_error(f"سرفصل درسی با شمارهٔ {topic_seq} در این رکورد نیست")
    course = _resolve_course(db, rec)
    if course is None:
        raise validation_error(
            "این سرفصل با هیچ درس یکتای همگام‌شده تطبیق نشد؛ ابتدا در صفحهٔ "
            "«دروس یکتا» همگام‌سازی کنید یا عنوان‌ها را در پایه‌یار هم‌سو نمایید")
    sv, topic_row = _ensure_topic_version(db, user, course, rec, topic)
    doc = (db.query(ContentDocument)
           .filter(ContentDocument.course_id == course.id,
                   ContentDocument.syllabus_version_id == sv.id,
                   ContentDocument.title == str(topic["title"]).strip())
           .first())
    if doc is None:
        doc = ContentDocument(
            course_id=course.id, syllabus_version_id=sv.id,
            title=str(topic["title"]).strip()[:300], goal="CONCEPT_TEACHING",
            scope={"topic_ids": [str(topic_row.id)]}, created_by=user.id,
        )
        db.add(doc)
        db.flush()
    plan = content_service.propose_plan(db, doc, user)
    plan = content_service.confirm_plan(db, plan, user)
    version = content_service.generate_content(db, doc, plan, user)
    award(db, user, "CONTENT_GENERATE", course_id=course.id, document_id=doc.id,
          version_id=version.id,
          note=f"تولید محتوا برای «{topic['title']}» — {course.title}")
    db.commit()
    qc = version.qc_report or {}
    return {"ok": True, "document_id": str(doc.id), "version_id": str(version.id),
            "version_number": version.version_number, "version_status": version.status,
            "course": {"id": str(course.id), "title": course.title},
            "topic": {"seq": topic.get("seq"), "title": topic["title"]},
            "points_awarded": POINTS["CONTENT_GENERATE"],
            "qc_blocks": len((version.structured_content or {}).get("blocks") or []),
            "qc_score": qc.get("score") if isinstance(qc, dict) else None,
            "message": (f"محتوای «{topic['title']}» تولید شد — نسخهٔ "
                        f"{version.version_number} با {POINTS['CONTENT_GENERATE']} امتیاز برای شما ثبت شد")}


# ---------- خروجی‌ها ----------

def export_content(db: Session, user: User, version_id: str, fmt: str) -> tuple[bytes, str, str]:
    """خروجی نسخهٔ محتوا در PDF/PPTX/HTML/DOCX — با امتیاز خودکار استاد."""
    from app.services.export_service import render_export

    import uuid as _uuid

    try:
        vid = _uuid.UUID(str(version_id))
    except (ValueError, AttributeError, TypeError):
        raise not_found("نسخهٔ محتوا یافت نشد")
    version = db.get(ContentVersion, vid)
    if version is None:
        raise not_found("نسخهٔ محتوا یافت نشد")
    doc = db.get(ContentDocument, version.document_id)
    if doc is None:
        raise not_found("سند محتوای این نسخه یافت نشد")
    fmt = (fmt or "").upper()
    if fmt not in EXPORT_EXT:
        raise validation_error("قالب خروجی باید یکی از PDF/PPTX/HTML/DOCX باشد")
    data, mime = render_export(db, version, fmt)
    award(db, user, "CONTENT_EXPORT", course_id=doc.course_id,
          document_id=version.document_id,
          version_id=version.id, fmt=fmt,
          note=f"خروجی {fmt} از نسخهٔ {version.version_number}")
    db.commit()
    base = (doc.title or "content").strip()[:60]
    safe = "".join(ch for ch in base if ch.isalnum() or ch in "-_ ").replace(" ", "-")
    filename = f"{safe or 'content'}-v{version.version_number}.{EXPORT_EXT[fmt]}"
    return data, mime, filename


# ---------- امتیاز اساتید ----------

def award(db: Session, user: User, action: str, *, course_id=None,
          document_id=None, version_id=None, fmt: str | None = None,
          note: str | None = None) -> tuple[ContributionPoint | None, int]:
    """ثبت امتیاز با قاعدهٔ ضدتکرار — None یعنی قبلاً ثبت شده (بدون امتیاز جدید)."""
    points = POINTS.get(action, 0)
    key = f"{user.id}:{action}:{version_id or '-'}:{fmt or '-'}"
    existing = db.query(ContributionPoint).filter(
        ContributionPoint.dedup_key == key).first()
    if existing is not None:
        return existing, 0
    row = ContributionPoint(user_id=user.id, action=action, points=points,
                            course_id=course_id, document_id=document_id,
                            version_id=version_id, fmt=fmt, note=note,
                            dedup_key=key)
    db.add(row)
    db.flush()
    return row, points


def points_me(db: Session, user: User, limit: int = 50) -> dict:
    """جمع امتیاز من + رکوردهای اخیر — صفحهٔ «امتیاز اساتید»."""
    total = (db.query(func.sum(ContributionPoint.points))
             .filter(ContributionPoint.user_id == user.id).scalar()) or 0
    rows = (db.query(ContributionPoint)
            .filter(ContributionPoint.user_id == user.id)
            .order_by(ContributionPoint.created_at.desc()).limit(limit).all())
    by_action: dict[str, int] = {}
    for r in rows:
        by_action[r.action] = by_action.get(r.action, 0) + r.points
    return {"total": int(total), "by_action": by_action,
            "rules": POINTS,
            "items": [{"id": str(r.id), "action": r.action, "points": r.points,
                       "fmt": r.fmt, "note": r.note,
                       "created_at": r.created_at.isoformat() if r.created_at else None}
                      for r in rows]}


def points_leaderboard(db: Session, limit: int = 10) -> dict:
    """جدول برترین مشارکت‌کنندگان محتوا — برای صفحهٔ امتیاز اساتید."""
    rows = (db.query(ContributionPoint.user_id,
                     func.sum(ContributionPoint.points).label("total"))
            .group_by(ContributionPoint.user_id)
            .order_by(func.sum(ContributionPoint.points).desc())
            .limit(limit).all())
    out = []
    for uid, total in rows:
        u = db.get(User, uid)
        out.append({"user_id": str(uid),
                    "name": (u.full_name if u else None) or "کاربر",
                    "total": int(total or 0)})
    return {"items": out}
