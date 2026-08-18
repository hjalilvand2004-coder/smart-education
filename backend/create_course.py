from app.database import SessionLocal
from app.models import Course


db = SessionLocal()

try:
    course = db.get(Course, 1038)

    if course is None:
        course = Course(
            id=1038,
            title="درس نمونه",
            description="درس ایجادشده برای تست سامانه",
            is_active=True,
        )

        db.add(course)
        db.commit()
        db.refresh(course)

        print("درس با موفقیت ایجاد شد:")
        print(course.id, course.title)

    else:
        print("این درس قبلاً وجود دارد:")
        print(course.id, course.title)

finally:
    db.close()