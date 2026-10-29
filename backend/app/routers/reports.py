# -*- coding: utf-8 -*-
"""
=====================================================================
Reports Router — خروجی‌های گرافیکی HTML / PowerPoint / PDF / Word
=====================================================================
    GET /api/reports/preview          → دادهٔ خام گزارش (JSON)
    GET /api/reports/export/{format}  → دانلود گزارش در فرمت خواسته‌شده

format ∈ html | pptx | pdf | docx
=====================================================================
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..config import EXPORTS_DIR
from ..database import get_db
from ..reports.builder import build_report, collect_data
from ..reports.theme import ensure_dir

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)

VALID_FORMATS = {"html", "pptx", "pdf", "docx"}

CONTENT_TYPES = {
    "html": "text/html; charset=utf-8",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/preview")
def reports_preview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """دادهٔ جامع گزارش را (بدون ساخت فایل) برمی‌گرداند."""
    return collect_data(db)


@router.get("/export/{fmt}")
def reports_export(fmt: str, db: Session = Depends(get_db)) -> Response:
    """
    ساخت و دانلود گزارش در فرمت خواسته‌شده.
    فایل به‌صورت همزمان در پوشهٔ exports/ نیز نگه‌داری می‌شود.
    """
    fmt = (fmt or "").strip().lower().lstrip(".")
    if fmt not in VALID_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"فرمت نامعتبر است. فرمت‌های مجاز: {', '.join(sorted(VALID_FORMATS))}",
        )

    try:
        content, filename, content_type = build_report(db, fmt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"خطا در تولید گزارش: {exc.__class__.__name__} — {exc}",
        )

    # نگه‌داری نسخهٔ محلی (اختیاری و بدون توقف پاسخ)
    try:
        out_dir = ensure_dir(EXPORTS_DIR)
        with open(out_dir / filename, "wb") as fh:
            fh.write(content)
    except Exception:  # noqa: BLE001
        pass

    disposition = (
        "inline" if fmt == "html" else "attachment"
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
