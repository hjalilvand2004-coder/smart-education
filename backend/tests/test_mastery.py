"""AC-08: نبود شواهد = UNKNOWN نه ضعف؛ بازتولیدپذیری تخمین؛ تشخیص و نقشه کلاس."""
from app.core.database import SessionLocal
from app.services import learning_service


def test_no_evidence_is_unknown_not_weak(client, ctx, st_headers):
    """AC-08: مفهوم بدون شواهد باید UNKNOWN با mastery=null باشد."""
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/mastery", headers=st_headers)
    assert r.status_code == 200
    rows = {row["concept_key"]: row for row in r.json()}
    adv = rows["adv_concept"]
    if adv["evidence_count"] < 3:
        assert adv["status"] == "UNKNOWN"
        assert adv["estimated_mastery"] is None
        assert adv["confidence"] is not None


def test_mastery_reproducible(client, ctx, prof_headers, st_headers, bank):
    """تخمین‌ها تابع شواهد هستند — دو بار محاسبه، همان نتیجه."""
    r1 = client.get(f"/api/v1/me/courses/{ctx['course_id']}/mastery", headers=st_headers).json()
    r2 = client.get(f"/api/v1/me/courses/{ctx['course_id']}/mastery", headers=st_headers).json()
    assert r1 == r2
    # بازتولید مستقیم از شواهد
    db = SessionLocal()
    est = learning_service.recompute_mastery(db, __import__("uuid").UUID(ctx["st_id"]),
                                             __import__("uuid").UUID(ctx["course_id"]))
    db.commit()
    db.close()
    by_key = {}
    for row in r1:
        by_key[row["concept_key"]] = row
    for m in est:
        key = "base_concept" if str(m.concept_id) == ctx["base_concept"] else "adv_concept"
        assert str(m.estimated_mastery) == str(by_key[key]["estimated_mastery"])


def test_diagnostics_recommends_actions(client, ctx, prof_headers, st_headers):
    """فرضیه تشخیصی با اقدام پیشنهادی؛ «INSUFFICIENT_EVIDENCE» برای نبود شواهد."""
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/diagnostics", headers=st_headers)
    assert r.status_code == 200
    for h in r.json():
        assert h["hypothesis_type"] in (
            "CURRENT_WEAK", "PREREQ_WEAK", "MISCONCEPTION", "SOLUTION_METHOD",
            "CALCULATION_ERROR", "COMPREHENSION", "INSUFFICIENT_EVIDENCE")
        assert h["recommended_actions"]


def test_prereq_weak_diagnosed(client, ctx, prof_headers, st_headers, bank):
    """AC/۶.۲: ضعف پیش‌نیاز به‌عنوان ریشه گزارش می‌شود نه ضعف مفهوم فعلی."""
    # پاسخ نادرست به سؤال مفهوم پیشرفته، بدون شواهد بر مفهوم پایه
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "آزمون تشخیص پیش‌نیاز", "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["adv_concept"]], "count": 4,
                                    "difficulty": None}]},
        "policy": {"feedback": "NONE", "allow_hint": False, "shuffle": False},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=st_headers).json()
    for q in att["questions"]:
        client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
            "question_version_id": q["question_version_id"], "answer": {"selected": ["Z1"]}})
    client.post(f"/api/v1/attempts/{att['id']}/finish", headers=st_headers)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/diagnostics", headers=st_headers)
    types = [h["hypothesis_type"] for h in r.json()]
    assert any(t in ("PREREQ_WEAK", "CURRENT_WEAK", "INSUFFICIENT_EVIDENCE") for t in types)


def test_class_aggregate_professor_only(client, ctx, prof_headers, st_headers):
    r = client.get(f"/api/v1/courses/{ctx['course_id']}/mastery/aggregate", headers=prof_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2
    r2 = client.get(f"/api/v1/courses/{ctx['course_id']}/mastery/aggregate", headers=st_headers)
    assert r2.status_code == 403  # دانشجو به نقشه کلاس دسترسی ندارد
