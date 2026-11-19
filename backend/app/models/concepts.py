"""گراف مفاهیم: گره‌ها، روابط، نگاشت موضوع‌ها و بدفهمی‌ها (بخش ۳.۲).

برای شروع، PostgreSQL کافی است؛ روابط در جدول و با محدودیت یکتا نگهداری می‌شوند
(قواعد داده بخش ۱۱ — همه داده‌ها در JSONB قرار نمی‌گیرند).
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, uid_col

CONCEPT_RELATION_TYPES = (
    "PREREQUISITE_OF",
    "PART_OF",
    "RELATED_TO",
    "APPLIED_IN",
    "MISCONCEPTION_OF",
)


class Concept(TimestampMixin, Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("course_id", "key", name="uq_concept_key"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    key: Mapped[str] = mapped_column(String(80), index=True)  # شناسه ثابت
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)  # نمونه‌ها (جداشده با ;;
    counter_examples: Mapped[str | None] = mapped_column(Text, nullable=True)  # ضدنمونه‌ها
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)  # DRAFT/APPROVED
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class ConceptRelation(TimestampMixin, Base):
    __tablename__ = "concept_relations"
    __table_args__ = (UniqueConstraint("from_concept_id", "to_concept_id", "rel_type", name="uq_concept_rel"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    from_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    to_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    rel_type: Mapped[str] = mapped_column(String(24), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class TopicConcept(TimestampMixin, Base):
    """نگاشت مفهوم به موضوع سرفصل."""

    __tablename__ = "topic_concepts"
    __table_args__ = (UniqueConstraint("topic_id", "concept_id", name="uq_topic_concept"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("syllabus_topics.id"), index=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)


class ConceptMisconception(TimestampMixin, Base):
    """بدفهمی رایج مرتبط با مفهوم — مبنای سؤال تشخیصی و توضیح جبرانی."""

    __tablename__ = "concept_misconceptions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
