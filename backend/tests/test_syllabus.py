"""AC-02: ساختار استخراج‌شده تا تأیید انسانی اعتبار رسمی ندارد؛ AC-06: اثر تغییر سرفصل."""
import time


def _run_job(client, headers, resp):
    for _ in range(40):
        job = client.get(f"/api/v1/jobs/{resp['job_id']}", headers=headers).json()
        if job["status"] in ("SUCCEEDED", "FAILED"):
            return job
        time.sleep(0.2)
    return job


def test_import_creates_draft_needing_approval(client, ctx, prof_headers):
    """ورود سرفصل → نسخه DRAFT؛ بدون تأیید، نسخه مصوب نیست (AC-02)."""
    resp = client.post("/api/v1/syllabus-imports", headers=prof_headers,
                       data={"course_id": ctx["course_id"],
                             "text": "فصل ۱: تست ورود\n1.1 موضوع ورودی\n\nاهداف یادگیری:\n- هدف ورود"}).json()
    job = _run_job(client, prof_headers, resp)
    assert job["status"] == "SUCCEEDED"
    assert "پیش از اعتبار رسمی" in job["result"]["message"]
    vid = job["result"]["syllabus_version_id"]
    detail = client.get(f"/api/v1/syllabus-versions/{vid}", headers=prof_headers).json()
    assert detail["status"] == "DRAFT"
    assert detail["chapters"], "ساختار استخراج‌شده نباید خالی باشد"


def test_approved_version_not_editable_in_place(client, ctx, prof_headers):
    """تأیید دوباره همان نسخه مجاز نیست؛ تغییر یعنی نسخه جدید (بخش ۳.۱)."""
    r = client.post(f"/api/v1/syllabus-versions/{ctx['syllabus_version_id']}/approve",
                    headers=prof_headers, json={})
    assert r.status_code == 422


def test_student_sees_only_approved_syllabus(client, ctx, st_headers, prof_headers):
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/syllabus", headers=st_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"


def test_syllabus_diff_reports_changes(client, ctx, prof_headers):
    """AC-06: تغییر سرفصل → گزارش تفاوت برای بازبینی محتواها."""
    resp = client.post("/api/v1/syllabus-imports", headers=prof_headers,
                       data={"course_id": ctx["course_id"],
                             "text": "فصل ۱: مبانی جدید\n1.1 مفهوم پایه\n1.2 مفهوم پیشرفته\n1.3 موضوع اضافه\n\nاهداف یادگیری:\n- تفسیر مفهوم پایه\n- هدف جدید"}).json()
    job = _run_job(client, prof_headers, resp)
    new_vid = job["result"]["syllabus_version_id"]
    r = client.get(f"/api/v1/syllabus-versions/{new_vid}/diff",
                   params={"against": ctx["syllabus_version_id"]}, headers=prof_headers)
    assert r.status_code == 200
    diff = r.json()
    assert any("1.3" in t or "اضافه" in t for t in diff["added_topics"]) or diff["added_objectives"]


def test_concept_graph_has_relations(client, ctx, st_headers):
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/concept-graph", headers=st_headers)
    assert r.status_code == 200
    graph = r.json()
    node_keys = {n["key"] for n in graph["nodes"]}
    assert {"base_concept", "adv_concept"} <= node_keys
    assert any(e["type"] == "PREREQUISITE_OF" for e in graph["edges"])
