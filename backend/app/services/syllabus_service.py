"""سرویس سرفصل مصوب: ورود، استخراج AI، تأیید انسانی، نسخه‌بندی و تفاوت‌ها (بخش ۳.۱).

نکته حاکمیتی: AI فقط ساختار را «پیشنهاد» می‌کند؛ اعتبار رسمی فقط با تأیید
نقش مجاز ایجاد می‌شود (AC-02).
"""
import re

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway
from app.ai.schemas import SyllabusStructureOut
from app.core.audit import audit
from app.core.database import utcnow
from app.core.errors import validation_error
from app.models.courses import Course
from app.models.syllabus import LearningObjective, SyllabusTopic, SyllabusVersion


def create_version(
    db: Session,
    course: Course,
    creator_id,
    title: str = "سرفصل درس",
    source_kind: str = "MANUAL",
    approval_reference: str | None = None,
    prerequisites_note: str | None = None,
    assessment_policy: str | None = None,
    notes: str | None = None,
) -> SyllabusVersion:
    last = (
        db.query(SyllabusVersion)
        .filter(SyllabusVersion.course_id == course.id)
        .order_by(SyllabusVersion.version_number.desc())
        .first()
    )
    version = SyllabusVersion(
        course_id=course.id,
        version_number=(last.version_number + 1) if last else 1,
        title=title,
        status="DRAFT",
        source_kind=source_kind,
        approval_reference=approval_reference,
        prerequisites_note=prerequisites_note,
        assessment_policy=assessment_policy,
        notes=notes,
        created_by=creator_id,
    )
    db.add(version)
    db.flush()
    return version


def add_topic(db: Session, version_id, kind: str, title: str, order_index: int = 0,
              parent_id=None, suggested_hours: float | None = None,
              description: str | None = None, needs_review: bool = False) -> SyllabusTopic:
    topic = SyllabusTopic(
        syllabus_version_id=version_id,
        parent_id=parent_id,
        kind=kind,
        title=title,
        order_index=order_index,
        suggested_hours=suggested_hours,
        description=description,
        needs_review=needs_review,
    )
    db.add(topic)
    db.flush()
    return topic


def add_objective(db: Session, version_id, code: str, statement: str,
                  topic_id=None, bloom_level: str | None = None) -> LearningObjective:
    obj = LearningObjective(
        syllabus_version_id=version_id,
        topic_id=topic_id,
        code=code,
        statement=statement,
        bloom_level=bloom_level,
    )
    db.add(obj)
    db.flush()
    return obj


def import_from_source(
    db: Session,
    course: Course,
    creator_id,
    text: str,
    source_kind: str = "TEXT",
    file_name: str | None = None,
    file_path: str | None = None,
) -> SyllabusVersion:
    """ورود سرفصل: استخراج اولیه ساختار با AI (یا هیوریستیک) + علامت‌گذاری بخش‌های مبهم."""
    structure: SyllabusStructureOut
    try:
        gateway = AIGateway(db)
        structure = gateway.run(
            "syllabus_extraction",
            {"course_title": course.title, "text": text[:12000]},
            schema=SyllabusStructureOut,
            created_by=creator_id,
        )
    except Exception:  # noqa: BLE001 — حالت جایگزین: استخراج هیوریستیک محلی
        from app.ai.mock_content import mock_syllabus_extraction

        structure = SyllabusStructureOut(**mock_syllabus_extraction({"text": text}))

    version = create_version(
        db, course, creator_id,
        title=course.title + " — سرفصل",
        source_kind=source_kind,
        notes="ساختار استخراج‌شده؛ پیش از استفاده در تولید محتوا باید تأیید شود.",
    )
    if file_path:
        version.official_file_path = file_path
        version.official_file_name = file_name
    if structure.ambiguous:
        version.ambiguous_notes = "؛ ".join(structure.ambiguous[:8])

    for ci, ch in enumerate(structure.chapters):
        chapter = add_topic(db, version.id, "CHAPTER", ch.title, order_index=ci,
                            suggested_hours=ch.hours)
        for ti, topic_title in enumerate(ch.topics):
            add_topic(db, version.id, "TOPIC", topic_title, order_index=ti,
                      parent_id=chapter.id, needs_review=len(topic_title) < 5)
    for oi, stmt in enumerate(structure.objectives):
        add_objective(db, version.id, f"LO{oi + 1}", stmt)

    return version


def approve_version(db: Session, version: SyllabusVersion, approver, notes: str | None = None) -> SyllabusVersion:
    """تأیید انسانی ساختار — تنها مسیر ایجاد اعتبار رسمی."""
    if version.status == "APPROVED":
        raise validation_error("این نسخه قبلاً تأیید شده است؛ برای تغییر، نسخه جدید بسازید.")
    topics = db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == version.id).count()
    if topics == 0:
        raise validation_error("سرفصل بدون فصل/موضوع قابل تأیید نیست")
    # نسخه مصوب قبلی منسوخ می‌شود ولی محتواهای متصل به آن دست‌نخورده می‌مانند (AC-06)
    db.query(SyllabusVersion).filter(
        SyllabusVersion.course_id == version.course_id,
        SyllabusVersion.status == "APPROVED",
        SyllabusVersion.id != version.id,
    ).update({"status": "SUPERSEDED"}, synchronize_session=False)
    version.status = "APPROVED"
    version.approved_by = approver.id
    version.approved_at = utcnow()
    if notes:
        version.notes = notes
    audit(db, approver.id, "SYLLABUS_APPROVE", "syllabus_version", version.id,
          after={"version_number": version.version_number})
    db.flush()
    return version


def _norm_title(t: str) -> str:
    return re.sub(r"[\s\u200c]+", " ", t).strip()


def diff_versions(db: Session, v1: SyllabusVersion, v2: SyllabusVersion) -> dict:
    """تفاوت دو نسخه — قرارداد: تغییرهای «v1 نسبت به v2» (مبنا: v2 قدیمی).
    مبنای گزارش اثر تغییر سرفصل (AC-06)."""
    t1 = {t.id: t for t in db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == v1.id)}
    t2 = {t.id: t for t in db.query(SyllabusTopic).filter(SyllabusTopic.syllabus_version_id == v2.id)}
    titles1 = {_norm_title(t.title) for t in t1.values()}
    titles2 = {_norm_title(t.title) for t in t2.values()}
    added = sorted(titles1 - titles2)
    removed = sorted(titles2 - titles1)
    o1 = {o.code: o.statement for o in
          db.query(LearningObjective).filter(LearningObjective.syllabus_version_id == v1.id)}
    o2 = {o.code: o.statement for o in
          db.query(LearningObjective).filter(LearningObjective.syllabus_version_id == v2.id)}
    changed_objectives = [
        {"code": k, "before": o2[k], "after": o1[k]}
        for k in sorted(set(o1) & set(o2)) if o1[k] != o2.get(k)
    ]
    return {
        "from_version": v2.version_number,
        "to_version": v1.version_number,
        "added_topics": added,
        "removed_topics": removed,
        "changed_objectives": changed_objectives,
        "added_objectives": [o1[k] for k in sorted(set(o1) - set(o2))],
        "removed_objectives": [o2[k] for k in sorted(set(o2) - set(o1))],
    }
