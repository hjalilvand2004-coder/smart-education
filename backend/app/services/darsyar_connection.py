"""تنظیمات و تست اتصال به درس‌یار۳۶۰ (darsyar360.ir) — الگوی payehyar_connection.

اولویت منبع تنظیمات: دیتابیس (ذخیرهٔ کاربر از صفحهٔ درس‌یار۳۶۰) > متغیر محیطی
S360_DARSYAR_* > پیش‌فرض کد. مالک دادهٔ مطلوبیات سامانهٔ درس‌یار است؛ این سامانه
فقط «رونوشت همگام‌شده» را نگه می‌دارد و کلید/آدرس همین‌جا پیکربندی می‌شود.

تست اتصال گام‌به‌گام (بدون مستند رسمی، defensive):
  گام ۱ دسترسی شبکه: GET {base}/
  گام ۲ احراز هویت: GET مسیر مرجع مطلوبیات با هدر X-API-Key (پاسخ ۲۰۰/۴۰۱/۴۰۳/۴۰۴)
"""
import time

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.integrations import DarsyarConnection

_PROBE_PATH = "/api/v1/services/instructor-preferences/probe"


def _row(db: Session) -> DarsyarConnection | None:
    return db.get(DarsyarConnection, 1)


def effective_connection(db: Session) -> dict:
    """تنظیمات مؤثر با منبع هر مقدار — برای نمایش و ساخت کلاینت."""
    s = get_settings()
    row = _row(db)
    if row and row.base_url.strip():
        base_url, base_src = row.base_url.strip().rstrip("/"), "DB"
    else:
        base_url, base_src = s.darsyar_base_url or "https://darsyar360.ir", "DEFAULT"
    if row and row.api_key.strip():
        api_key, key_src = row.api_key.strip(), "DB"
    elif s.darsyar_api_key:
        api_key, key_src = s.darsyar_api_key, "ENV"
    else:
        api_key, key_src = "", "NONE"
    if row and row.timeout_seconds:
        timeout, timeout_src = int(row.timeout_seconds), "DB"
    else:
        timeout, timeout_src = int(s.darsyar_timeout_seconds), "DEFAULT"
    return {"base_url": base_url, "api_key": api_key, "timeout_seconds": timeout,
            "base_url_source": base_src, "key_source": key_src,
            "timeout_source": timeout_src,
            "updated_at": (row.updated_at if row else None)}


def save_connection(db: Session, base_url: str | None = None,
                    api_key: str | None = None,
                    timeout_seconds: int | None = None) -> dict:
    """ذخیره (upsert) تنظیمات — None یعنی بدون تغییر، "" یعنی پاک‌کردن مقدار."""
    row = _row(db)
    if row is None:
        row = DarsyarConnection(id=1)
        db.add(row)
    if base_url is not None:
        base_url = base_url.strip()
        if base_url and not base_url.lower().startswith(("http://", "https://")):
            raise ValueError("آدرس سرویس باید با http:// یا https:// شروع شود")
        row.base_url = base_url[:255]
    if api_key is not None:
        row.api_key = api_key.strip()[:255]
    if timeout_seconds is not None:
        timeout_seconds = int(timeout_seconds)
        if not 1 <= timeout_seconds <= 60:
            raise ValueError("تایم‌اوت باید بین ۱ تا ۶۰ ثانیه باشد")
        row.timeout_seconds = timeout_seconds
    db.commit()
    return connection_view(db)


def connection_view(db: Session) -> dict:
    """نمای ماسک‌شدهٔ تنظیمات — کلید هرگز کامل برنمی‌گردد."""
    eff = effective_connection(db)
    key = eff["api_key"]
    masked = (f"{key[:8]}…{key[-4:]}" if len(key) > 12 else ("●●●" if key else None))
    return {"base_url": eff["base_url"], "api_key_masked": masked,
            "has_key": bool(key), "key_source": eff["key_source"],
            "base_url_source": eff["base_url_source"],
            "timeout_seconds": eff["timeout_seconds"],
            "timeout_source": eff["timeout_source"],
            "updated_at": eff["updated_at"].isoformat() if eff["updated_at"] else None,
            "data_owner": "درس‌یار۳۶۰ (darsyar360.ir)"}


def _open_http(transport: httpx.BaseTransport | None, timeout: float) -> httpx.Client:
    """کارخانهٔ httpx — نقطهٔ تزریق transport جعلی در تست‌ها."""
    return httpx.Client(timeout=timeout, transport=transport, follow_redirects=True)


