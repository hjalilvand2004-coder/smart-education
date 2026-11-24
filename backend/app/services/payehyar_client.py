"""کلاینت واقعی پایه‌یار۳۶۰ — هسته مشترک و اطلاعات پایه اکوسیستم دانشجو۳۶۰.

سرویس مقصد (پروب واقعی ۲۰۲۶-۱۱-۲۳): «PayehYar360 — Shared Core & Master Data»
FastAPI/OpenAPI 3.1 — شرکت ماه‌افزار هوشمند رسا.

قرارداد کامل «سند فنی اتصال» (v3.4.0):
- احراز: کلید API مصرف‌کننده (X-API-Key) یا OAuth2 client_credentials روی
  ``token_endpoint`` پرتال مرکزی (secret فقط از env — هرگز در مخزن) یا کاربر
  توسعه (X-Dev-User) برای مسیرهای مدیریتی.
- ``X-Correlation-ID``: یک UUID یکتا در هر درخواست برای ردیابی سراسری.
- ``Idempotency-Key``: یک UUID یکتا برای هر POST.
- ``If-None-Match`` / ``ETag``: کش درخواست‌های GET؛ پاسخ 304 یعنی «بدون تغییر»
  و بدون انتقال داده. ``If-Match`` برای نوشتن‌های شرطی (ETag دریافتی از GET).
- retry نمایی (سند: حداکثر ۵ تلاش) فقط روی 502/503/504 و خطاهای شبکه.
- timeout پیش‌فرض ۳۰ ثانیه (سند فنی).

نقشه احراز هویت سرویس واقعی (از پاسخ‌های واقعی سرویس استخراج شده):
- endpoint مصرف‌کنندگان اکوسیستم: ``GET /api/v1/services/masterdata/{domain}``
  با هدر ``X-API-Key`` (کلید ثبت‌شده توسط مدیر پایه‌یار در سرویس‌کلاینت‌ها).
- endpoint های مدیریتی (``/api/v1/masterdata/*`` و ``/api/v1/reference-sets``):
  در حالت توسعه هدر ``X-Dev-User`` لازم است؛ کاربر باید نقش steward /
  tenant_admin / master_data_editor / auditor و اتصال tenant داشته باشد.
- بدنه خطا ساختار ثابت دارد:
  ``{"code": ..., "message": ..., "correlation_id": ...}``؛ کدهای مشاهده‌شده:
  UNAUTHENTICATED / INSUFFICIENT_ROLE / NOT_FOUND.

هر خطا به ``PayehyarError`` با «راهنمای اقدام» فارسی نگاشت می‌شود تا کاربر در UI
دقیقاً بداند چه چیزی باید تنظیم شود؛ همگام‌سازی هرگز داده ساختگی واقعی‌نما
تولید نمی‌کند (برخلاف حالت نمونه per-course که فقط برای توسعه بدون شبکه است).
"""
import os
import time
import uuid

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
    "OAUTH_ERROR": (
        "احراز OAuth2 ناموفق بود. S360_PAYEHYAR_CLIENT_SECRET (یا PAYEHYAR_CLIENT_SECRET "
        "طبق سند) و S360_PAYEHYAR_TOKEN_ENDPOINT را با مقادیر دریافتی از SSO بررسی کنید؛ "
        "client_id باید «smart-learning» و scope «masterdata.read» باشد."
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


def _extract_items(body) -> list:
    """استخراج فهرست رکوردها از شکل‌های رایج پاسخ: آرایه خام یا کلید items/data/…"""
    if isinstance(body, list):
        return [x for x in body if isinstance(x, dict)]
    if isinstance(body, dict):
        for key in ("items", "data", "results", "records", "rows", "changes"):
            if isinstance(body.get(key), list):
                return [x for x in body[key] if isinstance(x, dict)]
    return []


class PayehyarClient:
    """کلاینت HTTP سرویس مرجع — transport قابل تزریق برای تست بدون شبکه."""

    # دامنه‌های گسترش‌یافته سند فنی → مسیر مدیریتی معادل (در نبود مسیر services)
    _ADMIN_ROUTES = {
        "professors": "/api/v1/masterdata/instructors",
        "classrooms": "/api/v1/masterdata/classrooms",
        "academic-groups": "/api/v1/masterdata/academic-groups",
        "reference-sets": "/api/v1/reference-sets",
    }

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 dev_user: str | None = None, timeout: int | None = None,
                 transport: httpx.BaseTransport | None = None,
                 settings: Settings | None = None,
                 client_id: str | None = None, client_secret: str | None = None,
                 token_endpoint: str | None = None, oauth_scope: str | None = None,
                 retry_max_attempts: int | None = None, retry_backoff: float | None = None,
                 etag_cache: bool | None = None):
        s = settings or get_settings()
        self.base_url = (base_url or s.payehyar_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else s.payehyar_api_key
        self.dev_user = dev_user if dev_user is not None else s.payehyar_dev_user
        # سند فنی: timeout_seconds = 30 — با حفظ سازگاری تنظیم قدیمی
        self.timeout = timeout or s.payehyar_http_timeout_seconds or s.payehyar_timeout_seconds
        self.client_id = client_id if client_id is not None else s.payehyar_client_id
        self.client_secret = (client_secret if client_secret is not None
                              else s.payehyar_client_secret)
        self.token_endpoint = token_endpoint or s.payehyar_token_endpoint
        self.oauth_scope = oauth_scope or s.payehyar_oauth_scope
        self.retry_max_attempts = (retry_max_attempts if retry_max_attempts is not None
                                   else s.payehyar_retry_max_attempts)
        self.retry_backoff = (retry_backoff if retry_backoff is not None
                              else s.payehyar_retry_backoff_seconds)
        self.etag_cache = etag_cache if etag_cache is not None else s.payehyar_etag_cache
        self._transport = transport
        self._token: str | None = None
        self._token_exp: float = 0.0
        self._etag_store: dict[str, str] = {}

    # ---------- احراز هویت ----------

    @property
    def auth_mode(self) -> str:
        if self.client_secret:
            return "OAUTH2"
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

    def _get_token(self) -> str | None:
        """توکن OAuth2 client_credentials طبق سند فنی (token_endpoint پرتال :8086).

        secret از S360_PAYEHYAR_CLIENT_SECRET یا نام سند PAYEHYAR_CLIENT_SECRET
        خوانده می‌شود؛ توکن تا ۶۰ ثانیه پیش از انقضا کش می‌شود.
        """
        secret = self.client_secret or os.getenv("PAYEHYAR_CLIENT_SECRET", "")
        if not secret:
            return None
        if self._token and time.monotonic() < self._token_exp:
            return self._token
        body = {"grant_type": "client_credentials", "client_id": self.client_id,
                "client_secret": secret, "scope": self.oauth_scope}
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout,
                              transport=self._transport) as client:
                resp = client.post(self.token_endpoint, data=body,
                                   headers={"X-Correlation-ID": str(uuid.uuid4())})
        except httpx.HTTPError as exc:
            raise PayehyarError("OAUTH_ERROR", f"دریافت توکن از SSO ناموفق بود: {exc}")
        if resp.status_code >= 400:
            raise PayehyarError("OAUTH_ERROR",
                                f"SSO توکن صادر نکرد (HTTP {resp.status_code}).")
        payload = resp.json() if resp.content else {}
        self._token = payload.get("access_token")
        if not self._token:
            raise PayehyarError("OAUTH_ERROR", "پاسخ SSO بدون access_token بود.")
        try:
            ttl = int(payload.get("expires_in", 3600))
        except (TypeError, ValueError):
            ttl = 3600
        self._token_exp = time.monotonic() + max(60, ttl - 60)
        return self._token

    # ---------- پایه ----------

    @staticmethod
    def _cache_key(path: str, params: dict | None) -> str:
        if not params:
            return path
        query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{path}?{query}"

    def _request(self, method: str, path: str, *, force_dev: bool = False,
                 json_body: dict | None = None, params: dict | None = None,
                 etag: bool = False, if_match: str | None = None) -> dict:
        """یک درخواست با قرارداد کامل سند فنی اتصال.

        - X-Correlation-ID یکتا در هر درخواست؛ Idempotency-Key یکتا در هر POST.
        - etag=True برای GET: ارسال If-None-Match از کش؛ پاسخ 304 →
          ``{"_not_modified": True}`` (بدون انتقال داده) و ذخیره ETag پاسخ‌های جدید.
        - if_match برای نوشتن شرطی با ETag دریافتی از GET.
        - retry نمایی روی 502/503/504 و خطای شبکه (سند: حداکثر ۵ تلاش).
        """
        headers = self._headers(force_dev)
        headers["X-Correlation-ID"] = str(uuid.uuid4())
        if method.upper() == "POST":
            headers["Idempotency-Key"] = str(uuid.uuid4())
        cache_key = self._cache_key(path, params)
        if etag and method.upper() == "GET" and self._etag_store.get(cache_key):
            headers["If-None-Match"] = self._etag_store[cache_key]
        if if_match:
            headers["If-Match"] = if_match
        token = self._get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        attempts = max(1, self.retry_max_attempts)
        resp: httpx.Response | None = None
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout,
                              transport=self._transport) as client:
                for attempt in range(1, attempts + 1):
                    try:
                        resp = client.request(method, path, headers=headers,
                                              json=json_body, params=params)
                    except httpx.HTTPError:
                        if attempt == attempts:
                            raise
                    else:
                        if resp.status_code not in (502, 503, 504) or attempt == attempts:
                            break
                    time.sleep(self.retry_backoff * (2 ** (attempt - 1)))
        except httpx.HTTPError as exc:
            raise PayehyarError("UNREACHABLE", f"اتصال به پایه‌یار۳۶۰ برقرار نشد: {exc}")
        if resp is None:  # دفاعی — عملاً رخ نمی‌دهد
            raise PayehyarError("UNREACHABLE", "پاسخی از سرویس مرجع دریافت نشد.")
        if resp.status_code == 304:
            return {"_not_modified": True}
        if resp.status_code >= 400:
            self._raise_for_response(resp, path)
        if etag and resp.headers.get("etag"):
            self._etag_store[cache_key] = resp.headers["etag"]
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
        از endpoint سرویس‌ها، وضعیت احراز هویت طبقه‌بندی می‌شود. نقاط پایانی
        ``health``/``ready`` سند فنی نیز بررسی می‌شوند (در استقرار فعلی ممکن است
        404 باشند — این حالت مانع اتصال نیست و فقط گزارش می‌شود).
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
        # سند فنی — monitoring: health/ready (نتیجه هر وضعیتی شفاف گزارش می‌شود)
        for name, path in (("health", "/api/v1/health"), ("ready", "/api/v1/ready")):
            try:
                self._request("GET", path)
                info[name] = {"available": True, "http_status": 200}
            except PayehyarError as exc:
                info[name] = {"available": False, "http_status": exc.http_status}
        return info

    def fetch_catalog(self) -> dict:
        """واکشی کاتالوگ از سه دامنه مستند راهنمای یکپارچه‌سازی (v1.0.12):
        unique-courses + split-courses → رکوردهای درس؛ course-syllabi → سرفصل مصوب.

        پاسخ هر دامنه: {ok, domain, title, count, generated_at, items[]}.
        خطای هر دامنه بحرانی نیست: در «warnings» ثبت و ادامه می‌دهیم (تاب‌آوری).
        با فعال بودن کش ETag، پاسخ 304 یعنی «بدون تغییر از آخرین واکشی».
        """
        if not self.api_key and not self.client_secret:
            # طبق راهنما، endpoint سرویس‌ها فقط با X-API-Key (یا Bearer OAuth2) باز می‌شود؛
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
                body = self._request("GET", f"/api/v1/services/masterdata/{domain}",
                                     etag=self.etag_cache)
            except PayehyarError as exc:
                warnings.append(f"{domain}: {exc.code} — {exc.message}")
                continue
            if body.get("_not_modified"):
                meta["domains"][domain] = {"not_modified": True}
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
                             params=params, etag=self.etag_cache)

    def fetch_extended_domain(self, domain: str, since: str | None = None) -> dict:
        """واکشی دامنه‌های گسترش‌یافته سند فنی (professors/classrooms/
        academic-groups/reference-sets) — ابتدا مسیر رسمی مصرف‌کننده
        (services/masterdata/{domain})، در نبودِ آن مسیر مدیریتی معادل
        (نیازمند X-Dev-User). خروجی: {items, source, warnings}."""
        if not self.api_key and not self.dev_user and not self.client_secret:
            raise PayehyarError("NEEDS_API_KEY", "اعتبارنامه‌ای تنظیم نشده است.",
                                hint=_HINTS["NEEDS_API_KEY"])
        warnings: list[str] = []
        params = {"since": since} if since else None
        if self.api_key or self.client_secret:
            try:
                body = self._request("GET", f"/api/v1/services/masterdata/{domain}",
                                     params=params, etag=self.etag_cache)
                if body.get("_not_modified"):
                    return {"items": [], "source": "services", "warnings": warnings,
                            "not_modified": True}
                return {"items": _extract_items(body), "source": "services",
                        "warnings": warnings}
            except PayehyarError as exc:
                warnings.append(f"services/{domain}: {exc.code} — {exc.message}")
        admin = self._ADMIN_ROUTES.get(domain)
        if admin and self.dev_user:
            try:
                body = self._request("GET", admin, params={"limit": 500},
                                     force_dev=True)
                return {"items": _extract_items(body), "source": "admin",
                        "warnings": warnings}
            except PayehyarError as exc:
                warnings.append(f"admin/{admin}: {exc.code} — {exc.message}")
        raise PayehyarError("REMOTE_ERROR",
                            "؛ ".join(warnings[:2]) or f"دامنه {domain} در دسترس نیست")

    def fetch_changes(self, cursor: str | None = None, limit: int = 200) -> dict:
        """فید تغییرات cursor-based برای همگام‌سازی افزایشی (سند: cursor عددی)."""
        params: dict = {"limit": limit}
        if cursor:
            try:
                params["cursor"] = int(str(cursor).strip())
            except ValueError:
                params["cursor"] = cursor  # کرسر غیرعددی — عیناً ارسال می‌شود
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
