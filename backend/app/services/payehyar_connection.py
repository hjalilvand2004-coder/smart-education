"""تنظیمات و تست اتصال به پایه‌یار۳۶۰ — راهکار «از داخل اپ» بدون نیاز به .env.

اولویت منبع تنظیمات: دیتابیس (ذخیرهٔ کاربر از صفحهٔ همگام‌سازی) > متغیر محیطی
S360_PAYEHYAR_* > پیش‌فرض کد. تست اتصال گام‌به‌گام اجرا می‌شود (دسترسی شبکه →
احراز هویت کلید → پیش‌نمایش داده) و برای هر گام خطای قابل‌اقدام فارسی می‌دهد.
"""
import time

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.integrations import PayehyarConnection
from app.services.payehyar_client import DEFAULT_BASE_URL, PayehyarClient

_LIGHT_ENDPOINT = "/api/v1/services/masterdata/unique-courses"


def _row(db: Session) -> PayehyarConnection | None:
    return db.get(PayehyarConnection, 1)


def effective_connection(db: Session) -> dict:
    """تنظیمات مؤثر با منبع هر مقدار — برای نمایش و ساخت کلاینت."""
    s = get_settings()
    row = _row(db)
    if row and row.base_url.strip():
        base_url, base_src = row.base_url.strip().rstrip("/"), "DB"
    else:
        base_url, base_src = s.payehyar_base_url or DEFAULT_BASE_URL, "DEFAULT"
    if row and row.api_key.strip():
        api_key, key_src = row.api_key.strip(), "DB"
    elif s.payehyar_api_key:
        api_key, key_src = s.payehyar_api_key, "ENV"
    else:
        api_key, key_src = "", "NONE"
    return {"base_url": base_url, "api_key": api_key,
            "base_url_source": base_src, "key_source": key_src,
            "updated_at": (row.updated_at if row else None)}


def client_for(db: Session, **overrides) -> PayehyarClient:
    """کلاینت با تنظیمات مؤثر — جایگزین PayehyarClient() در همهٔ مسیرهای همگام‌سازی.

    فقط وقتی مقدار صریح در دیتابیس ذخیره شده باشد پاس داده می‌شود؛ در غیر این
    صورت بدون kwarg ساخته می‌شود تا fallback خود کلاینت (متغیر محیطی/پیش‌فرض کد)
    فعال بماند — و امضای سازنده برای کلاس‌های مشتق بی‌تنش بماند."""
    eff = effective_connection(db)
    if eff["base_url_source"] == "DB" and "base_url" not in overrides:
        overrides["base_url"] = eff["base_url"]
    if eff["key_source"] == "DB" and "api_key" not in overrides:
        overrides["api_key"] = eff["api_key"]
    return PayehyarClient(**overrides)


def save_connection(db: Session, base_url: str | None = None,
                    api_key: str | None = None) -> dict:
    """ذخیره (upsert) تنظیمات اتصال — None یعنی بدون تغییر، "" یعنی پاک کردن.

    کلید بلافاصله در همهٔ همگام‌سازی‌های بعدی (دستی/زمان‌بند) اعمال می‌شود؛
    کلید هرگز در پاسخ API کامل برنمی‌گردد (فقط نمای ماسک‌شده)."""
    row = _row(db)
    if row is None:
        row = PayehyarConnection(id=1)
        db.add(row)
    if base_url is not None:
        base_url = base_url.strip()
        if base_url and not base_url.lower().startswith(("http://", "https://")):
            raise ValueError("آدرس سرویس باید با http:// یا https:// شروع شود")
        row.base_url = base_url[:255]
    if api_key is not None:
        row.api_key = api_key.strip()[:255]
    db.commit()
    return connection_view(db)


def connection_view(db: Session) -> dict:
    """نمای ماسک‌شدهٔ تنظیمات برای صفحهٔ تنظیمات اتصال."""
    eff = effective_connection(db)
    key = eff["api_key"]
    masked = (f"{key[:8]}…{key[-4:]}" if len(key) > 12 else ("●●●" if key else None))
    return {"base_url": eff["base_url"], "api_key_masked": masked,
            "has_key": bool(key), "key_source": eff["key_source"],
            "base_url_source": eff["base_url_source"],
            "updated_at": eff["updated_at"].isoformat() if eff["updated_at"] else None}


def _open_http(transport: httpx.BaseTransport | None, timeout: float) -> httpx.Client:
    """کارخانهٔ httpx — نقطهٔ تزریق transport جعلی در تست‌ها."""
    return httpx.Client(timeout=timeout, transport=transport, follow_redirects=True)


