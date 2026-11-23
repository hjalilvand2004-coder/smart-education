"""تست «به من یاد بده» — بازگویی دانشجو با روبرک AI (نسخه ۳.۱)."""
import uuid


def test_teach_back_full_flow(client, ctx, st_headers):
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/teach-backs", headers=st_headers,
                    json={"concept_id": ctx["base_concept"], "modality": "TEXT",
                          "content": ("مفهوم پایه یعنی شرط بنیادی تعریف؛ هر ساختار بعدی بر پایه "
                                      "این تعریف بنا می‌شود و ارتباط مستقیم با مفهوم پیشرفته دارد. "
                                      "مثلاً در حل مسئله، ابتدا شرط را بررسی می‌کنیم.")})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["concept_name"]
    scores = data["rubric_scores"]
    assert scores and len(scores) >= 3
    criteria = {s["criterion"] for s in scores}
    assert any("دقت تعریف" in c for c in criteria)
    assert any("پوشش روابط" in c for c in criteria)
    for s in scores:
        assert 0 <= s["score"] <= s["max_score"]
    assert data["follow_up_question"]
    assert "نمره رسمی" in data["note"]


def test_teach_back_too_short(client, ctx, st_headers):
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/teach-backs", headers=st_headers,
                    json={"concept_id": ctx["base_concept"], "modality": "TEXT",
                          "content": "کوتاه"})
    assert r.status_code == 422


def test_teach_back_concept_of_other_course(client, ctx, st_headers):
    r = client.post(f"/api/v1/me/courses/{ctx['course_id']}/teach-backs", headers=st_headers,
                    json={"concept_id": str(uuid.uuid4()), "modality": "TEXT",
                          "content": "یک توضیح کامل و طولانی برای مفهومی که وجود ندارد."})
    assert r.status_code == 404