def test_connection(db: Session, base_url: str | None = None,
                    api_key: str | None = None,
                    transport: httpx.BaseTransport | None = None,
                    timeout: float = 10.0) -> dict:
    """تست گام‌به‌گام اتصال — override فقط برای «تست پیش از ذخیره».

    گام ۱ دسترسی شبکه: پاسخ ریشهٔ سرویس
    گام ۲ احراز هویت: مسیر مرجع مطلوبیات با X-API-Key (۴۰۱/۴۰۳ کلید بد؛
         ۴۰۴ یعنی سرویس بالا است اما مسیر probe ساخته نشده — قابل‌قبول با هشدار)"""
    eff = effective_connection(db)
    base = (base_url if base_url is not None else eff["base_url"]).strip().rstrip("/")
    key = (api_key if api_key is not None else eff["api_key"]).strip()
    steps: list[dict] = []
    net_hint = ("سرویس درس‌یار از این دستگاه در دسترس نیست — آدرس را بررسی کنید؛ "
                "اگر اپ روی دستگاه دیگری اجرا می‌شود، از همان دستگاه دسترسی "
                "(ping/telnet) را بررسی کنید.")

    # ---------- گام ۱: دسترسی ----------
    t0 = time.perf_counter()
    try:
        with _open_http(transport, timeout) as hc:
            r = hc.get(base + "/")
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code < 500:
            steps.append({"name": "دسترسی به سرویس", "ok": True,
                          "detail": f"پاسخ HTTP {r.status_code} در {ms} میلی‌ثانیه از ریشهٔ سرویس",
                          "hint": None})
        else:
            steps.append({"name": "دسترسی به سرویس", "ok": False,
                          "detail": f"پاسخ HTTP {r.status_code} از ریشهٔ سرویس",
                          "hint": "سرویس مقصد پاسخ خطای سرور می‌دهد — وضعیت درس‌یار۳۶۰ را بررسی کنید."})
    except Exception as exc:  # noqa: BLE001
        steps.append({"name": "دسترسی به سرویس", "ok": False,
                      "detail": f"{type(exc).__name__}: {str(exc)[:180]}",
                      "hint": net_hint})
        return {"ok": False, "steps": steps,
                "summary": "اتصال به درس‌یار۳۶۰ برقرار نشد — ابتدا گام «دسترسی به سرویس» را رفع کنید."}

    # ---------- گام ۲: احراز هویت ----------
    if not key:
        steps.append({"name": "احراز هویت کلید API", "ok": False,
                      "detail": "هیچ کلیدی برای ارسال در هدر X-API-Key وجود ندارد",
                      "hint": "کلید سامانهٔ مصرف‌کننده را از مدیر درس‌یار۳۶۰ بردارید "
                              "و در کارت «تنظیمات اتصال» ذخیره کنید؛ تا آن زمان "
                              "مطلوبیات در «حالت نمونهٔ قطعی» نمایش داده می‌شود."})
        return {"ok": False, "steps": steps,
                "summary": "سرویس در دسترس است اما کلید API تنظیم نشده — کلید را "
                           "ذخیره کنید یا ادامه را با نمونهٔ قطعی پیش ببرید."}
    try:
        with _open_http(transport, timeout) as hc:
            r2 = hc.get(base + _PROBE_PATH, headers={"X-API-Key": key, "Accept": "application/json"})
        if r2.status_code == 200:
            steps.append({"name": "احراز هویت کلید API", "ok": True,
                          "detail": "کلید با هدر X-API-Key پذیرفته شد",
                          "hint": None})
            steps.append({"name": "مسیر دادهٔ مطلوبیات", "ok": True,
                          "detail": "endpoint مرجع مطلوبیات پاسخ ۲۰۰ داد — مسیر داده سالم است",
                          "hint": None})
            return {"ok": True, "steps": steps,
                    "summary": "اتصال به درس‌یار۳۶۰ کامل است ✓ — می‌توانید مطلوبیات را همگام‌سازی کنید."}
        if r2.status_code in (401, 403):
            steps.append({"name": "احراز هویت کلید API", "ok": False,
                          "detail": f"HTTP {r2.status_code} — {r2.text[:150]}",
                          "hint": "کلید نادرست است، غیرفعال شده یا دامنهٔ دسترسی ندارد — "
                                  "وضعیت کلید در درس‌یار۳۶۰ را بررسی کنید."})
        elif r2.status_code == 404:
            # سرویس بالاست ولی مسیر probe وجود ندارد — احراز هویت با کلید معتبر
            # محتمل است؛ به‌عنوان «قابل‌قبول با هشدار» گزارش می‌شود نه شکست قطعی.
            steps.append({"name": "احراز هویت کلید API", "ok": True,
                          "detail": "HTTP 404 برای مسیر probe — سرویس بالا است اما "
                                    "مسیر آزمایشی مطلوبیات ساخته نشده",
                          "hint": "با کلید ذخیره‌شده «همگام‌سازی» را امتحان کنید؛ اگر "
                                  "پاسخ نمونه دیدید یعنی کلید/مسیر واقعی برقرار نشده."})
            return {"ok": True, "steps": steps,
                    "summary": "سرویس درس‌یار در دسترس است ✓ (مسیر دقیق مطلوبیات آزمایش نشد — "
                               "همگام‌سازی واقعی را امتحان کنید)."}
        else:
            steps.append({"name": "احراز هویت کلید API", "ok": False,
                          "detail": f"HTTP {r2.status_code} — {r2.text[:150]}",
                          "hint": "خطای غیرمنتظرهٔ سرویس — لاگ درس‌یار را بررسی کنید."})
    except Exception as exc:  # noqa: BLE001
        steps.append({"name": "احراز هویت کلید API", "ok": False,
                      "detail": f"{type(exc).__name__}: {str(exc)[:180]}",
                      "hint": net_hint})
    return {"ok": False, "steps": steps,
            "summary": "دسترسی شبکه برقرار است اما احراز هویت کامل نشد — "
                       "بر اساس راهنمای گام دوم اقدام کنید."}
