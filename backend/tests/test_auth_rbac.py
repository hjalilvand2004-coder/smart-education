"""AC-05 / AC-10 / مجوزها: RBAC و کنترل دسترسی سطح رکورد."""
from tests.conftest import login


def test_login_wrong_password(client, ctx):
    r = client.post("/api/v1/auth/login", json={"username": "prof_test", "password": "bad"})
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_me_returns_course_roles(client, ctx, prof_headers):
    r = client.get("/api/v1/me", headers=prof_headers)
    assert r.status_code == 200
    roles = {cr["role"] for cr in r.json()["course_roles"]}
    assert "PROFESSOR" in roles


def test_student_cannot_publish_content(client, ctx, st_headers, prof_headers):
    """AC-05: دانشجو هرگز انتشار نمی‌تواند بکند."""
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند مجوز", "scope": {"concept_ids": [ctx["base_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    version = client.post(
        f"/api/v1/content-documents/{doc['id']}/generation-jobs", headers=prof_headers,
        json={"mode": "FULL"}).json()
    import time
    for _ in range(40):
        job = client.get(f"/api/v1/jobs/{version['job_id']}", headers=prof_headers).json()
        if job["status"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.2)
    assert job["status"] == "SUCCEEDED"
    vid = job["result"]["content_version_id"]
    client.post(f"/api/v1/content-versions/{vid}/reviews", headers=prof_headers,
                json={"decision": "APPROVE"})
    r = client.post(f"/api/v1/content-versions/{vid}/publish", headers=st_headers)
    assert r.status_code == 403


def test_ta_cannot_publish_by_policy(client, ctx, ta_headers, prof_headers):
    """دستیار پیش‌نویس می‌سازد ولی انتشار طبق سیاست دانشگاه فقط استاد."""
    doc = client.post("/api/v1/content-documents", headers=ta_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": "سند دستیار", "scope": {"concept_ids": [ctx["base_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    assert doc.get("title") == "سند دستیار"
    job = client.post(
        f"/api/v1/content-documents/{doc['id']}/generation-jobs", headers=ta_headers,
        json={"mode": "FULL"}).json()
    import time
    for _ in range(40):
        j = client.get(f"/api/v1/jobs/{job['job_id']}", headers=ta_headers).json()
        if j["status"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.2)
    vid = j["result"]["content_version_id"]
    client.post(f"/api/v1/content-versions/{vid}/reviews", headers=prof_headers,
                json={"decision": "APPROVE"})
    r = client.post(f"/api/v1/content-versions/{vid}/publish", headers=ta_headers)
    assert r.status_code == 403  # S360_TA_CAN_PUBLISH پیش‌فرض False


def test_outsider_cannot_access_course_data(client, ctx):
    """دانشجوی غیرثبت‌نام به سرفصل/محتوای درس دسترسی ندارد."""
    from tests.conftest import login

    outsider = login(client, "out_test")
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/syllabus", headers=outsider)
    assert r.status_code == 403
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/contents", headers=outsider)
    assert r.status_code == 403


def test_audit_log_written_on_publish(client, ctx, admin_headers, prof_headers):
    r = client.get("/api/v1/audit-logs", headers=admin_headers)
    assert r.status_code == 200
    actions = [row["action"] for row in r.json()]
    assert "CONTENT_PUBLISH" in actions or "SYLLABUS_APPROVE" in actions


def test_audit_logs_forbidden_for_professor(client, ctx, prof_headers):
    r = client.get("/api/v1/audit-logs", headers=prof_headers)
    assert r.status_code == 403


def test_audit_forbidden_for_student(client, ctx, st_headers):
    r = client.get("/api/v1/audit-logs", headers=st_headers)
    assert r.status_code == 403
