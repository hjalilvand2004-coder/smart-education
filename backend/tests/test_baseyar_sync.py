"""تست یکپارچگی پایه‌یار۳۶۰: واکشی اولیه، رویداد نسخه‌دار، تطبیق دوره‌ای و
قاعده طلایی «بدون بازنویسی بی‌صدا» (بازخورد ۳.۱).

این تست روی «درس اختصاصی BYR101» اجرا می‌شود تا تغییر نسخه سرفصل، نسخه‌های
درس TST101 (متعلق به سایر تست‌ها) را SUPERSEDED نکند. چرخه در یک تابع
idempotent اجرا می‌شود تا ترتیب الفبایی تست‌ها اهمیت نداشته باشد."""
from app.core.database import SessionLocal
from app.models.courses import Course, CourseOffering
from app.models.identity import User
from app.services import baseyar_service
from app.services.syllabus_service import approve_version, import_from_source

_SHARED: dict = {"stage": 0}


def _setup_course() -> None:
    """درس اختصاصی + سرفصل مصوب با عنوان‌های منطبق بر داده نمونه مرجع."""
    if _SHARED["stage"] >= 1:
        return
    db = SessionLocal()
    try:
        prof = db.query(User).filter(User.username == "prof_test").first()
        student = db.query(User).filter(User.username == "st_test").first()
        course = Course(code="BYR101", title="درس پایه‌یار ایزوله",
                        department="گروه تست", created_by=prof.id)
        db.add(course)
        db.flush()
        offering = CourseOffering(course_id=course.id, term="ترم مرجع",
                                  professor_id=prof.id)
        db.add(offering)
        db.flush()
        from app.models.courses import Enrollment
        from app.models.identity import CourseRole

        db.add(CourseRole(course_id=course.id, user_id=prof.id, role="PROFESSOR"))
        db.add(Enrollment(offering_id=offering.id, student_id=student.id))
        text = ("فصل ۱: مرجع\n"
                "1.1 موضوع مرجع یک\n"
                "1.2 موضوع مرجع دو\n\n"
                "اهداف یادگیری:\n- توضیح موضوع مرجع یک")
        sv = import_from_source(db, course, prof.id, text=text, source_kind="TEXT")
        approve_version(db, sv, prof)
        db.commit()
        _SHARED.update(course_id=str(course.id), code="BYR101", stage=1)
    finally:
        db.close()


def _seed_reference(version: str) -> None:
    code = _SHARED["code"]
    topics = [
        {"reference_id": f"{code}:t1", "title": "1.1 موضوع مرجع یک", "suggested_hours": 4},
        {"reference_id": f"{code}:t2", "title": "1.2 موضوع مرجع دو", "suggested_hours": 6},
    ]
    if version == "v2":
        topics[0]["title"] = "1.1 موضوع مرجع یک (بازنگری‌شده)"
        topics.append({"reference_id": f"{code}:t9", "title": "موضوع جدید مرجع",
                       "suggested_hours": 3})
        topics = [t for t in topics if t["reference_id"] != f"{code}:t2"]
    payload = {
        "reference_id": code, "reference_version": version,
        "title": "درس پایه‌یار ایزوله (مرجع)",
        "chapters": [{"reference_id": f"{code}:ch1", "title": "فصل اول",
                      "topics": topics}],
    }
    baseyar_service.SAMPLE_REFERENCES.setdefault(code, {})[version] = payload


