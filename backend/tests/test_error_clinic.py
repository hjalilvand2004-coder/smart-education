"""تست کلینیک خطا: دفتر خطای آموزشی، برچسب قابل اصلاح و بازگشت خطا (نسخه ۳.۱)."""
import uuid

_OBJECTIVE = {"MCQ", "MULTI_SELECT", "TRUE_FALSE", "NUMERIC", "ORDERING", "MATCHING"}


def _answer_wrong(client, ctx, st_headers, prof_headers, concept_id, time_ms):
    """ساخت شواهد خطا — تلاش‌های چندگانه تا حداقل یک پاسخ objective ثبت شود؛
    توزیع نوع سؤال‌های mock با UUID تصادفی هر پایگاه‌داده متفاوت است."""
    total_answered = 0
    for _ in range(3):
        assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
            "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
            "title": "کوییز کلینیک خطا", "kind": "PRACTICE", "mode": "FIXED",
            "blueprint": {"sections": [{"concept_ids": [concept_id], "count": 4,
                                        "difficulty": None}]},
            "policy": {"feedback": "NONE", "allow_hint": False, "shuffle": False},
        }).json()
        att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts",
                          headers=st_headers).json()
        answered = 0
        for q in att["questions"]:
            if q.get("type") not in _OBJECTIVE:
                continue
            answer = {"value": -987654321} if q["type"] == "NUMERIC" else {"selected": ["Z1"]}
            rr = client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
                "question_version_id": q["question_version_id"],
                "answer": answer, "time_spent_ms": time_ms})
            assert rr.status_code == 200, rr.text
            answered += 1
        client.post(f"/api/v1/attempts/{att['id']}/finish", headers=st_headers)
        total_answered += answered
        if answered >= 1:
            break
    return total_answered


def test_error_clinic_builds_and_attributes(client, ctx, st_headers, prof_headers, bank):
    # پاسخ سریع‌ونادرست → الگوی RUSH_ERROR
    assert _answer_wrong(client, ctx, st_headers, prof_headers, ctx["base_concept"], 10_000) >= 1
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/error-clinic", headers=st_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["entries"]
    entry = next(e for e in data["entries"] if e["pattern_key"] == "RUSH_ERROR")
    assert entry["evidence_count"] >= 1 and entry["status"] == "OPEN"
    assert entry["suggested_practice"]["url"].startswith("/course/")

    # برچسب قابل اصلاح: توضیح دانشجو (مثلاً قطع اینترنت)
    r2 = client.post(f"/api/v1/me/error-notes/{entry['id']}/attribution", headers=st_headers,
                     json={"explanation": "در آن لحظه اینترنت قطع بود و پاسخ ناقص ارسال شد"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "ATTRIBUTED"

    # پاسخ کند‌و‌نادرست → الگوی دوم (شکاف مفهومی/وابستگی راهنما)
    assert _answer_wrong(client, ctx, st_headers, prof_headers, ctx["base_concept"], 200_000) >= 1
    r3 = client.get(f"/api/v1/me/courses/{ctx['course_id']}/error-clinic", headers=st_headers)
    keys = {e["pattern_key"] for e in r3.json()["entries"]}
    assert "RUSH_ERROR" in keys
    assert keys & {"CONCEPT_GAP", "HINT_DEPENDENT", "SIGN_OR_STEP_ERROR"}


def test_error_clinic_recurrence(client, ctx, st_headers, prof_headers, bank):
    assert _answer_wrong(client, ctx, st_headers, prof_headers, ctx["adv_concept"], 10_000) >= 1
    first = client.get(f"/api/v1/me/courses/{ctx['course_id']}/error-clinic",
                       headers=st_headers).json()
    e1 = next(e for e in first["entries"] if e["concept_id"] == ctx["adv_concept"]
              and e["pattern_key"] == "RUSH_ERROR")
    # خطای تکراری پس از مشاهده → شمارنده بازگشت
    assert _answer_wrong(client, ctx, st_headers, prof_headers, ctx["adv_concept"], 10_000) >= 1
    second = client.get(f"/api/v1/me/courses/{ctx['course_id']}/error-clinic",
                        headers=st_headers).json()
    e2 = next(e for e in second["entries"] if e["id"] == e1["id"])
    assert e2["recurrence_count"] >= 1


def test_error_note_isolation(client, ctx, st_headers):
    """دانشجوی دیگر دفتر خطای خالی دارد (داده فردی)."""
    r = client.post("/api/v1/auth/register", json={
        "username": "clinic_iso", "password": "Pass1234!",
        "full_name": "دانشجوی ایزوله", "role": "STUDENT"})
    assert r.status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "username": "clinic_iso", "password": "Pass1234!"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    r2 = client.get(f"/api/v1/me/courses/{ctx['course_id']}/error-clinic", headers=headers)
    assert r2.status_code in (200, 403)
    if r2.status_code == 200:
        assert r2.json()["entries"] == []
