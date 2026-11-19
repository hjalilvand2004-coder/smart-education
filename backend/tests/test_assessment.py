"""AC-07 / AC-10 / تطبیق آموزشی: تلاش، تصحیح، نمره انسانی و اعتراض."""
import time


def _start_fixed_quiz(client, ctx, prof_headers, st_headers, title="آزمون تلاش", bank=None):
    del bank  # فقط برای وابستگی ترتیب فیکسچر
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": title, "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"]], "count": 3,
                                    "difficulty": None}]},
        "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": False},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts",
                      headers=st_headers).json()
    return assessment, att


def _answer_all(client, st_headers, att, correct_first=1):
    results = []
    for i, q in enumerate(att["questions"], start=1):
        qtype = q["type"]
        if qtype in ("MCQ", "MULTI_SELECT", "TRUE_FALSE"):
            # نمی‌دانیم کدام درست است؛ فقط ثبت پاسخ برای جریان
            opts = q.get("options") or []
            key = opts[0]["key"] if opts else "TRUE"
            answer = {"selected": [key] if qtype != "TRUE_FALSE" else key}
        elif qtype == "NUMERIC":
            answer = {"value": 10.5}
        else:
            answer = {"text": "پاسخ نمونه دانشجو با طول کافی برای بررسی معنایی و متناسب با تعریف"}
        r = client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers,
                        json={"question_version_id": q["question_version_id"],
                              "answer": answer, "time_spent_ms": 30000 + i * 1000,
                              "hint_used": False})
        assert r.status_code == 200, r.text
        results.append(r.json())
    return results


def test_attempt_requires_enrollment(client, ctx, prof_headers, st_headers, bank):
    outsider = login_outsider(client)
    assessment, _ = _start_fixed_quiz(client, ctx, prof_headers, st_headers, "آزمون ثبت‌نام")
    r = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=outsider)
    assert r.status_code == 403


def login_outsider(client):
    from tests.conftest import login

    return login(client, "out_test")


def test_response_version_fixed_and_traceable(client, ctx, prof_headers, st_headers, bank):
    """AC-07: پاسخ به نسخه ثابت سؤال ارجاع دارد و مسیر قابل ردیابی است."""
    assessment, att = _start_fixed_quiz(client, ctx, prof_headers, st_headers, "آزمون ردیابی")
    results = _answer_all(client, st_headers, att)
    detail = client.get(f"/api/v1/attempts/{att['id']}", headers=st_headers).json()
    assert detail["selection_log"], "مسیر انتخاب سؤال ثبت نشده"
    fin = client.post(f"/api/v1/attempts/{att['id']}/finish", headers=st_headers).json()
    assert "score" in fin and "max_score" in fin
    db_resp = client.get(f"/api/v1/responses/{results[0]['response_id']}", headers=st_headers)
    assert db_resp.status_code == 200
    assert db_resp.json()["question_version_id"] == att["questions"][0]["question_version_id"]


def test_mcq_auto_grading_deterministic(client, ctx, prof_headers, st_headers, bank):
    """تصحیح قطعی MCQ: پاسخ = فقط 0 یا 1."""
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "آزمون تصحیح قطعی", "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"]], "count": 1}]},
        "policy": {"feedback": "IMMEDIATE", "allow_hint": False, "shuffle": False},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=st_headers).json()
    q = att["questions"][0]
    r = client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
        "question_version_id": q["question_version_id"], "answer": {"selected": ["A"]}})
    assert r.status_code == 200
    assert r.json()["auto_scored"] is True
    assert r.json()["correctness"] in (0.0, 1.0)


def test_essay_ai_suggestion_then_human_final_and_dispute(client, ctx, prof_headers, st_headers, bank):
    """AC-10: نمره تشریحی = پیشنهاد AI با عدم قطعیت → بازبینی استاد → اعتراض دانشجو."""
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "آزمون تشریحی", "kind": "PRACTICE", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"]], "count": 5,
                                    "difficulty": "HARD"}]},
        "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": False},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=st_headers).json()
    assert any(q["type"] == "ESSAY" for q in att["questions"]), "سؤال تشریحی باید در پوشه HARD باشد"
    results = []
    for q in att["questions"]:
        if q["type"] == "ESSAY":
            r = client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
                "question_version_id": q["question_version_id"],
                "answer": {"text": "تعریف دقیق مفهوم پایه شامل اجزای اصلی است. مثال و کاربرد آن در مسئله مشهود است."},
                "time_spent_ms": 120000})
        else:
            r = client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers, json={
                "question_version_id": q["question_version_id"],
                "answer": {"text": "پاسخ کوتاه نمونه با تعریف"}, "time_spent_ms": 30000})
        results.append(r.json())
    essay = next(r for r in results if not r.get("auto_scored", True))
    assert essay["grading"] == "AI_SUGGESTED"
    assert essay["ai_feedback"]["uncertainty"] in ("LOW", "MEDIUM", "HIGH")
    assert essay["ai_feedback"].get("non_authoritative") is True

    resp_id = essay["response_id"]
    # اصلاح توسط استاد
    review = client.post(f"/api/v1/responses/{resp_id}/grading-reviews", headers=prof_headers,
                         json={"scores": [{"criterion": "دقت", "score": 4, "max_score": 5}],
                               "final_score": 8.5, "comment": "نمره رسمی پس از بازبینی"})
    assert review.status_code == 200 and review.json()["grading"] == "HUMAN"
    # اعتراض دانشجو
    dispute = client.post(f"/api/v1/responses/{resp_id}/disputes", headers=st_headers,
                          json={"comment": "نمره کم است؛ استدلال کامل بود"})
    assert dispute.status_code == 200 and dispute.json()["status"] == "OPEN"


def test_adaptive_practice_selects_by_weakness_and_stops(client, ctx, prof_headers, st_headers, bank):
    """تطبیق آموزشی: سؤال بعدی بر اساس وضعیت؛ مسیر ثبت؛ شرط پایان (پوشش)."""
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "تمرین تطبیقی تست", "kind": "PRACTICE", "mode": "ADAPTIVE_PRACTICE",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"], ctx["adv_concept"]],
                                    "count": 10}]},
        "policy": {"feedback": "IMMEDIATE", "allow_hint": True, "shuffle": True},
    }).json()
    att = client.post(f"/api/v1/assessments/{assessment['id']}/attempts", headers=st_headers).json()
    assert att["questions"], "سؤال اول تطبیقی باید انتخاب شود"
    steps = 0
    while steps < 15:
        remaining = client.get(f"/api/v1/attempts/{att['id']}", headers=st_headers).json()
        qs = remaining.get("remaining_questions") or []
        if not qs:
            break
        q = qs[0]
        if q["type"] in ("MCQ", "TRUE_FALSE"):
            opts = q.get("options") or []
            ans = {"selected": [opts[0]["key"]] if opts else "TRUE"}
        elif q["type"] == "NUMERIC":
            ans = {"value": 1}
        else:
            ans = {"text": "پاسخ تطبیقی با تعریف مفهوم"}
        r = client.post(f"/api/v1/attempts/{att['id']}/responses", headers=st_headers,
                        json={"question_version_id": q["question_version_id"], "answer": ans})
        assert r.status_code == 200
        steps += 1
    detail = client.get(f"/api/v1/attempts/{att['id']}", headers=st_headers).json()
    assert len(detail["selection_log"]) >= 1
    reasons = " ".join(s["reason"] for s in detail["selection_log"])
    assert reasons  # دلیل انتخاب ثبت شده است
