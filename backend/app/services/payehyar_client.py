"""کلاینت واقعی پایه‌یار۳۶۰ — هسته مشترک و اطلاعات پایه اکوسیستم دانشجو۳۶۰.

سرویس مقصد (پروب واقعی ۲۰۲۶-۱۱-۲۳): «PayehYar360 — Shared Core & Master Data»
FastAPI/OpenAPI 3.1 — نسخه ۱.۰.۸ — شرکت ماه‌افزار هوشمند رسا.

نقشه احراز هویت سرویس واقعی (از پاسخ‌های واقعی سرویس استخراج شده):
- endpoint مصرف‌کنندگان اکوسیستم: ``GET /api/v1/services/masterdata/{domain}``
  با هدر ``X-API-Key`` (کلید ثبت‌شده توسط مدیر پایه‌یار در سرویس‌کلاینت‌ها).
- endpoint های مدیریتی (``/api/v1/masterdata/*`` و ``/api/v1/sync/*``): در حالت
  توسعه هدر ``X-Dev-User`` لازم است؛ کاربر باید نقش steward / tenant_admin /
  master_data_editor / auditor و اتصال tenant داشته باشد.
- بدنه خطا ساختار ثابت دارد:
  ``{"code": ..., "message": ..., "correlation_id": ...}``؛ کدهای مشاهده‌شده:
  UNAUTHENTICATED / INSUFFICIENT_ROLE / NOT_FOUND.

هر خطا به ``PayehyarError`` با «راهنمای اقدام» فارسی نگاشت می‌شود تا کاربر در UI
دقیقاً بداند چه چیزی باید تنظیم شود؛ همگام‌سازی هرگز داده ساختگی واقعی‌نما
تولید نمی‌کند (برخلاف حالت نمونه per-course که فقط برای توسعه بدون شبکه است).
"""
import httpx

from app.core.config import Settings, get_settings

DEFAULT_BASE_URL = "http://188.212.96.235:8094"

# نقشه کد خطا → راهنمای اقدام فارسی (به‌صورت فرمت با جزئیات پاسخ سرویس)
_HINTS = {
    "NEEDS_API_KEY": (
        "کلید API تنظیم نشده است. در پایه‌یار۳۶۰ (سرویس‌کلاینت‌ها) یک کلید برای "
        "«دانشجو۳۶۰» صادر کنید و متغیر S360_PAYEHYAR_API_KEY را تنظیم کنید."
    ),
    "INVALID_API_KEY": (
        "کلید API نامعتبر یا قطع‌شده است. در پایه‌یار۳۶۰ وضعیت کلید را بررسی و "
        "در صورت نیاز کلید جدید صادر و S360_PAYEHYAR_API_KEY را به‌روز کنید."
    ),
    "NEEDS_ROLE": (
        "کاربر تنظیم‌شده نقش لازم را ندارد. نقش‌های موردنیاز: {roles}. یا کلید API "
        "تنظیم کنید یا S360_PAYEHYAR_DEV_USER را با کاربر دارای نقش تنظیم کنید."
    ),
    "NEEDS_TENANT": (
        "هویت به هیچ مشتری (tenant) متصل نیست. ورود باید از پرتال مرکزی با claim "
        "tenant انجام شود؛ یا از کلید API استفاده کنید."
    ),
    "UNREACHABLE": (
        "اتصال به پایه‌یار۳۶۰ برقرار نشد. آدرس S360_PAYEHYAR_BASE_URL و "
        "دسترسی شبکه را بررسی کنید."
    ),
}


class PayehyarError(Exception):
    """خطای فراخوانی سرویس مرجع — با کد طبقه‌بندی و راهنمای اقدام فارسی."""

    def __init__(self, code: str, message: str, hint: str | None = None,
                 http_status: int | None = None, correlation_id: str | None = None,
                 required_roles: list[str] | None = None):
        self.code = code
        self.message = message
        self.hint = hint or _HINTS.get(code)
        self.http_status = http_status
        self.correlation_id = correlation_id
        self.required_roles = required_roles or []
        super().__init__(message)


