"""تست بازطراحی علمی سرویس‌های تحلیلی (بازخورد ۳.۱): ترجیحات به‌جای سبک ثابت،
نشانه‌های دشواری + خودگزارش، روایت تسلط و کنترل پوشش آزمون تطبیقی."""
import uuid

_OBJECTIVE = {"MCQ", "MULTI_SELECT", "TRUE_FALSE", "NUMERIC", "ORDERING", "MATCHING"}


def _weak_evidence(client, ctx, st_headers, prof_headers, concept_id, count=3):
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "شواهد بازطراحی علمی", "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [concept_id], "count": count,
                                    "difficulty": None}]},
        "policy": {"feedback": "NONE", "allow_hint": False, "shuffle": False},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts",
                      headers=st_headers).json()
    for q in att["questions"]:
        if q.get("type") not in _OBJECTIVE:
            continue
        answer = {"value": -987654321} if q["type"] == "NUMERIC" else {"selected": ["Z1"]}
        for _ in range(4):
            client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
                "question_version_id": q["question_version_id"],
                "answer": answer, "time_spent_ms": 10_000})
    fr = client.post(f"/api/v1/attempts/{att['id']}/finish", headers=st_headers)
    return fr.json()


def test_interaction_pattern_not_fixed_label(client, ctx, st_headers, prof_headers, bank):
    _weak_evidence(client, ctx, st_headers, prof_headers, ctx["base_concept"], count=2)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/learning-style",
                   headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("OK", "UNKNOWN")
    if data["status"] == "OK":
        assert data["model"] == "interaction-pattern-v2"
        assert data["is_fixed_label"] is False
        assert "قابل تغییر" in data["label"] or "الگوی کنونی" in data["label"]
        assert "بهتر یاد می‌گیرید" not in data["label"], "ادعای توانایی ثابت ممنوع"
        assert data["changeable_note"]


def test_difficulty_signals_self_report_and_confounds(client, ctx, st_headers, prof_headers, bank):
    _weak_evidence(client, ctx, st_headers, prof_headers, ctx["base_concept"], count=2)
    r = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/cognitive-load",
                   headers=st_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("OK", "UNKNOWN")
    if data["status"] == "OK":
        assert data["model"] == "difficulty-signals-v2"
        assert "مثال ساده‌تر" in data["self_report_question"]
        assert "اینترنت" in data["confounds_note"] or "دسترس‌پذیری" in data["confounds_note"]
        assert "فشار شناختی بالاست" not in data["recommendation"], "نام‌گذاری محتاطانه الزامی"


def test_mastery_narrative_and_uncertainty(client, ctx, st_headers, prof_headers, bank):
    _weak_evidence(client, ctx, st_headers, prof_headers, ctx["base_concept"])
    rows = client.get(f"/api/v1/me/courses/{ctx['course_id']}/mastery",
                      headers=st_headers).json()
    weak = next(m for m in rows if m["concept_id"] == ctx["base_concept"])
    assert weak["status"] == "WEAK"
    nar = weak["narrative"]
    assert {"state_label", "evidence_line", "why", "next_step",
            "uncertainty_spread", "evidence_diverse"} <= set(nar)
    assert nar["state_label"] == "نیازمند تمرین"
    assert nar["why"] and nar["next_step"]["label"]
    assert nar["uncertainty_spread"] is not None and nar["uncertainty_spread"] > 0
    assert isinstance(nar["evidence_diverse"], bool)
    # UNKNOWN خنثی است، نه هشدار
    unk = next((m for m in rows if m["status"] == "UNKNOWN"), None)
    if unk:
        assert unk["narrative"]["state_label"] == "هنوز ارزیابی نشده"
        assert "خنثی" in unk["narrative"]["why"]


def test_weaknesses_are_hypotheses(client, ctx, st_headers, prof_headers, bank):
    _weak_evidence(client, ctx, st_headers, prof_headers, ctx["base_concept"])
    data = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/weaknesses",
                      headers=st_headers).json()
    assert data["weaknesses"]
    for w in data["weaknesses"]:
        assert w["nature"] == "HYPOTHESIS"
        assert w["probe"]["type"] == "DIAGNOSTIC_QUIZ"


def test_adaptive_coverage_reported(client, ctx, st_headers, prof_headers, bank):
    q = client.post(f"/api/v1/me/courses/{ctx['course_id']}/smart/quiz", headers=st_headers).json()
    assert q["mode"] == "ADAPTIVE_PRACTICE"
    if q["first_question"]:
        client.post(f"/api/v1/attempts/{q['attempt_id']}/responses", headers=st_headers, json={
            "question_version_id": q["first_question"]["question_version_id"],
            "answer": {"selected": ["Z1"]}, "time_spent_ms": 30_000})
    fr = client.post(f"/api/v1/attempts/{q['attempt_id']}/finish", headers=st_headers)
    assert fr.status_code == 200, fr.text
    cov = fr.json().get("coverage")
    assert cov is not None
    assert {"blueprint_concepts", "covered_concepts", "missing_concepts",
            "coverage_ratio"} <= set(cov)
    assert 0 <= (cov["coverage_ratio"] or 0) <= 1


def test_forgetting_scheduling_note(client, ctx, st_headers, prof_headers, bank):
    _weak_evidence(client, ctx, st_headers, prof_headers, ctx["base_concept"], count=2)
    data = client.get(f"/api/v1/me/courses/{ctx['course_id']}/smart/forgetting-curve",
                      headers=st_headers).json()
    assert "زمان‌بندی پیشنهادی مرور" in data["scheduling_vs_memory_note"]
