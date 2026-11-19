"""AC-13: Idempotency؛ مشارکت دانشجو (بخش ۹)؛ رویدادهای outbox."""
import time


def test_idempotency_same_key_same_job(client, ctx, prof_headers):
    """AC-13: اجرای مجدد با همان Idempotency-Key، Job تکراری نمی‌سازد."""
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند idempotency", "scope": {"concept_ids": [ctx["base_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    key = "test-key-12345"
    r1 = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                     headers={**prof_headers, "Idempotency-Key": key},
                     json={"mode": "FULL"})
    r2 = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                     headers={**prof_headers, "Idempotency-Key": key},
                     json={"mode": "FULL"})
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["job_id"] == r2.json()["job_id"]
    assert r2.json()["idempotent_replay"] is True


def test_export_idempotency(client, ctx, prof_headers):
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند خروجی idem", "scope": {"concept_ids": [ctx["base_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    job = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                      headers=prof_headers, json={"mode": "FULL"}).json()
    for _ in range(40):
        j = client.get(f"/api/v1/jobs/{job['job_id']}", headers=prof_headers).json()
        if j["status"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.2)
    vid = j["result"]["content_version_id"]
    client.post(f"/api/v1/content-versions/{vid}/reviews", headers=prof_headers,
                json={"decision": "APPROVE"})
    client.post(f"/api/v1/content-versions/{vid}/publish", headers=prof_headers)
    key = "export-key-99"
    e1 = client.post(f"/api/v1/content-versions/{vid}/exports",
                     headers={**prof_headers, "Idempotency-Key": key}, json={"format": "PDF"})
    e2 = client.post(f"/api/v1/content-versions/{vid}/exports",
                     headers={**prof_headers, "Idempotency-Key": key}, json={"format": "PDF"})
    assert e1.json()["job_id"] == e2.json()["job_id"]


def test_student_creation_full_cycle(client, ctx, st_headers, prof_headers):
    """چرخه DRAFT → AI_FEEDBACK → SUBMITTED → PEER_REVIEW → TEACHER_REVIEW → APPROVED
    بدون ورود مستقیم به بانک رسمی."""
    creation = client.post("/api/v1/student-creations", headers=st_headers, json={
        "course_id": ctx["course_id"], "activity_type": "EXPLANATION",
        "concept_id": ctx["base_concept"],
        "content": {"title": "توضیح من", "body": "مفهوم پایه یعنی تعریف دقیق پایه؛ با مثال ملموس می‌توان "
                                                 "آن را نشان داد و با ضدنمونه مرز آن را روشن کرد. "
                                                 "مثال: در مسئله کلاسی... (متن کامل برای کفایت)"},
        "ai_use_disclosed": False,
    }).json()
    assert creation["status"] == "AI_FEEDBACK"
    assert creation["ai_feedback"]["feedback"]

    submitted = client.post(f"/api/v1/student-creations/{creation['id']}/submit",
                            headers=st_headers).json()
    assert submitted["status"] in ("PEER_REVIEW", "SUBMITTED")

    # بررسی همتا (امیر همکلاسی نیست در ctx؛ فقط استاد نهایی بررسی می‌کند در تست)
    r = client.post(f"/api/v1/student-creations/{creation['id']}/teacher-reviews",
                    headers=prof_headers, json={"decision": "APPROVE", "comment": "خوب بود"})
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"

    # بانک رسمی: سؤال جدیدی از این تولید ساخته نشده است
    bank = client.get(f"/api/v1/questions?course_id={ctx['course_id']}", headers=prof_headers).json()
    assert all(q["current_version"]["body"] != "توضیح من" for q in bank["items"])


def test_banned_content_rejected(client, ctx, st_headers):
    r = client.post("/api/v1/student-creations", headers=st_headers, json={
        "course_id": ctx["course_id"], "activity_type": "CRITIQUE",
        "content": {"title": "نقد", "body": "این توضیح خیلی احمقانه است"}})
    assert r.status_code == 422


def test_outbox_event_emitted_on_publish(client, ctx, prof_headers):
    """رویداد انتشار برای یکپارچه‌سازی (LMS/باشگاه/داشبورد) در outbox ثبت می‌شود."""
    from app.core.database import SessionLocal
    from app.models.ops import OutboxEvent

    db = SessionLocal()
    events = db.query(OutboxEvent).filter(OutboxEvent.event_type == "content.published").all()
    db.close()
    assert events


def test_job_listing_and_status(client, ctx, prof_headers):
    jobs = client.get("/api/v1/jobs", headers=prof_headers).json()
    assert jobs and all(k in jobs[0] for k in ("id", "kind", "status", "progress"))
