# -*- coding: utf-8 -*-
"""
=====================================================================
Report Theme — پالت رنگ، فونت و ابزارهای مشترک گزارش‌ها
=====================================================================
تم گرافیکی مشترک هر چهار خروجی (HTML / PowerPoint / PDF / Word)
تا هویت بصری سامانه در همهٔ فرمت‌ها یکسان و حرفه‌ای بماند.
=====================================================================
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

# ------------------------------------------------------------------
# پالت رنگ سازمانی
# ------------------------------------------------------------------
PALETTE = {
    "primary": "#4F46E5",      # نیلی — رنگ اصلی برند
    "primary_dark": "#3730A3",
    "primary_light": "#EEF2FF",
    "accent": "#7C3AED",       # بنفش
    "cyan": "#06B6D4",
    "teal": "#0D9488",
    "amber": "#F59E0B",
    "rose": "#E11D48",
    "green": "#16A34A",
    "ink": "#1E293B",          # متن اصلی
    "muted": "#64748B",
    "line": "#E2E8F0",
    "bg": "#F8FAFC",
    "white": "#FFFFFF",
}

CHART_COLORS = [
    "#4F46E5", "#06B6D4", "#7C3AED", "#F59E0B",
    "#0D9488", "#E11D48", "#16A34A", "#6366F1",
]

FONT_DIR = Path(__file__).resolve().parent / "fonts"

FONT_REGULAR = FONT_DIR / "Vazirmatn-Regular.ttf"
FONT_BOLD = FONT_DIR / "Vazirmatn-Bold.ttf"


# ------------------------------------------------------------------
# تاریخ شمسی
# ------------------------------------------------------------------
_JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    """تبدیل میلادی به جلالی (الگوریتم استاندارد)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) \
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_today() -> str:
    """تاریخ امروز به شمسی، مثل: ۸ آبان ۱۴۰۴"""
    import datetime as _dt

    now = _dt.date.today()
    jy, jm, jd = to_jalali(now.year, now.month, now.day)
    return f"{jd} {_JALALI_MONTHS[jm - 1]} {jy}"


# ------------------------------------------------------------------
# فارسی‌سازی اعداد
# ------------------------------------------------------------------
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(value) -> str:
    """تبدیل ارقام لاتین به فارسی برای نمایش در خروجی‌ها."""
    return str(value).translate(_FA_DIGITS)


# ------------------------------------------------------------------
# فونت برای PDF (ReportLab)
# ------------------------------------------------------------------
def register_pdf_fonts():
    """
    ثبت فونت فارسی در ReportLab و بازگرداندن نام فونت‌ها.
    اگر فونت باندل‌شده نبود، به Helvetica برمی‌گردد.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        if FONT_REGULAR.exists():
            pdfmetrics.registerFont(TTFont("Vazir", str(FONT_REGULAR)))
        if FONT_BOLD.exists():
            pdfmetrics.registerFont(TTFont("Vazir-Bold", str(FONT_BOLD)))

        regular = "Vazir" if FONT_REGULAR.exists() else "Helvetica"
        bold = "Vazir-Bold" if FONT_BOLD.exists() else "Helvetica-Bold"
        return regular, bold
    except Exception:  # noqa: BLE001
        return "Helvetica", "Helvetica-Bold"


# ------------------------------------------------------------------
# فارسی‌سازی متن برای PDF (Reshape + Bidi)
# ------------------------------------------------------------------
def fa_text(text: str) -> str:
    """
    متن فارسی را برای رندر درست در ReportLab آماده می‌کند
    (اتصال حروف + ترتیب راست‌به‌چپ).
    """
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:  # noqa: BLE001
        return str(text)


def ensure_dir(path: Path) -> Path:
    os.makedirs(path, exist_ok=True)
    return path
