"""بانک سؤال (بخش ۵): سؤال با نسخه‌بندی، نگاشت مفاهیم/اهداف، روبرک و بدفهمی هدف.

- نسخه سؤال هنگام آزمون ثابت می‌ماند (AC-07): Response به QuestionVersion ارجاع دارد.
- سؤال تولیدی AI بدون تأیید وارد امتحان رسمی نمی‌شود (status gate).
- دشواری تخمینی و تجربی جدا نگهداری می‌شوند.
"""
import uuid
from sqlalchemy import ForeignKey, Float, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col

QUESTION_TYPES = (
    "MCQ", "MULTI_SELECT", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY",
    "NUMERIC", "CASE", "CODE", "ORDERING", "MATCHING",
)
QUESTION_STATUSES = ("AI_GENERATED", "DRAFT", "PENDING_REVIEW", "APPROVED", "REJECTED", "RETIRED")
QUESTION_USAGES = ("PRACTICE", "QUIZ", "OFFICIAL_EXAM")
COGNITIVE_LEVELS = ("REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE")
DIFFICULTIES = ("EASY", "MEDIUM", "HARD")


class Question(TimestampMixin, Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    type: Mapped[str] = mapped_column(String(16), index=True)
    difficulty_estimated: Mapped[str] = mapped_column(String(8), default="MEDIUM")
    difficulty_empirical: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1 (1-نرخ صحیح)
    cognitive_level: Mapped[str] = mapped_column(String(16), default="UNDERSTAND")
    usage: Mapped[str] = mapped_column(String(16), default="PRACTICE", index=True)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    misconception_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    source: Mapped[str | None] = mapped_column(String(24), nullable=True)  # AI / HUMAN
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # مشابهت با بانک
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # هشدارهای اعتبارسنجی/بررسی
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class QuestionVersion(TimestampMixin, Base):
    __tablename__ = "question_versions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    body: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # [{key,text}]
    answer: Mapped[dict] = mapped_column(JSONB, default=dict)  # پاسخ مرجع بر اساس نوع
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # [{criterion,max_score}]
    source_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    generated_by_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    is_current: Mapped[bool] = mapped_column(default=True)


class QuestionConcept(TimestampMixin, Base):
    __tablename__ = "question_concepts"
    __table_args__ = (UniqueConstraint("question_id", "concept_id", name="uq_question_concept"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    learning_objective_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
