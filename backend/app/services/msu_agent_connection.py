"""تنظیمات و تست اتصال به هستهٔ عامل «دانشگاه هوشمند من» — الگوی darsyar_connection.

اولویت منبع تنظیمات: دیتابیس (ذخیرهٔ مدیر از پنل مدیریت) > متغیر محیطی
S360_MSU_AGENT_* > پیش‌فرض کد. ویجت شناور (frontend/public/msu-agent-widget.js)
از مسیر widget-config همین تنظیمات را می‌گیرد و در همهٔ صفحات سامانه رندر
می‌شود؛ گپ چت مستقیماً از مرورگر به هستهٔ عامل زده می‌شود (طراحی ویجت).

تست اتصال گام‌به‌گام (بر اساس widget.js نسخهٔ 1.2.0 و نمونهٔ مرجع):
  گام ۱ دسترسی شبکه و سلامت هسته: GET {base}/api/health
  گام ۲ (اختیاری) احراز توکن: /api/widget/config — ۲۰۰ یعنی هسته بدون نیاز به
       توکن هم پاسخ می‌دهد؛ ۴۰۱/۴۰۳ یعنی REQUIRE_AUTH=true و توکن لازم است.
"""
import time

import httpx
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.integrations import MsuAgentConnection

_POSITIONS = ("br", "bl")


def _row(db: Session) -> MsuAgentConnection | None:
    try:
        return db.get(MsuAgentConnection, 1)
    except OperationalError:
        # دیتابیس قدیمی که هنوز جدولش را ندارد — تنظیمات پیش‌فرض معتبر می‌ماند
        return None


def _valid_color(v: str) -> bool:
    v = v.strip()
    return len(v) in (4, 7) and v.startswith("#") and all(
        c in "0123456789abcdefABCDEF" for c in v[1:])


def effective_connection(db: Session) -> dict:
    """تنظیمات مؤثر با منبع هر مقدار — برای نمایش و تزریق در ویجت."""
    s = get_settings()
    row = _row(db)
    if row and row.base_url.strip():
        base_url, base_src = row.base_url.strip().rstrip("/"), "DB"
    else:
        base_url, base_src = s.msu_agent_base_url or "http://localhost:8000", "DEFAULT"
    if row and row.origin.strip():
        origin, origin_src = row.origin.strip()[:64], "DB"
    else:
        origin, origin_src = s.msu_agent_origin or "student360", "DEFAULT"
    if row and row.accent.strip() and _valid_color(row.accent):
        accent, accent_src = row.accent.strip(), "DB"
    else:
        accent, accent_src = s.msu_agent_accent or "#7c3aed", "DEFAULT"
    if row and row.accent2.strip() and _valid_color(row.accent2):
        accent2, accent2_src = row.accent2.strip(), "DB"
    else:
        accent2, accent2_src = s.msu_agent_accent2 or "#5b21b6", "DEFAULT"
    if row and row.position.strip() in _POSITIONS:
        position, position_src = row.position.strip(), "DB"
    else:
        position, position_src = s.msu_agent_position or "br", "DEFAULT"
    if row and row.token.strip():
        token, token_src = row.token.strip()[:1024], "DB"
    elif s.msu_agent_token:
        token, token_src = s.msu_agent_token, "ENV"
    else:
        token, token_src = "", "NONE"
    if row is not None:
        enabled, enabled_src = bool(row.enabled), "DB"
    else:
        enabled, enabled_src = bool(s.msu_agent_enabled), "DEFAULT"
    return {"base_url": base_url, "origin": origin, "accent": accent,
            "accent2": accent2, "position": position, "token": token,
            "enabled": enabled,
            "base_url_source": base_src, "origin_source": origin_src,
            "accent_source": accent_src, "accent2_source": accent2_src,
            "position_source": position_src, "token_source": token_src,
            "enabled_source": enabled_src,
            "updated_at": (row.updated_at if row else None)}


def save_connection(db: Session, base_url: str | None = None,
                    origin: str | None = None, accent: str | None = None,
                    accent2: str | None = None, position: str | None = None,
                    token: str | None = None, enabled: bool | None = None) -> dict:
    """ذخیره (upsert) تنظیمات — None یعنی بدون تغییر، "" یعنی پاک‌کردن مقدار."""
    row = _row(db)
    if row is None:
        row = MsuAgentConnection(id=1)
        db.add(row)
    if base_url is not None:
        base_url = base_url.strip()
        if base_url and not base_url.lower().startswith(("http://", "https://")):
            raise ValueError("آدرس هستهٔ عامل باید با http:// یا https:// شروع شود")
        row.base_url = base_url[:255]
    if origin is not None:
        row.origin = origin.strip()[:64]
    if accent is not None:
        accent = accent.strip()
        if accent and not _valid_color(accent):
            raise ValueError("رنگ باید به‌شکل #RGB یا #RRGGBB باشد")
        row.accent = accent[:16]
    if accent2 is not None:
        accent2 = accent2.strip()
        if accent2 and not _valid_color(accent2):
            raise ValueError("رنگ دوم باید به‌شکل #RGB یا #RRGGBB باشد")
        row.accent2 = accent2[:16]
    if position is not None:
        position = position.strip()
        if position and position not in _POSITIONS:
            raise ValueError("موقعیت ویجت باید br (پایین‌راست) یا bl (پایین‌چپ) باشد")
        row.position = position[:4]
    if token is not None:
        row.token = token.strip()[:1024]
    if enabled is not None:
        row.enabled = 1 if enabled else 0
    db.commit()
    return connection_view(db)


