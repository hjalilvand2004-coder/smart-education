"""رجیستری Handlerهای پس‌زمینه (بخش ۱۳) — تولید محتوا، سؤال، خروجی و ورود سرفصل.

خط تولید محتوا: بازیابی سرفصل/منابع → تولید ساختار → اعتبارسنجی Schema →
کنترل کیفیت → ذخیره پیش‌نویس → اعلان (outbox).
خط تولید خروجی: نسخه ثابت محتوا → انتخاب قالب → تبدیل بلوک‌ها → Render →
کنترل فایل → ذخیره Artifact → لینک دریافت.
Worker تولید فایل از Worker AI تفکیک می‌شود (در استقرار Celery با صف مجزا).
"""
from app.core.jobs import add_step, set_progress
from app.core.storage import LocalStorage


def get_handler(kind: str):
    handlers = {
        "syllabus_import": handle_syllabus_import,
        "content_plan": handle_content_plan,
        "content_generation": handle_content_generation,
        "content_full": handle_content_full,
        "content_block_regeneration": handle_block_regeneration,
        "question_generation": handle_question_generation,
        "export": handle_export,
    }
    return handlers.get(kind)


def handle_syllabus_import(db, job):
    from app.models.courses import Course
    from app.models.ops import OutboxEvent
    from app.services.syllabus_service import import_from_source

    payload = job.payload or {}
    set_progress(db, job, 10)
    add_step(db, job, "بازیابی درس و متن منبع")
    course = db.get(Course, payload["course_id"])
    version = import_from_source(
        db, course, job.created_by,
        text=payload.get("text", ""),
        source_kind=payload.get("source_kind", "TEXT"),
        file_name=payload.get("file_name"),
        file_path=payload.get("file_path"),
    )
    set_progress(db, job, 80)
    add_step(db, job, "استخراج ساختار و ثبت نسخه پیش‌نویس")
    db.add(OutboxEvent(event_type="syllabus.imported", payload={
        "syllabus_version_id": str(version.id), "course_id": str(course.id),
        "status": version.status,
    }))
    db.flush()
    set_progress(db, job, 100)
    job.result = {"syllabus_version_id": str(version.id),
                  "status": version.status,
                  "message": "ساختار استخراج‌شده پیش از اعتبار رسمی باید تأیید شود (AC-02)"}


def handle_content_plan(db, job):
    from app.models.content import ContentDocument
    from app.models.identity import User
    from app.services.content_service import propose_plan

    payload = job.payload or {}
    set_progress(db, job, 20)
    doc = db.get(ContentDocument, payload["document_id"])
    add_step(db, job, "بازیابی سرفصل، مفاهیم و منابع مجاز")
    user = db.get(User, job.created_by or doc.created_by)
    plan = propose_plan(db, doc, user, job_id=job.id)
    set_progress(db, job, 100)
    job.result = {"plan_id": str(plan.id), "status": plan.status}


def handle_content_generation(db, job):
    from app.models.content import ContentDocument, ContentPlan, ContentVersion
    from app.models.ops import OutboxEvent
    from app.core.database import utcnow
    from app.services.content_service import generate_content, run_qc

    payload = job.payload or {}
    set_progress(db, job, 15)
    doc = db.get(ContentDocument, payload["document_id"])
    add_step(db, job, "بازیابی سرفصل مصوب و منابع")
    if doc is None:
        raise ValueError("سند یافت نشد")
    plan = db.get(ContentPlan, payload.get("plan_id")) if payload.get("plan_id") else None
    if plan is None:
        # آخرین طرح تأییدشده یا طرح جدید
        plan = (
            db.query(ContentPlan)
            .filter(ContentPlan.document_id == doc.id, ContentPlan.status == "CONFIRMED")
            .order_by(ContentPlan.created_at.desc())
            .first()
        )
        if plan is None:
            from app.services.content_service import propose_plan, confirm_plan
            from app.models.identity import User

            user = db.get(User, doc.created_by)
            set_progress(db, job, 35)
            add_step(db, job, "طراحی آموزشی (مرحله اول)")
            plan = propose_plan(db, doc, user, job_id=job.id)
            confirm_plan(db, plan, user)
    set_progress(db, job, 55)
    add_step(db, job, "تولید محتوای ساختاریافته و اعتبارسنجی Schema")
    version = generate_content(db, doc, plan, db.get(User, doc.created_by), job_id=job.id)
    set_progress(db, job, 85)
    add_step(db, job, "کنترل کیفیت و ذخیره پیش‌نویس")
    db.add(OutboxEvent(event_type="content.generated", payload={
        "content_version_id": str(version.id), "document_id": str(doc.id),
    }))
    db.flush()
    set_progress(db, job, 100)
    job.result = {"content_version_id": str(version.id),
                  "qc_overall": (version.qc_report or {}).get("overall")}


