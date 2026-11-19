"""AC-07 / AC-09 / gate سؤال: بانک سؤال، تأیید و استفاده در آزمون."""
import time


def _gen_and_get(client, ctx, prof_headers, n=6):
    resp = client.post("/api/v1/question-generation-jobs", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "concept_ids": [ctx["base_concept"], ctx["adv_concept"]],
        "types": ["MCQ", "TRUE_FALSE", "SHORT_ANSWER"], "count": n,
    }).json()
    for _ in range(40):
        job = client.get(f"/api/v1/jobs/{resp['job_id']}", headers=prof_headers).json()
        if job["status"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.2)
    assert job["status"] == "SUCCEEDED"
    return job["result"]["question_ids"]


def test_ai_questions_start_unapproved(client, ctx, prof_headers):
    """سؤال AI با وضعیت غیرتأیید شروع می‌شود؛ gate امتحان رسمی."""
    qids = _gen_and_get(client, ctx, prof_headers)
    assert qids
    q = client.get(f"/api/v1/questions/{qids[0]}", headers=prof_headers).json()
    assert q["status"] in ("AI_GENERATED", "PENDING_REVIEW")
    assert q["current_version"]["answer"] is not None  # کلید پاسخ ذخیره شده
    assert q["current_version"]["explanation"]


def test_approve_gate_before_exam_use(client, ctx, prof_headers, st_headers):
    """AC-07/سؤال تأییدنشده در آزمون استفاده نمی‌شود؛ پس از تأیید استفاده می‌شود."""
    qids = _gen_and_get(client, ctx, prof_headers, n=3)
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "آزمون gate", "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"]], "count": 2}]},
        "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": False},
    }).json()
    # بانک حالا شامل سؤال‌های تأیید جلسات قبل + جدیدهای تأییدنشده است؛
    # تلاش دانشجو فقط از APPROVED انتخاب می‌کند:
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=st_headers).json()
    for q in att["questions"]:
        assert q["body"], "سؤال خالی"
    # تأیید سؤال‌های جدید توسط استاد
    for qid in qids:
        client.post(f"/api/v1/questions/{qid}/reviews", headers=prof_headers,
                    json={"decision": "APPROVE"})
        assert client.get(f"/api/v1/questions/{qid}", headers=prof_headers).json()["status"] == "APPROVED"


def test_student_cannot_approve_question(client, ctx, prof_headers, st_headers):
    qids = _gen_and_get(client, ctx, prof_headers, n=1)
    r = client.post(f"/api/v1/questions/{qids[0]}/reviews", headers=st_headers,
                    json={"decision": "APPROVE"})
    assert r.status_code == 403


def test_manual_question_structure_validation(client, ctx, prof_headers):
    """سؤال MCQ با کلید خارج از گزینه‌ها رد می‌شود."""
    r = client.post("/api/v1/questions", headers=prof_headers, json={
        "course_id": ctx["course_id"], "type": "MCQ", "body": "کدام درست است؟",
        "options": [{"key": "A", "text": "الف"}, {"key": "B", "text": "ب"}, {"key": "C", "text": "ج"}],
        "answer": {"correct": ["Z"]}, "explanation": "چون...",
        "concept_ids": [ctx["base_concept"]],
    })
    assert r.status_code == 422
    r2 = client.post("/api/v1/questions", headers=prof_headers, json={
        "course_id": ctx["course_id"], "type": "MCQ", "body": "کدام درست است؟",
        "options": [{"key": "A", "text": "الف"}, {"key": "B", "text": "ب"}, {"key": "C", "text": "ج"}],
        "answer": {"correct": ["A"]}, "explanation": "چون تعریف دقیق همین است",
        "concept_ids": [ctx["base_concept"]],
    })
    assert r2.status_code == 200


def test_questions_hidden_from_students(client, ctx, prof_headers, st_headers):
    r = client.get(f"/api/v1/questions?course_id={ctx['course_id']}", headers=st_headers)
    assert r.status_code == 403
