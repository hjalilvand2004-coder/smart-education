"""مدل‌های تجربه «مسیر یادگیری» و یکپارچگی مرجع (نسخه ۳.۱).

اصل معماری: داده مرجع (درس/سرفصل) متعلق به پایه‌یار۳۶۰ است؛ در این سامانه
فقط «رونوشت همگام‌شده» نگهداری می‌شود و هر تغییر مرجع، بدون بازنویسی بی‌صدای
گراف مفاهیم و شواهد دانشجو، به‌صورت گزارش تغییر برای بررسی استاد ثبت می‌گردد.

قابلیت‌های متمایز این نسخه:
- «اینجا گیر کردم» (StuckMark) → ورود استاد هوشمند از همان نقطه محتوا
- کلینیک خطا (ErrorNotebookEntry) → دفتر خطای آموزشی با برچسب قابل اصلاح
- «به من یاد بده» (TeachBackSubmission) → دانشجو در نقش مدرس با روبرک AI
- جلسه یادگیری با زمان انتخابی (LearningSession) → ۵/۱۵/۳۰ دقیقه با توقف/ادامه
- آمادگی آزمون صادقانه (ExamPrepPlan) → اولویت‌بندی با نمایش عدم‌قطعیت
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col

STUCK_KINDS = (
    "NOT_UNDERSTOOD",       # معنی عبارت را نمی‌فهمم
    "CONNECTION_UNCLEAR",   # ارتباطش با مطلب قبلی روشن نیست
    "STEP_UNCLEAR",         # نمی‌دانم چرا این مرحله انجام شد
    "KNOWS_BUT_CANT_SOLVE", # مفهوم را می‌دانم اما نمی‌توانم حل کنم
)
ERROR_STATUSES = ("OPEN", "ATTRIBUTED", "RESOLVED")
SESSION_STATES = ("ACTIVE", "PAUSED", "DONE")
SYNC_DIRECTIONS = ("INITIAL_PULL", "CHANGE_EVENT", "RECONCILE")
SYNC_STATUSES = ("SYNCED", "UP_TO_DATE", "REVIEW_REQUIRED", "FAILED")


class ReferenceSyncLog(TimestampMixin, Base):
    """گزارش هر همگام‌سازی با پایه‌یار۳۶۰ — مرجع حقیقت درس/سرفصل خارج است.

    سامانه هرگز نسخه مصوب سرفصل و گراف مفاهیم را بی‌صدا بازنویسی نمی‌کند؛
    تغییر مرجع → نسخه پیش‌نویس جدید + فهرست نگاشت‌های نیازمند بررسی استاد.
    """

    __tablename__ = "reference_sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    direction: Mapped[str] = mapped_column(String(16), index=True)   # INITIAL_PULL/CHANGE_EVENT/RECONCILE
    status: Mapped[str] = mapped_column(String(16), index=True)      # SYNCED/UP_TO_DATE/REVIEW_REQUIRED/FAILED
    reference_system: Mapped[str] = mapped_column(String(32), default="baseyar360")
    reference_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_syllabus_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # گزارش تغییر به فارسی
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StuckMark(TimestampMixin, Base):
    """«اینجا گیر کردم» — علامت‌گذاری نقطه گیر در محتوا با نوع مشکل."""

    __tablename__ = "stuck_marks"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    content_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    block_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_anchor: Mapped[str | None] = mapped_column(Text, nullable=True)  # عبارت علامت‌گذاری‌شده
    kind: Mapped[str] = mapped_column(String(32), index=True)  # یکی از STUCK_KINDS
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    tutor_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class ErrorNotebookEntry(TimestampMixin, Base):
    """دفتر خطای آموزشی (کلینیک خطا) — تفسیر خطا «فرضیه» است و دانشجو می‌تواند
    برچسب را اصلاح/رد کند؛ بازگشت خطا در تلاش بعدی شمرده می‌شود."""

    __tablename__ = "error_notebook_entries"
    __table_args__ = (UniqueConstraint("learner_id", "course_id", "concept_id", "pattern_key",
                                       name="uq_error_note"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    pattern_key: Mapped[str] = mapped_column(String(64), index=True)  # SIGN_ERROR/TRANSPOSE/UNIT/CONCEPT_GAP/...
    title: Mapped[str] = mapped_column(String(200))
    evidence: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # شواهد: response_id ها
    suggested_practice: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)
    student_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TeachBackSubmission(TimestampMixin, Base):
    """«به من یاد بده» — دانشجو مفهوم را با کلام خود توضیح می‌دهد؛ سامانه با
    روبرک (دقت تعریف، پوشش روابط، کیفیت مثال، ابهام‌ها) بازخورد می‌دهد.
    خروجی بازخورد یادگیری است، نه نمره رسمی."""

    __tablename__ = "teach_back_submissions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    modality: Mapped[str] = mapped_column(String(8), default="TEXT")  # TEXT/AUDIO
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rubric: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    follow_up_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="REVIEWED", index=True)


class LearningSession(TimestampMixin, Base):
    """جلسه یادگیری با زمان انتخابی (۵/۱۵/۳۰ دقیقه) — ترکیب مرور/مثال/تمرین
    متناسب با زمان؛ قابل توقف و ادامه."""

    __tablename__ = "learning_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    minutes: Mapped[int] = mapped_column(Integer)  # 5/15/30
    composition: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # گام‌ها
    state: Mapped[str] = mapped_column(String(12), default="ACTIVE", index=True)
    progress: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # گام جاری/انجام‌شده‌ها
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExamPrepPlan(TimestampMixin, Base):
    """برنامه آمادگی آزمون با اولویت‌بندی صادقانه — پوشش یادگیری و عدم‌قطعیت
    نمایش داده می‌شود؛ هیچ وعده نمره/قبولی وجود ندارد."""

    __tablename__ = "exam_prep_plans"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    exam_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO date
    available_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", index=True)


MASTERDATA_MODES = ("FULL", "INCREMENTAL")
MASTERDATA_STATUSES = ("OK", "PARTIAL", "FAILED")
# وضعیت‌های اتصال به سرویس مرجع — هر وضعیت پیام راهنمای قابل‌اقدام دارد
PAYEHYAR_PROBE_STATUSES = ("OK", "NEEDS_API_KEY", "INVALID_API_KEY", "NEEDS_ROLE",
                           "UNREACHABLE", "NOT_CONFIGURED")


class MasterdataSyncLog(TimestampMixin, Base):
    """گزارش هر اجرای همگام‌سازی کاتالوگ (دروس + سرفصل‌ها) از پایه‌یار۳۶۰.

    برخلاف ReferenceSyncLog (که گزارش هر درس است) این جدول تاریخچه اجراهای
    کل کاتالوگ را نگه می‌دارد: آمار ایجاد/به‌روزرسانی، نسخه‌های پیش‌نویس
    ساخته‌شده، هشدارهای نرمال‌سازی، خطای احراز هویت قابل‌اقدام و کرسر فید تغییرات.
    """

    __tablename__ = "masterdata_sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    mode: Mapped[str] = mapped_column(String(16), index=True)          # FULL / INCREMENTAL
    status: Mapped[str] = mapped_column(String(16), index=True)        # OK / PARTIAL / FAILED
    remote_version: Mapped[str | None] = mapped_column(String(32), nullable=True)  # نسخه سرویس مرجع
    courses_created: Mapped[int] = mapped_column(Integer, default=0)
    courses_updated: Mapped[int] = mapped_column(Integer, default=0)
    up_to_date: Mapped[int] = mapped_column(Integer, default=0)
    syllabus_drafts_created: Mapped[int] = mapped_column(Integer, default=0)
    review_required: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # فهرست رکوردهای نگاشت‌نشدنی
    cursor_before: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cursor_after: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class PayehyarRecord(TimestampMixin, Base):
    """رونوشت عمومی رکوردهای masterdata پایه‌یار۳۶۰ (دامنه‌های بدون مدل بومی).

    دامنه‌های درس/سرفصل (unique-courses / split-courses / course-syllabi) در
    مدل‌های بومی (Course / SyllabusVersion) ذخیره می‌شوند؛ دامنه‌های گسترش‌یافته
    سند فنی (professors / classrooms / academic-groups / reference-sets) اینجا
    «یکتا و تفکیکی» نگه داشته می‌شوند: UNIQUE(domain, external_id) و تشخیص
    تغییر واقعی با content_hash (بدون تکرار و بدون ادغام رکوردها).
    """

    __tablename__ = "payehyar_masterdata_records"
    __table_args__ = (UniqueConstraint("domain", "external_id",
                                       name="uq_payehyar_domain_extid"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    domain: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    code: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="payehyar360")
    source_route: Mapped[str | None] = mapped_column(String(32), nullable=True)  # services/admin
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PayehyarEventInbox(TimestampMixin, Base):
    """صندوق ورودی رویدادهای RabbitMQ پایه‌یار۳۶۰ (سند فنی: smart_learning_event_inbox).

    کلید اصلی event_id است؛ پردازش idempotent: رویداد تکراری بدون اثر دومین
    نادیده گرفته می‌شود و شکست پردازش با وضعیت FAILED + پیام خطا ثبت می‌گردد
    (پیام به DLQ می‌رود و پس از رفع می‌تواند دوباره اعمال شود).
    """

    __tablename__ = "smart_learning_event_inbox"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    routing_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)  # PENDING/PROCESSED/FAILED
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class DarsyarPreference(TimestampMixin, Base):
    """کش مطلوبیات درسی/زمانی استاد واکشی‌شده از درس‌یار۳۶۰ (darsyar360.ir).

    منبع داده درس‌یار است؛ این جدول فقط «رونوشت همگام‌شده» را برای نمایش سریع
    و کار در حالت آفلاین نگه می‌دارد (الگوی مشابه PayehyarRecord). source مشخص
    می‌کند داده زنده است یا نمونهٔ توسعه وقتی سرویس در دسترس نیست.
    """

    __tablename__ = "darsyar_preferences"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=uid_col)
    professor_ext_id: Mapped[str] = mapped_column(String(120), index=True)
    professor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="demo")  # live / demo
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
