"""تنظیمات تست: پایگاه داده SQLite موقت، سیدینگ حداقلی و کلاینت API."""
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP = Path(tempfile.mkdtemp(prefix="s360_test_"))
os.environ["S360_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["S360_STORAGE_DIR"] = str(_TMP / "storage")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401
from app.core.permissions import Role  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.identity import CourseRole, User  # noqa: E402
from app.models.courses import Course, CourseOffering, Enrollment  # noqa: E402
from app.models.resources import Resource, ResourcePermission  # noqa: E402
from app.services.syllabus_service import (approve_version, import_from_source)  # noqa: E402
from app.services import concept_service, rag  # noqa: E402


@pytest.fixture(scope="session")
def client():
    Base.metadata.create_all(engine)
    with TestClient(__import__("app.main", fromlist=["app"]).app) as c:
        yield c


def _mk_user(db, username, full_name, role):
    u = User(username=username, full_name=full_name,
             password_hash=hash_password("Pass1234!"), role=role)
    db.add(u)
    db.flush()
    return u


@pytest.fixture(scope="session")
def ctx(client):
    """سیدینگ پایه: کاربران، درس، سرفصل مصوب، مفاهیم، منابع."""
    db = SessionLocal()
    prof = _mk_user(db, "prof_test", "استاد تست", Role.PROFESSOR.value)
    ta = _mk_user(db, "ta_test", "دستیار تست", Role.STUDENT.value)
    st = _mk_user(db, "st_test", "دانشجوی تست", Role.STUDENT.value)
    outsider = _mk_user(db, "out_test", "دانشجوی خارج", Role.STUDENT.value)
    admin = _mk_user(db, "edu_test", "مدیر آموزشی", Role.EDUCATION_ADMIN.value)
    tech = _mk_user(db, "tech_test", "مدیر فنی", Role.TECH_ADMIN.value)

    course = Course(code="TST101", title="درس تست", department="گروه تست",
                    credits=2, created_by=prof.id)
    db.add(course)
    db.flush()
    offering = CourseOffering(course_id=course.id, term="ترم تست", professor_id=prof.id)
    db.add(offering)
    db.flush()
    db.add(CourseRole(course_id=course.id, user_id=prof.id, role=Role.PROFESSOR.value))
    db.add(CourseRole(course_id=course.id, user_id=ta.id, role=Role.ASSISTANT.value))
    db.add(Enrollment(offering_id=offering.id, student_id=st.id))

    text = "فصل ۱: مبانی\n1.1 مفهوم پایه\n1.2 مفهوم پیشرفته\n\nفصل ۲: کاربرد\n2.1 حل مسئله\n\nاهداف یادگیری:\n- تفسیر مفهوم پایه\n- حل مسئله با مفهوم پیشرفته"
    sv = import_from_source(db, course, prof.id, text=text, source_kind="TEXT")
    approve_version(db, sv, prof)

    t_base = db.query(__import__("app.models.syllabus", fromlist=["SyllabusTopic"]).SyllabusTopic).filter(
        __import__("app.models.syllabus", fromlist=["SyllabusTopic"]).SyllabusTopic.title.like("1.1%")).first()
    t_adv = db.query(__import__("app.models.syllabus", fromlist=["SyllabusTopic"]).SyllabusTopic).filter(
        __import__("app.models.syllabus", fromlist=["SyllabusTopic"]).SyllabusTopic.title.like("1.2%")).first()
    c_base = concept_service.create_concept(
        db, course.id, prof, "base_concept", "مفهوم پایه",
        "تعریف دقیق مفهوم پایه برای تست", topic_ids=[t_base.id], status="APPROVED",
        misconceptions=[{"title": "بدفهمی رایج پایه"}])
    c_adv = concept_service.create_concept(
        db, course.id, prof, "adv_concept", "مفهوم پیشرفته",
        "تعریف دقیق مفهوم پیشرفته برای تست", topic_ids=[t_adv.id],
        prerequisite_ids=[c_base.id], status="APPROVED")

    res = Resource(course_id=course.id, title="کتاب تست", kind="TEXTBOOK",
                   language="FA", uploaded_by=prof.id, contains_exam_material=False)
    db.add(res)
    db.flush()
    rag.index_resource_text(db, res,
                            "مفهوم پایه عبارت است از تعریف دقیق پایه. مفهوم پیشرفته بر پایه آن بنا می‌شود "
                            "و در حل مسئله به‌کار می‌رود.")
    db.add(ResourcePermission(resource_id=res.id, course_id=course.id))
    exam_res = Resource(course_id=course.id, title="کلید امتحان تست", kind="EXAM_KEY",
                        language="FA", uploaded_by=prof.id, contains_exam_material=True)
    db.add(exam_res)
    db.flush()
    rag.index_resource_text(db, exam_res, "کلید امتحان: پاسخ سؤال ۱ برابر ۴۲ است.")
    db.add(ResourcePermission(resource_id=exam_res.id, course_id=course.id))
    db.commit()

    data = {
        "prof_id": str(prof.id), "ta_id": str(ta.id), "st_id": str(st.id),
        "outsider_id": str(outsider.id), "admin_id": str(admin.id), "tech_id": str(tech.id),
        "course_id": str(course.id), "offering_id": str(offering.id),
        "syllabus_version_id": str(sv.id), "base_concept": str(c_base.id),
        "adv_concept": str(c_adv.id), "resource_id": str(res.id), "exam_resource_id": str(exam_res.id),
    }
    db.close()
    return data


def login(client, username):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "Pass1234!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def prof_headers(ctx, client):
    return login(client, "prof_test")


@pytest.fixture(scope="session")
def bank(ctx, client, prof_headers):
    """بانک سؤال تأییدشده (سشن‌محور) — مستقل از ترتیب الفبایی فایل‌های تست."""
    r = client.post("/api/v1/question-generation-jobs", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "concept_ids": [ctx["base_concept"], ctx["adv_concept"]],
        "types": ["MCQ", "TRUE_FALSE", "SHORT_ANSWER", "NUMERIC", "ESSAY"],
        "count": 10,
    }).json()
    for _ in range(40):
        job = client.get(f"/api/v1/jobs/{r['job_id']}", headers=prof_headers).json()
        if job["status"] in ("SUCCEEDED", "FAILED"):
            break
        import time

        time.sleep(0.2)
    assert job["status"] == "SUCCEEDED", job.get("error")
    qids = job["result"]["question_ids"]
    for qid in qids:
        client.post(f"/api/v1/questions/{qid}/reviews", headers=prof_headers,
                    json={"decision": "APPROVE"})
    return qids


@pytest.fixture(scope="session")
def ta_headers(ctx, client):
    return login(client, "ta_test")


@pytest.fixture(scope="session")
def st_headers(ctx, client):
    return login(client, "st_test")


@pytest.fixture(scope="session")
def admin_headers(ctx, client):
    return login(client, "edu_test")


@pytest.fixture(scope="session")
def tech_headers(ctx, client):
    return login(client, "tech_test")