def handle_content_full(db, job):
    """PLAN + CONTENT در یک Job (با تأیید خودکار طرح برای تجربه سریع‌تر)."""
    payload = dict(job.payload or {})
    payload["mode"] = "FULL"
    handle_content_generation(db, job)


def handle_block_regeneration(db, job):
    from app.models.content import ContentVersion
    from app.models.identity import User
    from app.services.content_service import regenerate_block

    payload = job.payload or {}
    set_progress(db, job, 30)
    version = db.get(ContentVersion, payload["content_version_id"])
    user = db.get(User, payload.get("user_id") or version.created_by)
    add_step(db, job, "بازتولید فقط بلوک هدف")
    regenerate_block(db, version, payload["block_id"], payload.get("instruction"),
                     user, job_id=job.id)
    set_progress(db, job, 100)
    job.result = {"content_version_id": str(version.id), "block_id": payload["block_id"],
                  "revision": version.revision}


def handle_question_generation(db, job):
    from app.models.identity import User
    from app.services.question_service import generate_questions

    payload = job.payload or {}
    set_progress(db, job, 25)
    user = db.get(User, job.created_by)
    add_step(db, job, "تولید سؤال‌های نگاشت‌شده به مفاهیم")
    questions = generate_questions(db, user, payload, job_id=job.id)
    set_progress(db, job, 90)
    add_step(db, job, "بررسی ساختاری و مشابهت با بانک")
    set_progress(db, job, 100)
    job.result = {
        "question_ids": [str(q.id) for q in questions],
        "message": "سؤال‌های تولیدی تا تأیید نقش مجاز وارد آزمون رسمی نمی‌شوند",
    }


def handle_export(db, job):
    import hashlib

    from app.models.content import ContentVersion
    from app.models.exports import ExportArtifact, ExportJob
    from app.services.export_service import render_export

    payload = job.payload or {}
    set_progress(db, job, 15)
    version = db.get(ContentVersion, payload["content_version_id"])
    export_job = db.get(ExportJob, payload["export_job_id"])
    add_step(db, job, f"تبدیل بلوک‌ها به قالب {payload['format']}")
    data, mime = render_export(db, version, payload["format"], payload.get("options"))
    set_progress(db, job, 70)
    add_step(db, job, "کنترل فایل و ذخیره Artifact")
    fmt = payload["format"].lower()
    file_name = f"content_v{version.version_number}_{version.id.hex[:8]}.{fmt}"
    info = LocalStorage().save(f"exports/{version.id}/{file_name}", data)
    if info["size"] == 0:
        raise ValueError("خروجی خروجی تولید شد ولی فایل خالی است")
    artifact = ExportArtifact(
        export_job_id=export_job.id, file_path=info["path"], file_name=file_name,
        mime=mime, sha256=info["sha256"], size_bytes=info["size"],
    )
    db.add(artifact)
    export_job.status = "SUCCEEDED"
    db.flush()
    set_progress(db, job, 100)
    job.result = {"export_job_id": str(export_job.id), "artifact_id": str(artifact.id),
                  "sha256": info["sha256"], "size": info["size"]}