class PayehyarClient:
    """کلاینت HTTP سرویس مرجع — transport قابل تزریق برای تست بدون شبکه."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 dev_user: str | None = None, timeout: int | None = None,
                 transport: httpx.BaseTransport | None = None,
                 settings: Settings | None = None):
        s = settings or get_settings()
        self.base_url = (base_url or s.payehyar_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else s.payehyar_api_key
        self.dev_user = dev_user if dev_user is not None else s.payehyar_dev_user
        self.timeout = timeout or s.payehyar_timeout_seconds
        self._transport = transport

    # ---------- پایه ----------

    @property
    def auth_mode(self) -> str:
        if self.api_key:
            return "API_KEY"
        if self.dev_user:
            return "DEV_USER"
        return "NONE"

    def _headers(self, force_dev: bool = False) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key and not force_dev:
            h["X-API-Key"] = self.api_key
        elif self.dev_user:
            h["X-Dev-User"] = self.dev_user
        return h

    def _request(self, method: str, path: str, *, force_dev: bool = False,
                 json_body: dict | None = None, params: dict | None = None) -> dict:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout,
                              transport=self._transport) as client:
                resp = client.request(method, path, headers=self._headers(force_dev),
                                      json=json_body, params=params)
        except httpx.HTTPError as exc:
            raise PayehyarError("UNREACHABLE", f"اتصال به پایه‌یار۳۶۰ برقرار نشد: {exc}")

        if resp.status_code >= 400:
            self._raise_for_response(resp, path)
        if not resp.content:
            return {}
        return resp.json()

    def _raise_for_response(self, resp: httpx.Response, path: str) -> None:
        """نگاشت پاسخ خطای سرویس مرجع به PayehyarError با راهنمای اقدام."""
        body: dict = {}
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001 — پاسخ غیر JSON (مثلاً HTML پراکسی)
            pass
        code = body.get("code") or ""
        message = body.get("message") or f"خطای {resp.status_code} از سرویس مرجع"
        cid = body.get("correlation_id")
        roles = (body.get("details") or {}).get("required_roles") or []

        if code == "INSUFFICIENT_ROLE":
            hint = _HINTS["NEEDS_ROLE"].format(roles=", ".join(roles) or "steward")
            raise PayehyarError("NEEDS_ROLE", message, hint=hint,
                                http_status=resp.status_code, correlation_id=cid,
                                required_roles=roles)
        if code == "UNAUTHENTICATED":
            if "کلید API ارسال نشده" in message or "X-API-Key" in message:
                raise PayehyarError("NEEDS_API_KEY", message, http_status=resp.status_code,
                                    correlation_id=cid)
            if "نامعتبر" in message or "قطع" in message:
                raise PayehyarError("INVALID_API_KEY", message, http_status=resp.status_code,
                                    correlation_id=cid)
            if "X-Dev-User" in message:
                raise PayehyarError("NEEDS_API_KEY", message, http_status=resp.status_code,
                                    correlation_id=cid,
                                    hint=("حالت توسعه سرویس مرجع فعال است؛ "
                                          "S360_PAYEHYAR_DEV_USER را با کاربر دارای نقش "
                                          "تنظیم کنید یا کلید API صادر کنید."))
            if "tenant" in message:
                raise PayehyarError("NEEDS_TENANT", message, http_status=resp.status_code,
                                    correlation_id=cid)
            raise PayehyarError("NEEDS_API_KEY", message, http_status=resp.status_code,
                                correlation_id=cid)
        raise PayehyarError("REMOTE_ERROR", f"{message} ({path})",
                            http_status=resp.status_code, correlation_id=cid)

    # ---------- عملیات ----------

    def probe(self) -> dict:
        """بررسی دسترس‌پذیری و وضعیت احراز هویت — بدون خطا؛ همیشه dict برمی‌گرداند.

        openapi.json همیشه عمومی است (نام/نسخه سرویس)؛ سپس با یک فراخوانی سبک
        از endpoint سرویس‌ها، وضعیت احراز هویت طبقه‌بندی می‌شود.
        """
        info = {"base_url": self.base_url, "auth_mode": self.auth_mode,
                "reachable": False, "service_title": None, "service_version": None,
                "status": "UNREACHABLE", "hint": _HINTS["UNREACHABLE"],
                "required_roles": []}
        try:
            meta = self._request("GET", "/openapi.json")
        except PayehyarError as exc:
            info.update(status=exc.code if exc.code != "REMOTE_ERROR" else "UNREACHABLE",
                        hint=exc.hint or info["hint"])
            return info
        info["reachable"] = True
        info["service_title"] = (meta.get("info") or {}).get("title")
        info["service_version"] = (meta.get("info") or {}).get("version")
        info["hint"] = None
        try:
            # سبک‌ترین فراخوانی احرازدار برای طبقه‌بندی وضعیت؛ endpoint سرویس‌ها
            # فقط X-API-Key می‌پذیرد و endpoint مدیریتی نقش X-Dev-User را می‌سنجد.
            if self.dev_user and not self.api_key:
                self._request("GET", "/api/v1/masterdata/instructors", params={"limit": 1})
            else:
                # سبک‌ترین دامنه رسمی مصرف‌کننده طبق راهنمای یکپارچه‌سازی
                self._request("GET", "/api/v1/services/masterdata/unique-courses")
            info["status"] = "OK"
        except PayehyarError as exc:
            info["status"] = exc.code
            info["hint"] = exc.hint
            info["required_roles"] = exc.required_roles
            # پیام واقعی سرویس مرجع برای شفافیت کامل حفظ می‌شود
            info["detail"] = exc.message
        return info

    def fetch_catalog(self) -> dict:
        """واکشی کاتالوگ از سه دامنه مستند راهنمای یکپارچه‌سازی (v1.0.12):
        unique-courses + split-courses → رکوردهای درس؛ course-syllabi → سرفصل مصوب.

        پاسخ هر دامنه: {ok, domain, title, count, generated_at, items[]}.
        خطای هر دامنه بحرانی نیست: در «warnings» ثبت و ادامه می‌دهیم (تاب‌آوری).
        """
        if not self.api_key:
            # طبق راهنما، endpoint سرویس‌ها فقط با X-API-Key باز می‌شود؛
            # هدر X-Dev-User فقط مسیرهای مدیریتی پنل را باز می‌کند.
            raise PayehyarError("NEEDS_API_KEY",
                                "مسیر مصرف‌کننده فقط با کلید API باز می‌شود.",
                                hint=_HINTS["NEEDS_API_KEY"])
        warnings: list[str] = []
        courses: list[dict] = []
        syllabi: list[dict] = []
        meta: dict = {"domains": {}}
        for domain in ("unique-courses", "split-courses", "course-syllabi"):
            try:
                body = self._request("GET", f"/api/v1/services/masterdata/{domain}")
            except PayehyarError as exc:
                warnings.append(f"{domain}: {exc.code} — {exc.message}")
                continue
            items = body.get("items") or []
            meta["domains"][domain] = {"count": body.get("count", len(items)),
                                       "generated_at": body.get("generated_at")}
            if domain in ("unique-courses", "split-courses"):
                courses.extend(items)
            else:
                syllabi.extend(items)
        if not courses:
            # هیچ درسی واکشی نشد — خطای واقعی را بالا بفرست تا لاگ شود
            if warnings:
                raise PayehyarError("REMOTE_ERROR", "؛ ".join(warnings[:3]))
            raise PayehyarError("REMOTE_ERROR", "پاسخ خالی از سرویس مرجع")
        return {"courses": courses, "syllabi": syllabi,
                "warnings": warnings, "meta": meta}

    def fetch_domain(self, domain: str, since: str | None = None) -> dict:
        """واکشی یک دامنه مشخص با پارامتر since طبق راهنما (برای sync افزایشی)."""
        params = {"since": since} if since else None
        return self._request("GET", f"/api/v1/services/masterdata/{domain}",
                             params=params)

    def fetch_changes(self, cursor: str | None = None, limit: int = 200) -> dict:
        """فید تغییرات cursor-based برای همگام‌سازی افزایشی."""
        params: dict = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/api/v1/sync/changes", params=params)

    def send_checkpoint(self, cursor: str, scope: str = "masterdata",
                        note: str | None = None) -> bool:
        """ثبت نقطه آخرین همگام‌سازی در سرویس مرجع — بهترین تلاش؛ شکست بحرانی نیست."""
        try:
            self._request("POST", "/api/v1/sync/checkpoints",
                          json_body={"cursor": int(cursor) if str(cursor).isdigit() else 0,
                                     "scope": scope, "note": note})
            return True
        except (PayehyarError, ValueError):
            return False
