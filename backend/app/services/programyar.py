"""کلاینت اتصال به سامانه «برنامه‌یار۳۶۰» (برنامه‌ریزی درسی دانشگاه).

واکشی «درس‌های یکتا» از GET /api/courses/unique؛ در صورت فعال‌بودن احراز هویت،
ابتدا با POST /api/auth/login توکن گرفته و در هدر Authorization ارسال می‌شود.
نگاشت فیلدها defensive است تا تغییر شکل پاسخِ سامانه مقصد، واکشی را نشکند.
"""
import httpx

from app.core.config import get_settings
from app.core.errors import AppError

DEFAULT_BASE_URL = "http://188.212.96.235:8083"


def _pick(raw: dict, *keys: str):
    """اولین مقدار غیرخالی بین کلیدهای احتمالی."""
    for k in keys:
        v = raw.get(k)
        if v not in (None, ""):
            return v
    return None


def parse_unique_course(raw: dict) -> dict:
    """نگاشت یک رکورد درس یکتا به شکل استاندارد دانشجو۳۶۰."""
    if not isinstance(raw, dict):
        return {}
    code = _pick(raw, "course_code", "code", "unique_code", "course_unique_code", "unique_course_code")
    title = _pick(raw, "course_name", "name", "title", "course_title")
    units = _pick(raw, "units", "unit_count", "credit", "credits")
    try:
        units = int(units) if units not in (None, "") else None
    except (TypeError, ValueError):
        units = None
    return {
        "code": str(code) if code is not None else "",
        "title": str(title) if title is not None else "",
        "units": units,
        "department": _pick(raw, "department", "group", "faculty", "dep"),
        "term": _pick(raw, "term", "semester", "academic_term"),
        "field_of_study": _pick(raw, "field_of_study", "field", "major"),
        "degree_level": _pick(raw, "degree_level", "degree", "level"),
        "description": _pick(raw, "description", "comment", "notes"),
    }


class ProgramyarClient:
    """کلاینت HTTP برنامه‌یار۳۶۰ با تلاش بی‌توکن و سپس لاگین."""

    def __init__(self, base_url: str | None = None, timeout: float = 12.0,
                 transport: httpx.BaseTransport | None = None):
        s = get_settings()
        self.base_url = (base_url or s.programyar_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._transport = transport  # فقط برای تست

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout,
                            transport=self._transport, follow_redirects=True)

    def login(self, client: httpx.Client, username: str, password: str) -> str | None:
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        if resp.status_code != 200:
            return None
        data = resp.json() if resp.content else {}
        return _pick(data, "access_token", "token", "jwt")

    def get_unique_courses(self, username: str | None = None,
                           password: str | None = None) -> dict:
        """واکشی درس‌های یکتا؛ اگر سامانه ورود خواست، با اعتبار داده‌شده (یا env) لاگین می‌کند."""
        s = get_settings()
        username = username or s.programyar_username or None
        password = password or s.programyar_password or None

        try:
            with self._client() as client:
                resp = client.get("/api/courses/unique")
                if resp.status_code in (401, 403) or (resp.status_code == 200 and "وارد شوید" in resp.text):
                    if not (username and password):
                        return {"items": [], "total": 0, "auth_used": False, "reachable": True,
                                "message": ("برنامه‌یار۳۶۰ در دسترس است اما برای واکشی درس‌ها "
                                            "نام کاربری و رمز آن سامانه لازم است.")}
                    token = self.login(client, username, password)
                    if not token:
                        return {"items": [], "total": 0, "auth_used": False, "reachable": True,
                                "message": "ورود به برنامه‌یار۳۶۰ ناموفق بود؛ نام کاربری/رمز را بررسی کنید."}
                    resp = client.get("/api/courses/unique", headers={"Authorization": f"Bearer {token}"})
                if resp.status_code != 200:
                    raise AppError(502, "PROGRAMYAR_ERROR",
                                   f"برنامه‌یار۳۶۰ پاسخ {resp.status_code} داد؛ دسترسی سرور را بررسی کنید.")
                payload = resp.json() if resp.content else []
                rows = payload if isinstance(payload, list) else (
                    payload.get("items") or payload.get("courses") or payload.get("data") or [])
                if not isinstance(rows, list):
                    rows = []
                items = [parse_unique_course(r) for r in rows if isinstance(r, dict)]
                items = [i for i in items if i.get("code") or i.get("title")]
                return {"items": items, "total": len(items),
                        "auth_used": bool(username and password),
                        "reachable": True, "message": "واکشی با موفقیت انجام شد."}
        except httpx.HTTPError:
            return {"items": [], "total": 0, "auth_used": False, "reachable": False,
                    "message": ("اتصال به برنامه‌یار۳۶۰ برقرار نشد؛ سامانه مقصد در دسترس نیست یا "
                                "آدرس اشتباه است. می‌توانید درس‌ها را دستی ثبت کنید.")}
