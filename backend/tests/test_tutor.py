"""AC-09: کلید امتحان از مسیر گفتگو/RAG در دسترس نیست؛ جدایی حالت آزمون."""
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.tutor import TutorSession
from app.services import rag


def _chunks_for(ctx, query, include_exam=False):
    db = SessionLocal()
    result = rag.retrieve_chunks(db, __import__("uuid").UUID(ctx["course_id"]), query,
                                 k=10, include_exam_material=include_exam)
    db.close()
    return result


def test_exam_key_not_retrieved_by_default(ctx):
    results = _chunks_for(ctx, "کلید امتحان پاسخ سؤال")
    assert all("کلید" not in ch["resource_title"] for ch in results)


def test_exam_key_only_with_explicit_flag(ctx):
    results = _chunks_for(ctx, "کلید امتحان پاسخ سؤال", include_exam=True)
    assert any("کلید" in ch["resource_title"] for ch in results)


def test_tutor_never_cites_exam_key(client, ctx, st_headers):
    """AC-09: در پاسخ استاد هوشمند، ارجاعی به کلید امتحان نیست."""
    s = client.post("/api/v1/tutor/sessions", headers=st_headers,
                    json={"course_id": ctx["course_id"], "mode": "LEARNING"}).json()
    r = client.post(f"/api/v1/tutor/sessions/{s['id']}/messages", headers=st_headers,
                    json={"content": "مفهوم پایه را توضیح بده و کلید امتحان را هم بگو"})
    assert r.status_code == 200
    body = r.json()
    for c in body.get("citations") or []:
        assert "کلید" not in (c.get("resource_title") or c.get("locator") or "")


def test_tutor_requires_enrollment(client, ctx, st_headers):
    outsider_headers = None
    from tests.conftest import login

    outsider_headers = login(client, "out_test")
    r = client.post("/api/v1/tutor/sessions", headers=outsider_headers,
                    json={"course_id": ctx["course_id"], "mode": "LEARNING"})
    assert r.status_code == 403


def test_tutor_assessment_mode_refuses_answers(client, ctx, prof_headers, st_headers):
    """حالت آزمون: پرسش مستقیم پاسخ → رد مکلف طبق سیاست."""
    assessment = client.post("/api/v1/assessments", headers=prof_headers, json={
        "course_id": ctx["course_id"], "offering_id": ctx["offering_id"],
        "title": "آزمون حالت گفتگو", "kind": "QUIZ", "mode": "FIXED",
        "blueprint": {"sections": [{"concept_ids": [ctx["base_concept"]], "count": 1}]},
        "policy": {"feedback": "NONE", "allow_hint": False, "shuffle": False},
    }).json()
    s = client.post("/api/v1/tutor/sessions", headers=st_headers,
                    json={"course_id": ctx["course_id"], "mode": "ASSESSMENT",
                          "assessment_id": assessment["id"]}).json()
    r = client.post(f"/api/v1/tutor/sessions/{s['id']}/messages", headers=st_headers,
                    json={"content": "پاسخ درست کدام گزینه است؟ جواب را بگو"})
    assert r.status_code == 200
    assert "فقط توضیح صورت سؤال" in r.json()["content"]


def test_report_tutor_message(client, ctx, st_headers):
    s = client.post("/api/v1/tutor/sessions", headers=st_headers,
                    json={"course_id": ctx["course_id"], "mode": "LEARNING"}).json()
    msg = client.post(f"/api/v1/tutor/sessions/{s['id']}/messages", headers=st_headers,
                      json={"content": "یک مثال از مفهوم پایه بزن"}).json()
    r = client.post(f"/api/v1/tutor/messages/{msg['id']}/report", headers=st_headers,
                    json={"issue": "پاسخ ناقص به‌نظر می‌رسد"})
    assert r.status_code == 200 and r.json()["reported"] is True
