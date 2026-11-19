"""Jobهای تولید خروجی و فایل‌های خروجی (بخش ۴.۳ و ۱۳.۲).

هر Artifact با هش و نسخه قالب ثبت می‌شود تا بازتولید فایل ممکن باشد.
"""
import uuid
from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import GUID, Base, TimestampMixin, JSONB, uid_col

EXPORT_FORMATS = ("PDF", "PPTX", "HTML", "DOCX", "ZIP")


class ExportJob(TimestampMixin, Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    content_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_versions.id"), index=True)
    format: Mapped[str] = mapped_column(String(10))
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    job_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="QUEUED", index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class ExportArtifact(TimestampMixin, Base):
    __tablename__ = "export_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uid_col)
    export_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("export_jobs.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    template_version: Mapped[str] = mapped_column(String(24), default="v1")
