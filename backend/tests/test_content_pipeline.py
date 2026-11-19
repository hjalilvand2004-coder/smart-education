"""AC-01 / AC-03 / AC-05 / قفل بهینه: خط تولید محتوا و ویرایش بلوکی."""
import time

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.services.content_service import (create_document, generate_content,
                                          propose_plan, confirm_plan)


def _wait_job(client, headers, job_id):
    for _ in range(40):
        job = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
        if job["status"] in ("SUCCEEDED", "FAILED"):
            return job
        time.sleep(0.2)
    return job


def test_generation_requires_approved_syllabus(client, ctx, prof_headers):
    """AC-01: تولید فقط با اتصال به نسخه مصوب سرفصل."""
    import uuid

    from app.models.identity import User

    # نسخه DRAFT جدید
    resp = client.post("/api/v1/syllabus-imports", headers=prof_headers,
                       data={"course_id": ctx["course_id"], "text": "فصل ۱: پیش‌نویس\n1.1 موضوع"}).json()
    job = _wait_job(client, prof_headers, resp["job_id"])
    draft_sv = job["result"]["syllabus_version_id"]
    db = SessionLocal()
    user = db.get(User, uuid.UUID(ctx["prof_id"]))
    doc = create_document(db, user, {
        "course_id": ctx["course_id"], "syllabus_version_id": draft_sv,
        "title": "سند روی پیش‌نویس", "scope": {"concept_ids": [ctx["base_concept"]]}})
    plan = propose_plan(db, doc, user)
    confirm_plan(db, plan, user)
    try:
        generate_content(db, doc, plan, user)
        raise AssertionError("تولید روی سرفصل مصوب‌نشده نباید مجاز باشد")
    except AppError as e:
        assert "AC-01" in e.message or "مصوب" in e.message
    finally:
        db.rollback()
        db.close()


def test_block_edit_and_selective_regeneration(client, ctx, prof_headers, st_headers):
    """AC-03: بازتولید یک بخش، ویرایش دستی سایر بخش‌ها را از بین نمی‌برد."""
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند ویرایش بلوکی", "scope": {"concept_ids": [ctx["base_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    job = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                      headers=prof_headers, json={"mode": "FULL"}).json()
    job = _wait_job(client, prof_headers, job["job_id"])
    assert job["status"] == "SUCCEEDED"
    vid = job["result"]["content_version_id"]
    version = client.get(f"/api/v1/content-versions/{vid}", headers=prof_headers).json()
    blocks = version["blocks"]
    assert len(blocks) >= 5 and version["qc_report"]["overall"] in ("PASS", "WARN")

    # ویرایش دستی بلوک اول
    target = blocks[0]
    edited = client.patch(f"/api/v1/content-versions/{vid}/blocks/{target['id']}",
                          headers=prof_headers,
                          json={"patch": {"body": "متن ویرایش‌شده توسط استاد"},
                                "expected_revision": version["revision"]})
    assert edited.status_code == 200
    v2 = edited.json()
    assert v2["revision"] == version["revision"] + 1

    # بازتولید بلوک دوم → ویرایش بلوک اول باید حفظ شود
    other = blocks[1]
    regen = client.post(f"/api/v1/content-versions/{vid}/blocks/{other['id']}/regenerate",
                        headers=prof_headers, json={"instruction": "ساده‌تر کن"})
    job = _wait_job(client, prof_headers, regen.json()["job_id"])
    assert job["status"] == "SUCCEEDED"
    v3 = client.get(f"/api/v1/content-versions/{vid}", headers=prof_headers).json()
    first = next(b for b in v3["blocks"] if b["id"] == target["id"])
    assert first.get("body") == "متن ویرایش‌شده توسط استاد", "ویرایش دستی از بین رفته است!"
    second = next(b for b in v3["blocks"] if b["id"] == other["id"])
    assert "بازتولید" in (second.get("body") or "") or second.get("body") != other.get("body")


def test_revision_conflict_returns_409(client, ctx, prof_headers):
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند تداخل", "scope": {"concept_ids": [ctx["base_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    job = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                      headers=prof_headers, json={"mode": "FULL"}).json()
    job = _wait_job(client, prof_headers, job["job_id"])
    vid = job["result"]["content_version_id"]
    version = client.get(f"/api/v1/content-versions/{vid}", headers=prof_headers).json()
    stale_revision = version["revision"] - 1 if version["revision"] > 1 else version["revision"] + 5
    r = client.patch(f"/api/v1/content-versions/{vid}/blocks/{version['blocks'][0]['id']}",
                     headers=prof_headers,
                     json={"patch": {"body": "تلاش با نسخه قدیمی"}, "expected_revision": stale_revision})
    assert r.status_code == 409
    assert r.json()["error"]["details"]["current_revision"] == version["revision"]


def test_publish_gate_and_student_visibility(client, ctx, prof_headers, st_headers):
    """AC-05: محتوا پیش از تأیید و انتشار برای دانشجو در دسترس نیست."""
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند انتشار", "scope": {"concept_ids": [ctx["base_concept"], ctx["adv_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    job = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                      headers=prof_headers, json={"mode": "FULL"}).json()
    job = _wait_job(client, prof_headers, job["job_id"])
    vid = job["result"]["content_version_id"]

    # پیش از انتشار
    r = client.get(f"/api/v1/content-versions/{vid}", headers=st_headers)
    assert r.status_code == 403
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/contents", headers=st_headers)
    assert all(c["version_id"] != vid for c in r.json())

    # انتشار بدون تأیید → خطا
    r = client.post(f"/api/v1/content-versions/{vid}/publish", headers=prof_headers)
    assert r.status_code == 422

    client.post(f"/api/v1/content-versions/{vid}/reviews", headers=prof_headers,
                json={"decision": "APPROVE", "notes": "تأیید علمی"})
    r = client.post(f"/api/v1/content-versions/{vid}/publish", headers=prof_headers)
    assert r.status_code == 200

    # پس از انتشار دانشجو می‌بیند ولی فیلدهای مدیریتی ندارد
    r = client.get(f"/api/v1/content-versions/{vid}", headers=st_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PUBLISHED" and len(body["blocks"]) > 0
    assert body["qc_report"] is None and body["plan"] is None


def test_qc_coverage_report(client, ctx, prof_headers):
    """کنترل کیفیت: پوشش اهداف، ارجاع‌های معتبر، هشدار ساختاری."""
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند QC", "scope": {"concept_ids": [ctx["base_concept"], ctx["adv_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    job = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                      headers=prof_headers, json={"mode": "FULL"}).json()
    job = _wait_job(client, prof_headers, job["job_id"])
    vid = job["result"]["content_version_id"]
    version = client.get(f"/api/v1/content-versions/{vid}", headers=prof_headers).json()
    qc = version["qc_report"]
    assert qc["coverage_ratio"] is not None
    assert "این کنترل تضمین صحت علمی نیست" in qc["note"]
    # ارجاع نامعتبر تشخیص داده می‌شود اگر وارد شده باشد
    assert isinstance(qc["invalid_refs"], list)
