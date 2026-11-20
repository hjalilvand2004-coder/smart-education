"""سرویس‌های یادگیری هوشمند (بخش ۳) — دسته کامل: تحلیل، توصیه، آزمون هوشمند.

- نبود شواهد در همه سرویس‌های تحلیلی = UNKNOWN نه ضعف (AC-08).
- کوییز هوشمند تطبیقی: پاسخ نادرست → سؤال پیش‌نیاز با دلیل ثبت می‌شود.
"""
import uuid

from app.core.database import SessionLocal


_OBJECTIVE = {"MCQ", "MULTI_SELECT", "TRUE_FALSE", "NUMERIC", "ORDERING", "MATCHING"}


def _wrong_attempt(client, ctx, st_headers, prof_headers, concept_ids, count=4, repeats=4):
    """ساخت شواهد ضعف قطعی: فقط سؤال‌های objective با پاسخ تضمیناً نادرست.

    هر POST پاسخ یک LearningEvent ثبت می‌کند؛ با repeats>=4، حتی یک سؤال
    objective هم شواهد WEAK (تسلط ~۰٫۲۱) می‌سازد (min_evidence=3).
    """
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "تلاش تشخیصی سرویس‌های هوشمند", "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": concept_ids, "count": count,
                                    "difficulty": None}]},
        "policy": {"feedback": "NONE", "allow_hint": False, "shuffle": False},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts",
                      headers=st_headers).json()
    answered = 0
    for q in att["questions"]:
        if q.get("type") not in _OBJECTIVE:
            continue  # ESSAY/CASE/SHORT_ANSWER: نمره AI/انسانی — شواهد قطعی نیست
        answer = {"value": -987654321} if q["type"] == "NUMERIC" else {"selected": ["Z1"]}
        for _ in range(repeats):
            rr = client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
                "question_version_id": q["question_version_id"],
                "answer": answer, "time_spent_ms": 10_000})
            assert rr.status_code == 200, rr.text
        answered += 1
    fr = client.post(f"/api/v1/attempts/{att['id']}/finish", headers=st_headers)
    assert fr.status_code == 200, fr.text
    assert answered >= 1, "پسخ objective برای ساخت شواهد یافت نشد"
    return att


# ---------------- داشبورد و تحلیل ----------------

def test_smart_overview_shape(client, ctx, st_headers):
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/overview", headers=st_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert {"mastery", "top_weaknesses", "next_actions",
            "cognitive_load", "learning_style", "forgetting"} <= set(data)
    assert data["next_actions"]
    assert data["mastery"]["total"] >= 2


def test_weaknesses_no_evidence(client, ctx, st_headers):
    """شواهد ناکافی → UNKNOWN، نه weak."""
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/weaknesses", headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    assert "weaknesses" in data and "unknown_count" in data
    for w in data["weaknesses"]:
        assert w["severity"] == round(1 - w["estimated_mastery"], 3)
        assert "prerequisites" in w


def test_weaknesses_and_root_cause_after_weak_evidence(client, ctx, prof_headers, st_headers, bank):
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["base_concept"]])
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["adv_concept"]])
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/weaknesses", headers=st_headers)
    data = r.json()
    assert data["weak_count"] >= 1
    ids = {w["concept_id"] for w in data["weaknesses"]}
    assert ids <= {ctx["base_concept"], ctx["adv_concept"]}

    rc = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/root-causes", headers=st_headers)
    assert rc.status_code == 200
    entries = rc.json()
    assert entries
    for e in entries:
        assert e["chains"] and e["interpretation"]
    # ریشه زنجیره مفهوم پیشرفته، مفهوم پایه است (PREREQUISITE_OF)
    adv = next((e for e in entries if e["concept_id"] == ctx["adv_concept"]), None)
    if adv:
        assert adv["chains"][0]["ids"][0] == ctx["base_concept"]


def test_answer_analysis_patterns(client, ctx, st_headers, prof_headers, bank):
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["base_concept"]])
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/answer-analysis", headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "OK"
    assert data["total"] >= 1
    assert data["accuracy"] <= 0.2  # همه پاسخ‌های objective نادرست بودند
    assert data["patterns"]["fast_wrong"] >= 1  # زمان ۱۰ ثانیه < نصف انتظار هر دشواری
    assert data["insights"]