def _run_flow(client, ctx, prof_headers, st_headers) -> None:
    """واکشی اولیه → رویداد نسخه‌دار v2 → بررسی → تأیید نسخه → تطبیق دوره‌ای."""
    _setup_course()
    if _SHARED["stage"] >= 2:
        return
    _seed_reference("v1")

    # ---------- واکشی اولیه ----------
    r = client.post("/api/v1/integration/baseyar/sync", headers=prof_headers,
                    json={"course_id": _SHARED["course_id"], "mode": "INITIAL_PULL"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "SYNCED"
    st = client.get(f"/api/v1/integration/baseyar/status?course_id={_SHARED['course_id']}",
                    headers=prof_headers).json()
    assert st["owner_system"] == "پایه‌یار۳۶۰"
    assert st["sync_state"] == "VALID" and st["reference_version"] == "v1"
    assert st["note"].startswith("منبع حقیقت")

    # ---------- رویداد نسخه‌دار v2: تغییرنام + حذف + افزودن ----------
    _seed_reference("v2")
    before = client.get(f"/api/v1/me/courses/{_SHARED['course_id']}/mastery",
                        headers=st_headers).json()
    r = client.post("/api/v1/integration/baseyar/sync", headers=prof_headers,
                    json={"course_id": _SHARED["course_id"], "mode": "CHANGE_EVENT"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "REVIEW_REQUIRED"
    assert "بررسی استاد" in data["message"]
    report = data["report"]
    assert report["reference_version_new"] == "v2"
    assert report["topics_removed"] == 1 and report["topics_renamed"] == 1
    assert report["topics_added"] == 1
    assert report["mappings_needing_review"] >= 1

    # قاعده طلایی: نسخه مصوب/شواهد/تسلط دست‌نخورده می‌مانند
    after = client.get(f"/api/v1/me/courses/{_SHARED['course_id']}/mastery",
                       headers=st_headers).json()
    assert {m["concept_id"]: m["status"] for m in before} == \
           {m["concept_id"]: m["status"] for m in after}
    st = client.get(f"/api/v1/integration/baseyar/status?course_id={_SHARED['course_id']}",
                    headers=prof_headers).json()
    assert st["sync_state"] == "REVIEW_REQUIRED"
    assert st["reference_version"] == "v1"  # تا تأیید استاد، نسخه قبلی ملاک است
    assert st["open_reviews"] >= 1

    # ---------- بررسی استاد + تأیید نسخه جدید + تطبیق دوره‌ای ----------
    r = client.post(f"/api/v1/integration/baseyar/reviews/{data['log_id']}/apply",
                    headers=prof_headers)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["status"] == "SYNCED"
    # در درس ایزوله نگاشتی ساخته نشده؛ پاک‌سازی صرفاً اطلاعاتی است
    assert res["cleared_mappings"] >= 0
    st = client.get(f"/api/v1/integration/baseyar/status?course_id={_SHARED['course_id']}",
                    headers=prof_headers).json()
    assert st["sync_state"] == "VALID" and st["reference_version"] == "v2"
    ap = client.post(f"/api/v1/syllabus-versions/{data['new_syllabus_version_id']}/approve",
                     headers=prof_headers)
    assert ap.status_code == 200, ap.text
    r2 = client.post("/api/v1/integration/baseyar/sync", headers=prof_headers,
                     json={"course_id": _SHARED["course_id"], "mode": "RECONCILE"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "UP_TO_DATE"
    _SHARED["stage"] = 2


def test_full_sync_lifecycle_without_silent_rewrite(client, ctx, prof_headers, st_headers):
    _run_flow(client, ctx, prof_headers, st_headers)


def test_sync_student_forbidden(client, ctx, st_headers, prof_headers):
    _run_flow(client, ctx, prof_headers, st_headers)
    r = client.post("/api/v1/integration/baseyar/sync", headers=st_headers,
                    json={"course_id": _SHARED["course_id"], "mode": "RECONCILE"})
    assert r.status_code == 403


def test_fresh_course_initial_pull(client, ctx, prof_headers):
    """درس بدون اتصال مرجع: INITIAL_PULL مستقیم پیوند می‌زند."""
    db = SessionLocal()
    try:
        prof = db.query(User).filter(User.username == "prof_test").first()
        course = Course(code="BYR999", title="درس پایه‌یار نو",
                        department="گروه تست", created_by=prof.id)
        db.add(course)
        db.commit()
        course_id = str(course.id)
    finally:
        db.close()
    r = client.post("/api/v1/integration/baseyar/sync", headers=prof_headers,
                    json={"course_id": course_id, "mode": "INITIAL_PULL"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SYNCED"