def test_connection(db: Session, base_url: str | None = None,
                    api_key: str | None = None,
                    transport: httpx.BaseTransport | None = None,
                    timeout: float = 10.0) -> dict:
    """تست گام‌به‌گام اتصال — کلید/آدرس override فقط برای «تست پیش از ذخیره».

    گام ۱ دسترسی: openapi.json عمومی سرویس (نسخه/نام هم از همین‌جا می‌آید)
    گام ۲ احراز هویت: یک فراخوانی سبک دامنهٔ رسمی با X-API-Key
    گام ۳ پیش‌نمایش: شمارش آیتم‌های پاسخ — تأیید نهایی سالم بودن مسیر داده"""
    eff = effective_connection(db)
    base = (base_url if base_url is not None else eff["base_url"]).strip().rstrip("/")
    key = (api_key if api_key is not None else eff["api_key"]).strip()
    steps: list[dict] = []
    net_hint = ("سرویس از این دستگاه در دسترس نیست — آدرس و پورت را با تنظیمات "
                "پایه‌یار مقایسه کنید؛ اگر اپ روی دستگاه دیگری اجرا می‌شود، از همان "
                "دستگاه دسترسی (ping/telnet) را بررسی کنید و فایروال پورت را باز کنید.")

    # ---------- گام ۱: دسترسی ----------
    t0 = time.perf_counter()
    title, version = None, None
    try:
        with _open_http(transport, timeout) as hc:
            r = hc.get(f"{base}/openapi.json")
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            meta = (r.json() or {}).get("info") or {}
            title, version = meta.get("title"), meta.get("version")
            steps.append({"name": "دسترسی به سرویس", "ok": True,
                          "detail": f"پاسخ HTTP 200 در {ms} میلی‌ثانیه — "
                                    f"{title or 'سرویس مرجع'} نسخه {version or '?'}",
                          "hint": None})
        else:
            steps.append({"name": "دسترسی به سرویس", "ok": False,
                          "detail": f"پاسخ HTTP {r.status_code} از آدرس داده‌شده",
                          "hint": "آدرس پایه احتمالاً ناقص است — باید نشانی ریشهٔ "
                                  "سرویس باشد (مثال: http://188.212.96.235:8094)"})
    except Exception as exc:  # noqa: BLE001 — هر خطای شبکه باید پیام فارسی بگیرد
        steps.append({"name": "دسترسی به سرویس", "ok": False,
                      "detail": f"{type(exc).__name__}: {str(exc)[:180]}",
                      "hint": net_hint})
        return {"ok": False, "steps": steps,
                "summary": "اتصال برقرار نشد — ابتدا گام «دسترسی به سرویس» را رفع کنید."}

    # ---------- گام ۲: احراز هویت ----------
    if not key:
        steps.append({"name": "احراز هویت کلید API", "ok": False,
                      "detail": "هیچ کلیدی برای ارسال در هدر X-API-Key وجود ندارد",
                      "hint": "در پنل پایه‌یار۳۶۰ → «سرویس‌های داده» → «سامانه‌های "
                              "مصرف‌کننده» کلید سامانهٔ «سامانه یادگیری هوشمند» را "
                              "بردارید و همین‌جا ذخیره کنید."})
        return {"ok": False, "steps": steps,
                "summary": "سرویس در دسترس است اما کلید API تنظیم نشده — کلید را "
                           "در کارت «تنظیمات و تست اتصال» ذخیره کنید."}
    try:
        with _open_http(transport, timeout) as hc:
            r2 = hc.get(f"{base}{_LIGHT_ENDPOINT}", params={"limit": 5},
                        headers={"X-API-Key": key})
        if r2.status_code == 200:
            items = (r2.json() or {}).get("items") or []
            steps.append({"name": "احراز هویت کلید API", "ok": True,
                          "detail": "کلید با هدر X-API-Key پذیرفته شد",
                          "hint": None})
            steps.append({"name": "پیش‌نمایش داده", "ok": True,
                          "detail": f"دریافت {len(items)} درس یکتا از دامنهٔ "
                                    "masterdata — مسیر داده سالم است",
                          "hint": None})
            return {"ok": True, "steps": steps,
                    "summary": f"اتصال کامل است ✓ ({title or 'پایه‌یار۳۶۰'} نسخه "
                               f"{version or '?'} — کلید سالم) — می‌توانید همگام‌سازی کنید."}
        if r2.status_code in (401, 403):
            steps.append({"name": "احراز هویت کلید API", "ok": False,
                          "detail": f"HTTP {r2.status_code} — {r2.text[:150]}",
                          "hint": "کلید نادرست است یا غیرفعال شده یا دامنهٔ "
                                  "دسترسی ندارد — در پنل پایه‌یار وضعیت کلید "
                                  "«سامانه یادگیری هوشمند» را بررسی کنید."})
        elif r2.status_code == 404:
            steps.append({"name": "احراز هویت کلید API", "ok": False,
                          "detail": "HTTP 404 — endpoint دامنه یافت نشد",
                          "hint": "نسخهٔ سرویس مرجع با نسخهٔ مورد انتظار اپ "
                                  "هم‌خوان نیست — نسخهٔ سرویس را با مستندات "
                                  "یکپارچه‌سازی مقایسه کنید."})
        else:
            steps.append({"name": "احراز هویت کلید API", "ok": False,
                          "detail": f"HTTP {r2.status_code} — {r2.text[:150]}",
                          "hint": "خطای غیرمنتظرهٔ سرویس — لاگ پایه‌یار را بررسی "
                                  "کنید و دوباره تست بگیرید."})
    except Exception as exc:  # noqa: BLE001
        steps.append({"name": "احراز هویت کلید API", "ok": False,
                      "detail": f"{type(exc).__name__}: {str(exc)[:180]}",
                      "hint": net_hint})
    return {"ok": False, "steps": steps,
            "summary": "دسترسی شبکه برقرار است اما احراز هویت کامل نشد — "
                       "بر اساس راهنمای گام دوم اقدام کنید."}
