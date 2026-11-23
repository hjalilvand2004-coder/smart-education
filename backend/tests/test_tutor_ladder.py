"""تست نردبان راهنمایی استاد هوشمند و «اینجا گیر کردم» (نسخه ۳.۱)."""
import uuid


def _make_exam_assessment(client, ctx, prof_headers, bank):
    r = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "آزمون نردبان", "kind": "EXAM", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"]],
                                    "count": 2, "difficulty": None}]},
        "policy": {"feedback": "AFTER_FINISH", "allow_hint": False, "shuffle": False},
    })
    assert r.status_code == 201 or r.status_code == 200, r.text
    return r.json()


def test_tutor_ladder_guide_mode(client, ctx, st_headers):
    r = client.post("/api/v1/tutor/sessions", headers=st_headers,
                    json={"course_id": ctx["course_id"], "mode": "LEARNING"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    m = client.post(f"/api/v1/tutor/sessions/{sid}/messages", headers=st_headers,
                    json={"content": "چطور مفهوم پایه را در مسئله به‌کار ببرم؟",
                          "help_mode": "GUIDE"})
    assert m.status_code == 200, m.text
    meta = m.json()["meta"]
    assert meta["help_mode"] == "GUIDE"
    assert meta["ladder_level"] <= 2, "حالت GUIDE نباید راه‌حل کامل بدهد (سطح ≤ ۲)"
    assert "سؤال راهنما" in m.json()["content"] or "قدم اول" in m.json()["content"]


def test_tutor_ladder_explain_mode(client, ctx, st_headers):
    r = client.post("/api/v1/tutor/sessions", headers=st_headers,
                    json={"course_id": ctx["course_id"], "mode": "LEARNING"})
    sid = r.json()["id"]
    m = client.post(f"/api/v1/tutor/sessions/{sid}/messages", headers=st_headers,
                    json={"content": "مفهوم پایه را با مثال توضیح بده",
                          "help_mode": "EXPLAIN"})
    assert m.status_code == 200
    meta = m.json()["meta"]
    assert meta["help_mode"] == "EXPLAIN" and meta["ladder_level"] >= 3


def test_tutor_assessment_policy_locks_ladder(client, ctx, st_headers, prof_headers, bank):
    """در نشست متصل به آزمون، حتی درخواست EXPLAIN هم به سطح ۱ محدود می‌شود."""
    a = _make_exam_assessment(client, ctx, prof_headers, bank)
    r = client.post("/api/v1/tutor/sessions", headers=st_headers,
                    json={"course_id": ctx["course_id"], "mode": "ASSESSMENT",
                          "assessment_id": a["id"]})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    m = client.post(f"/api/v1/tutor/sessions/{sid}/messages", headers=st_headers,
                    json={"content": "پاسخ سؤال را بگو", "help_mode": "EXPLAIN"})
    assert m.status_code == 200
    meta = m.json()["meta"]
    assert meta["help_mode"] == "GUIDE" and meta["ladder_level"] <= 1
    assert "آزمون" in meta["policy_note"]


def test_stuck_mark_creates_anchored_session(client, ctx, st_headers):
    """«اینجا گیر کردم»: علامت + ورود استاد هوشمند از همان نقطه."""
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/stuck-marks", headers=st_headers,
                    json={"kind": "STEP_UNCLEAR",
                          "block_anchor": "انتقال جمله منفی در تساوی",
                          "note": "در مرحله دوم حل گیر کردم"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["kind_label"] and data["tutor_session_id"]
    # پاسخ استاد باید به همان عبارت ارجاع دهد
    hist = client.get(f"/api/v1/tutor/sessions/{data['tutor_session_id']}/messages",
                      headers=st_headers).json()
    assert hist and hist[-1]["role"] == "assistant"
    joined = " ".join(h["content"] for h in hist)
    assert "انتقال جمله منفی" in joined


def test_stuck_mark_invalid_kind(client, ctx, st_headers):
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/stuck-marks", headers=st_headers,
                    json={"kind": "LOST_INTERNET", "block_anchor": "x"})
    assert r.status_code == 422


def test_stuck_mark_without_anchor(client, ctx, st_headers):
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/stuck-marks", headers=st_headers,
                    json={"kind": "NOT_UNDERSTOOD"})
    assert r.status_code == 422
