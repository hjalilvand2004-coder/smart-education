"""نقش‌ها و کنترل دسترسی (بخش ۲ سند نیازمندی‌ها).

دسترسی مبتنی بر «دانشگاه/درس/گروه درسی/ثبت‌نام» است:
- نقش سراسری کاربر (مدیر آموزشی، کارشناس کیفیت، مدیر فنی ...)
- نقش درسی در course_roles (استاد، دستیار، مدیر گروه ...)
- ثبت‌نام دانشجو در enrollments

عملیات حساس باید همراه audit ثبت شود (در سرویس‌ها انجام می‌شود).
"""
from enum import Enum

from sqlalchemy.orm import Session

from app.core.errors import forbidden


class Role(str, Enum):
    STUDENT = "STUDENT"
    PROFESSOR = "PROFESSOR"
    ASSISTANT = "ASSISTANT"
    GROUP_ADMIN = "GROUP_ADMIN"
    EDUCATION_ADMIN = "EDUCATION_ADMIN"
    QUALITY_REVIEWER = "QUALITY_REVIEWER"
    TECH_ADMIN = "TECH_ADMIN"


COURSE_STAFF_ROLES = {Role.PROFESSOR, Role.ASSISTANT, Role.GROUP_ADMIN}
CONTENT_EDITOR_ROLES = {Role.PROFESSOR, Role.ASSISTANT}
SYLLABUS_APPROVER_ROLES = {Role.PROFESSOR, Role.GROUP_ADMIN, Role.EDUCATION_ADMIN}
REVIEWER_ROLES = {Role.PROFESSOR, Role.GROUP_ADMIN, Role.QUALITY_REVIEWER}
GLOBAL_ADMIN_ROLES = {Role.EDUCATION_ADMIN, Role.TECH_ADMIN}
QUESTION_APPROVER_ROLES = {Role.PROFESSOR, Role.QUALITY_REVIEWER}


def get_course_role(db: Session, user_id, course_id) -> Role | None:
    from app.models.identity import CourseRole

    row = (
        db.query(CourseRole)
        .filter(CourseRole.user_id == user_id, CourseRole.course_id == course_id)
        .first()
    )
    return Role(row.role) if row else None


def is_enrolled(db: Session, user_id, course_id) -> bool:
    from app.models.courses import CourseOffering, Enrollment

    row = (
        db.query(Enrollment)
        .join(CourseOffering, Enrollment.offering_id == CourseOffering.id)
        .filter(Enrollment.student_id == user_id, CourseOffering.course_id == course_id)
        .first()
    )
    return row is not None


def get_effective_role(db: Session, user, course_id) -> Role | None:
    """نقش مؤثر کاربر در درس؛ نقش‌های سراسری مدیریتی هم دیده می‌شوند."""
    if user.role in GLOBAL_ADMIN_ROLES:
        return Role(user.role)
    if user.role == Role.QUALITY_REVIEWER:
        return Role.QUALITY_REVIEWER
    return get_course_role(db, user.id, course_id)


def ensure_course_role(db: Session, user, course_id, roles: set[Role]) -> Role:
    role = get_course_role(db, user.id, course_id)
    if role not in roles:
        raise forbidden("نقش شما در این درس اجازه این عملیات را نمی‌دهد")
    return role


def ensure_staff(db: Session, user, course_id) -> Role:
    """استاد/دستیار/مدیر گروه همان درس یا مدیر سراسری."""
    if user.role in GLOBAL_ADMIN_ROLES or user.role == Role.QUALITY_REVIEWER:
        return Role(user.role)
    return ensure_course_role(db, user, course_id, COURSE_STAFF_ROLES)


def ensure_enrolled_or_staff(db: Session, user, course_id) -> None:
    if is_enrolled(db, user.id, course_id):
        return
    ensure_staff(db, user, course_id)


def ensure_can_publish(db: Session, user, course_id) -> None:
    """انتشار فقط توسط استاد درس (یا دستیار در صورت سیاست دانشگاه) — AC-05."""
    from app.core.config import get_settings

    role = get_course_role(db, user.id, course_id)
    if role == Role.PROFESSOR:
        return
    if role == Role.ASSISTANT and get_settings().ta_can_publish:
        return
    if user.role == Role.EDUCATION_ADMIN:
        return
    raise forbidden("انتشار محتوا فقط توسط استاد درس و طبق سیاست دانشگاه مجاز است")


def ensure_global_role(user, roles: set[Role]) -> Role:
    if Role(user.role) not in roles:
        raise forbidden("این عملیات نیازمند نقش مدیریتی است")
    return Role(user.role)