def connection_view(db: Session) -> dict:
    """نمای ماسک‌شدهٔ تنظیمات برای پنل مدیریت — توکن هرگز کامل برنمی‌گردد."""
    eff = effective_connection(db)
    token = eff["token"]
    masked = (f"{token[:10]}…{token[-4:]}" if len(token) > 14
              else ("●●●" if token else None))
    return {"base_url": eff["base_url"], "origin": eff["origin"],
            "accent": eff["accent"], "accent2": eff["accent2"],
            "position": eff["position"], "token_masked": masked,
            "has_token": bool(token), "token_source": eff["token_source"],
            "enabled": eff["enabled"], "enabled_source": eff["enabled_source"],
            "base_url_source": eff["base_url_source"],
            "updated_at": eff["updated_at"].isoformat() if eff["updated_at"] else None,
            "data_owner": "دانشگاه هوشمند من — هستهٔ عامل"}


def widget_config(db: Session) -> dict:
    """پیکربندی کامل تزریق ویجت — برای همهٔ کاربران واردشده (ویجت در همهٔ صفحات است).

    توکن کامل برمی‌گردد چون ویجت باید آن را در هدر ارسال کند (طراحی رسمی
    widget.js: localStorage یا setToken)؛ دامنهٔ توکن در هستهٔ عامل تعیین می‌شود.
    """
    eff = effective_connection(db)
    return {"enabled": eff["enabled"], "base_url": eff["base_url"],
            "origin": eff["origin"], "accent": eff["accent"],
            "accent2": eff["accent2"], "position": eff["position"],
            "token_key": "msu_agent_token", "token": eff["token"]}


def _open_http(transport: httpx.BaseTransport | None, timeout: float) -> httpx.Client:
    """کارخانهٔ httpx — نقطهٔ تزریق transport جعلی در تست‌ها."""
    return httpx.Client(timeout=timeout, transport=transport, follow_redirects=True)


def test_connection(db: Session, base_url: str | None = None,
                    transport: httpx.BaseTransport | None = None) -> dict:
    """تست گام‌به‌گام هستهٔ عامل: سلامت → پیکربندی ویجت."""
    eff = effective_connection(db)
    base = (base_url or eff["base_url"]).strip().rstrip("/")
    if not base.lower().startswith(("http://", "https://")):
        return {"ok": False, "steps": [
            {"step": "آدرس", "ok": False, "detail": "آدرس باید با http:// یا https:// شروع شود"}]}
    steps: list[dict] = []
    # گام ۱ — سلامت هسته
    t0 = time.perf_counter()
    try:
        with _open_http(transport, 4.0) as client:
            r = client.get(f"{base}/api/health")
        ms = int((time.perf_counter() - t0) * 1000)
        ok = r.status_code == 200
        steps.append({"step": "سلامت هسته (GET /api/health)", "ok": ok,
                      "detail": f"HTTP {r.status_code} — {ms}ms"})
    except Exception as exc:  # noqa: BLE001 — هر خطای شبکه به گام تبدیل می‌شود
        steps.append({"step": "سلامت هسته (GET /api/health)", "ok": False,
                      "detail": f"عدم دسترسی: {type(exc).__name__}"})
        return {"ok": False, "steps": steps}
    # گام ۲ — پیکربندی ویجت (REQUIRE_AUTH=true → ۴۰۱/۴۰۳ با توکن لازم)
    try:
        with _open_http(transport, 4.0) as client:
            r = client.get(f"{base}/api/widget/config")
        if r.status_code == 200:
            detail = "پاسخ ۲۰۰ — هسته بدون نیاز به توکن پیکربندی می‌دهد"
        elif r.status_code in (401, 403):
            detail = "پاسخ " + str(r.status_code) + " — هسته توکن دانشجو می‌خواهد؛ در تنظیمات ذخیره کنید"
        else:
            detail = f"HTTP {r.status_code} — مسیر پیکربندی اختیاری است"
        steps.append({"step": "پیکربندی ویجت (GET /api/widget/config)", "ok": True,
                      "detail": detail})
    except Exception as exc:  # noqa: BLE001
        steps.append({"step": "پیکربندی ویجت (GET /api/widget/config)", "ok": True,
                      "detail": f"مسیر پاسخگو نبود ({type(exc).__name__}) — اختیاری"})
    return {"ok": all(s["ok"] for s in steps), "steps": steps,
            "base_url": base, "engine": "live"}
