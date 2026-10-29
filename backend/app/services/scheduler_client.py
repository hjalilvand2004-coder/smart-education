# -*- coding: utf-8 -*-
"""
=====================================================================
Scheduler Service Client — کلاینت سرویس برنامه‌ریزی درسی
=====================================================================
لیست درس‌ها از سرویس بیرونی «سامانه هوشمند برنامه‌ریزی درسی»
(مخزن university-scheduler) خوانده می‌شود.

نقاط اتصال (Endpoints):
    GET /api/courses/unique   → دروس یکتا (id, code, title, ...)
    GET /api/courses/offered  → دروس ارائه‌شده ترم جاری
    GET /health               → بررسی سلامت سرویس

همه متدها «بدون پرتاب استثنا» طراحی شده‌اند تا اگر سرویس بیرونی
در دسترس نبود، سامانه همچنان کار کند (Graceful Degradation).
=====================================================================
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from ..config import SCHEDULER_BASE_URL, SCHEDULER_TIMEOUT

logger = logging.getLogger(__name__)


class SchedulerClient:
    """کلاینت HTTP برای تبادل سرویس با university-scheduler."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or SCHEDULER_BASE_URL).rstrip("/")

    # --------------------------------------------------------------
    # سلامت سرویس
    # --------------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        """
        وضعیت سرویس بیرونی را برمی‌گرداند.

        خروجی:
            {"available": bool, "base_url": str, "version": str|None,
             "detail": str}
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/health",
                timeout=SCHEDULER_TIMEOUT,
            )
            if resp.status_code == 200:
                data = {}
                try:
                    data = resp.json()
                except Exception:
                    pass
                return {
                    "available": True,
                    "base_url": self.base_url,
                    "version": data.get("version"),
                    "detail": "سرویس برنامه‌ریزی درسی در دسترس است.",
                }
            return {
                "available": False,
                "base_url": self.base_url,
                "version": None,
                "detail": f"پاسخ غیرمنتظره با کد {resp.status_code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "available": False,
                "base_url": self.base_url,
                "version": None,
                "detail": f"سرویس در دسترس نیست: {exc.__class__.__name__}",
            }

    # --------------------------------------------------------------
    # خواندن لیست درس‌ها
    # --------------------------------------------------------------
    def fetch_unique_courses(self) -> Optional[List[Dict[str, Any]]]:
        """دروس یکتا را از سرویس بیرونی می‌خواند؛ خطا → None."""
        return self._get_json("/api/courses/unique")

    def fetch_offered_courses(self) -> Optional[List[Dict[str, Any]]]:
        """دروس ارائه‌شده را از سرویس بیرونی می‌خواند؛ خطا → None."""
        return self._get_json("/api/courses/offered")

    def _get_json(self, path: str) -> Optional[List[Dict[str, Any]]]:
        try:
            resp = httpx.get(
                f"{self.base_url}{path}",
                timeout=SCHEDULER_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.warning(
                    "Scheduler %s → HTTP %s", path, resp.status_code
                )
                return None
            data = resp.json()
            return data if isinstance(data, list) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Scheduler %s failed: %s", path, exc)
            return None

    # --------------------------------------------------------------
    # نرمال‌سازی داده بیرونی → ساختار درون‌سیستمی
    # --------------------------------------------------------------
    @staticmethod
    def normalize_course(raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        رکورد درس سرویس بیرونی را به ساختار استاندارد سامانه تبدیل
        می‌کند. فیلدهای اختیاری با مقدار پیش‌فرض پر می‌شوند.
        """
        title = (
            raw.get("title")
            or raw.get("course_title")
            or raw.get("name")
            or "درس بدون عنوان"
        )
        code = str(
            raw.get("code") or raw.get("course_code") or raw.get("id") or ""
        )
        credits = raw.get("credits") or raw.get("units") or 3
        description_parts = []
        if code:
            description_parts.append(f"کد درس (از سرویس برنامه‌ریزی): {code}")
        if raw.get("group"):
            description_parts.append(f"گروه: {raw['group']}")
        if raw.get("estimated_capacity"):
            description_parts.append(f"ظرفیت تخمینی: {raw['estimated_capacity']}")
        if raw.get("course_type"):
            description_parts.append(f"نوع: {raw['course_type']}")

        return {
            "external_id": raw.get("id"),
            "code": code,
            "title": str(title).strip(),
            "credits": int(credits) if str(credits).isdigit() else 3,
            "is_active": bool(
                raw.get("active", raw.get("status", "active") == "active")
            ),
            "description": " | ".join(description_parts) or None,
            "source": "university-scheduler",
        }
