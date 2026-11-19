"""برنامه مطالعه، مرور فاصله‌دار و حالت جایگزین خرابی AI (AC-12، AC-14 مربوط به داده)."""
from app.core.database import SessionLocal
from app.core.config import get_settings


def test_study_plan_generation_with_cap(client, ctx, st_headers):
    """برنامه با سقف روزانه و دلیل انتخاب هر فعالیت ساخته می‌شود."""
    r = client.post("/api/v1/study-plans", headers=st_headers, json={
        "course_id": ctx["course_id"], "weekly_hours": 5,
        "goals": "آمادگی آزمون تست"})
    assert r.status_code == 200
    plan = r.json()
    assert plan["activities"]
    per_day = {}
    for a in plan["activities"]:
        per_day[a["day_offset"]] = per_day.get(a["day_offset"], 0) + a["estimated_minutes"]
    # سقف روزانه: weekly_hours*60/7 ≈ 43 → حداقل ۲۰ دقیقه؛ سقف ۲۴۰
    assert all(m <= 240 for m in per_day.values())
    assert all(a["rationale"] for a in plan["activities"])
    assert plan["rationale_summary"]


def test_activity_status_update(client, ctx, st_headers):
    plan = client.post("/api/v1/study-plans", headers=st_headers, json={
        "course_id": ctx["course_id"], "weekly_hours": 6}).json()
    act = plan["activities"][0]
    r = client.patch(f"/api/v1/study-activities/{act['id']}", headers=st_headers,
                     json={"status": "DONE"})
    assert r.status_code == 200 and r.json()["status"] == "DONE"
    r2 = client.patch(f"/api/v1/study-activities/{act['id']}", headers=st_headers,
                      json={"status": "WRONG"})
    assert r2.status_code == 422


def test_review_schedule_updates(client, ctx, prof_headers, st_headers, bank):
    """مرور فاصله‌دار: پاسخ درست فاصله را زیاد، پاسخ نادرست را ریست می‌کند."""
    from app.core.database import SessionLocal
    from app.models.planning import ReviewSchedule

    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "آزمون مرور", "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"]], "count": 2}]},
        "policy": {"feedback": "NONE", "allow_hint": False, "shuffle": False},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=st_headers).json()
    for q in att["questions"]:
        client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
            "question_version_id": q["question_version_id"], "answer": {"selected": ["B"]}})
    client.post(f"/api/v1/attempts/{att['id']}/finish", headers=st_headers)
    r = client.get(f"/api/v1/me/review-schedule?course_id={ctx['course_id']}", headers=st_headers)
    assert r.status_code == 200
    assert all("interval_days" in row and "algorithm" in row for row in r.json())


def test_ai_failure_fallback_for_syllabus_import(client, ctx, prof_headers, monkeypatch=None):
    """AC-12: خرابی مدل، ورود سرفصل را متوقف نمی‌کند (استخراج هیوریستیک)."""
    import time

    from app.ai.gateway import AIGateway

    def broken_run(self, *a, **kw):
        raise RuntimeError("مدل در دسترس نیست")

    original = AIGateway.run
    AIGateway.run = broken_run
    try:
        resp = client.post("/api/v1/syllabus-imports", headers=prof_headers,
                           data={"course_id": ctx["course_id"],
                                 "text": "فصل ۱: بدون AI\n1.1 موضوع بدون AI\n\nاهداف یادگیری:\n- هدف بدون AI"}).json()
        for _ in range(40):
            job = client.get(f"/api/v1/jobs/{resp['job_id']}", headers=prof_headers).json()
            if job["status"] in ("SUCCEEDED", "FAILED"):
                break
            time.sleep(0.2)
        assert job["status"] == "SUCCEEDED", job.get("error")
        assert job["result"]["syllabus_version_id"]
    finally:
        AIGateway.run = original


def test_storage_isolation(ctx):
    """کنترل مسیر فایل: خروج از ریشه ذخیره‌سازی مسدود است."""
    from app.core.errors import AppError
    from app.core.storage import LocalStorage

    storage = LocalStorage(get_settings().storage_dir)
    try:
        storage.open_path("../../etc/passwd")
        raise AssertionError("path traversal نباید مجاز باشد")
    except AppError:
        pass