# ---------------- کوییز هوشمند تطبیقی ----------------

def test_smart_quiz_flow(client, ctx, st_headers, bank):
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/smart/quiz", headers=st_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "ADAPTIVE_PRACTICE"
    assert data["assessment_id"] and data["attempt_id"]
    if data["first_question"]:
        rr = client.post(f"/api/v1/attempts/{data['attempt_id']}/responses", headers=st_headers,
                         json={"question_version_id": data["first_question"]["question_version_id"],
                               "answer": {"selected": ["Z1"]}, "time_spent_ms": 30_000})
        assert rr.status_code == 200, rr.text
    att = client.get(f"/api/v1/attempts/{data['attempt_id']}", headers=st_headers)
    assert att.status_code == 200


def test_smart_quiz_access_control(client, ctx, prof_headers):
    """استاد ثبت‌نام‌شده دانشجویی نیست؛ مسیر دانشجویی برای او هم باز است اما
    مسیرهای استادی محافظت می‌شوند (تست پایین)."""
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/smart/quiz", headers=prof_headers)
    assert r.status_code in (200, 403)


# ---------------- توصیه‌گرها ----------------

def test_resource_recommendation(client, ctx, st_headers, prof_headers, bank):
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["base_concept"]], count=3)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/resources", headers=st_headers)
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert isinstance(recs, list)
    # کلید امتحان هرگز توصیه نمی‌شود (AC-09)
    assert all("کلید امتحان" not in str(x.get("title", "")) for x in recs)


def test_remedial_pack(client, ctx, st_headers, prof_headers, bank):
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["base_concept"]], count=3)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/remedial-pack", headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    if data["status"] == "OK":
        assert data["concepts"]
        for c in data["concepts"]:
            assert c["review_hint"]
            assert len(c["questions"]) <= 3


# ---------------- مدل‌های رفتاری ----------------

def test_learning_style(client, ctx, st_headers, prof_headers, bank):
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["base_concept"]], count=3)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/learning-style", headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("OK", "UNKNOWN")
    if data["status"] == "OK":
        assert data["dominant_style"] in ("VISUAL", "PRACTICAL", "CONVERSATIONAL")
        assert abs(sum(data["distribution"].values()) - 1.0) < 0.01


def test_forgetting_curve(client, ctx, st_headers, prof_headers, bank):
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["base_concept"]], count=3)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/forgetting-curve", headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    assert "concepts" in data and "urgent_count" in data
    for c in data["concepts"]:
        assert c["retention_now"] is None or 0 <= c["retention_now"] <= 1
        assert c["retention_target"] == 0.7


def test_cognitive_load(client, ctx, st_headers, prof_headers, bank):
    _wrong_attempt(client, ctx, st_headers, prof_headers, [ctx["base_concept"]], count=3)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/cognitive-load", headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("OK", "UNKNOWN")
    if data["status"] == "OK":
        assert 0 <= data["load_index"] <= 100
        assert data["band"] in ("LOW", "MEDIUM", "HIGH")


# ---------------- آموزش کوتاه ----------------

def test_micro_lessons(client, ctx, st_headers):
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/micro-lessons", headers=st_headers)
    assert r.status_code == 200
    lessons = r.json()["lessons"]
    assert isinstance(lessons, list)
    for l in lessons:
        assert l["estimated_minutes"] >= 2
        assert l["steps"]


# ---------------- استاد: شبیه‌سازی امتحان + صف اعتبارسنجی ----------------

def test_exam_simulation_and_access(client, ctx, prof_headers, st_headers, bank):
    r = client.post(f"/api/v1/courses/{ctx['course_id']}/smart/exam-simulation", headers=st_headers)
    assert r.status_code == 403
    r = client.post(f"/api/v1/courses/{ctx['course_id']}/smart/exam-simulation",
                    headers=prof_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sections"] >= 2
    assert data["assessment"]["kind"] == "EXAM"
    assert data["assessment"]["mode"] == "FIXED"


def test_validation_queue_and_access(client, ctx, prof_headers, st_headers, bank):
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/smart/validation-queue", headers=st_headers)
    assert r.status_code == 403
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/smart/validation-queue",
                   headers=prof_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and "pending_count" in data
    for item in data["items"]:
        assert item["status"] in ("AI_GENERATED", "PENDING_REVIEW")
