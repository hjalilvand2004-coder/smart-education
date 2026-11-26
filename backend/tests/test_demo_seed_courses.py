"""تست سید دمو v3.13.0 — درس‌های واقعی طرح‌های درس پیوست + ارتقای دیتابیس قدیمی.

سید دمو سنگین است (خط تولید کامل)؛ پس در یک دیتابیس ایزوله فایل‌محور اجرا
می‌شود و SessionLocal ماژول با monkeypatch به همان دیتابیس هدایت می‌گردد.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.database import Base
from app.models.courses import Course, CourseOffering, Enrollment
from app.models.identity import User
from app.models.resources import Resource
from app.services import demo_seed


def _seed_on(tmp_db_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_db_path}")
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    monkeypatch.setattr(demo_seed, "SessionLocal", S)
    return S


def test_demo_seed_real_courses_and_upgrade(monkeypatch, tmp_path):
    S = _seed_on(tmp_path / "demo.db", monkeypatch)

    # ۱) سید روی دیتابیس خالی: چهار درس واقعی پیوست ساخته می‌شود
    demo_seed.seed_demo_data()
    db = S()
    codes = {c.code for c in db.query(Course).all()}
    assert {"DM-29", "IOT-22", "SWD-06", "ST-35"} <= codes
    dm = db.query(Course).filter(Course.code == "DM-29").first()
    assert dm is not None and "داده‌کاوی" in dm.title and dm.degree_level == "کارشناسی"
    assert db.query(Resource).filter(Resource.course_id == dm.id).count() == 3
    db.close()

    # ۲) شبیه‌سازی دیتابیس نسخهٔ قبل: درس ریاضی + زنجیرهٔ ارائه/منبع/ثبت‌نام
    db = S()
    old = Course(code="MATH101", title="ریاضیات عمومی ۱", department="گروه ریاضی",
                 degree_level="کارشناسی", credits=3, term="نیم‌سال جاری")
    db.add(old)
    db.flush()
    off = CourseOffering(course_id=old.id, term="نیم‌سال جاری")
    db.add(off)
    db.flush()
    st = db.query(User).filter(User.username == "student.sara").first()
    db.add(Enrollment(offering_id=off.id, student_id=st.id))
    old_res = Resource(course_id=old.id, title="جزوه حد و مشتق", kind="TEXTBOOK",
                       language="FA", license="مالکیت گروه")
    db.add(old_res)
    db.commit()
    old_id, off_id, res_id = old.id, off.id, old_res.id
    db.close()

    # ۳) سید مجدد: زنجیرهٔ ریاضی پاک و درس‌های جدید سر جایشان می‌مانند
    demo_seed.seed_demo_data()
    db = S()
    assert db.query(Course).filter(Course.code == "MATH101").count() == 0
    assert db.query(CourseOffering).filter(CourseOffering.id == off_id).count() == 0
    assert db.query(Resource).filter(Resource.id == res_id).count() == 0
    assert db.query(Course).filter(Course.code == "DM-29").count() == 1
    assert db.query(User).filter(User.username == "student.sara").count() == 1
    db.close()

    # ۴) اجرای سوم — idempotent، هیچ درس تکراری نمی‌سازد
    demo_seed.seed_demo_data()
    db = S()
    assert db.query(Course).filter(Course.code.in_(demo_seed.DEMO_COURSE_CODES)).count() == 4
    db.close()
