"""منابع آموزشی و قطعه‌های RAG (بخش ۱۴.۱).

- منابع امتحان فعال / کلید سؤال با contains_exam_material علامت‌گذاری می‌شوند
  و از مخزن بازیابی گفتگو (RAG) کنار گذاشته می‌شوند (AC-09).
- قطعه‌بندی RAG از قطعه‌بندی آموزشی تدریس جدا است.
- MVP: بردار embedding به‌صورت JSON ذخیره می‌شود؛ در استقرار نهایی ستون
  pgvector + ایندکس HNSW جایگزین می‌شود (migration آماده است).
"""
import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col


class Resource(TimestampMixin, Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(24), default="OTHER")  # TEXTBOOK/LECTURE_NOTES/VIDEO/ARTICLE/EXAM_KEY/SLIDES/OTHER
    authors: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="FA")
    license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contains_exam_material: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="AVAILABLE", index=True)
    ai_usable: Mapped[bool] = mapped_column(Boolean, default=True)  # مجوز استفاده در AI
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class ResourceChunk(TimestampMixin, Base):
    __tablename__ = "resource_chunks"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(300), nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # pgvector در استقرار نهایی
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ResourcePermission(TimestampMixin, Base):
    """مجوز استفاده منبع در یک درس/نقش — مبنای فیلتر مجوز پیش از بازیابی."""

    __tablename__ = "resource_permissions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"), index=True)
    allowed_roles: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # null = همه نقش‌های درس
