"""کلاینت اتصال به سامانه «برنامه‌یار۳۶۰» — فقط «برنامهٔ ترم جاری» (v3.9.0).

طبق تصمیم محصول: از برنامه‌یار۳۶۰ تنها سرویسِ «برنامهٔ ترم جاری متناسب با استاد»
مصرف می‌شود، نه چیز دیگری؛ دروس یکتا و سرفصل‌ها از پایه‌یار۳۶۰ می‌آیند.

قرارداد مصرف (پیکربندی‌پذیر؛ در نبود مستند رسمی چند مسیر مرسوم امتحان می‌شود):
  GET {base}/api/schedules?professor={ext_id}&term=current
  GET {base}/api/v1/schedules/current/{ext_id}
  GET {base}/api/professors/{ext_id}/schedule
  در صورت نیاز، ابتدا POST /api/auth/login توکن گرفته و در هدر Authorization می‌رود.
  پاسخ موردانتظار: فهرست جلسات هفتگی [{day, start, end, course_title, course_code,
  group, place}] یا {items|schedule|data: [...]} — نگاشت defensive است تا تغییر
  شکل پاسخ سامانهٔ مقصد واکشی را نشکند.

اگر سرویس در دسترس نبود/مسیر نبود → «نمونهٔ قطعی» deterministic بر پایهٔ شناسهٔ
استاد و درس‌های سامانه؛ source="demo" با پیام شفاف در UI (هم‌قرارداد با درس‌یار).
"""
import hashlib
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings

DEFAULT_BASE_URL = "http://188.212.96.235:8083"

DAYS = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه")
SLOTS = (("۸:۰۰", "۹:۳۰"), ("۹:۴۵", "۱۱:۱۵"), ("۱۱:۳۰", "۱۳:۰۰"),
         ("۱۴:۰۰", "۱۵:۳۰"), ("۱۵:۴۵", "۱۷:۱۵"))
PLACES = ("کلاس ۱۰۱", "کلاس ۲۰۳", "آزمایشگاه مرکزی", "کلاس ۳۰۵", "سالن همایش")

# ---------- تقویم جلالی آفلاین (فقط برای برچسب ترم جاری) ----------


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل میلادی به جلالی — الگوریتم استاندارد jalaali (آفلاین، بدون وابستگی)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
            + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1])
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


def fa_digits(text) -> str:
    """تبدیل ارقام لاتین به فارسی برای برچسب ترم."""
    return str(text).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def current_term_label(now: datetime | None = None) -> str:
    """برچسب ترم جاری از تقویم جلالی: نیم‌سال اول/دوم یا تابستان."""
    now = now or datetime.now(timezone.utc)
    jy, jm, _ = gregorian_to_jalali(now.year, now.month, now.day)
    if jm >= 7:
        return f"نیم‌سال اول {fa_digits(jy)}–{fa_digits(jy + 1)}"
    if jm <= 3:
        return f"نیم‌سال دوم {fa_digits(jy - 1)}–{fa_digits(jy)}"
    return f"ترم تابستان {fa_digits(jy)}"  # تیر/مرداد/شهریور


def _pick(raw: dict, *keys: str):
    """اولین مقدار غیرخالی بین کلیدهای احتمالی."""
    for k in keys:
        v = raw.get(k)
        if v not in (None, ""):
            return v
    return None


def parse_schedule_row(raw: dict) -> dict | None:
    """نگاشت defensive یک ردیف برنامهٔ هفتگی به شکل استاندارد دانشجو۳۶۰."""
    if not isinstance(raw, dict):
        return None
    title = _pick(raw, "course_title", "title", "course_name", "lesson_title", "name")
    day = _pick(raw, "day", "weekday", "day_of_week", "day_name")
    if not (title and day):
        return None
    return {
        "day": str(day),
        "start": str(_pick(raw, "start", "start_time", "from", "begin") or ""),
        "end": str(_pick(raw, "end", "end_time", "to", "finish") or ""),
        "course_title": str(title),
        "course_code": str(_pick(raw, "course_code", "code", "unique_code", "lesson_code") or ""),
        "group": str(_pick(raw, "group", "group_code", "section") or ""),
        "place": str(_pick(raw, "place", "location", "classroom", "room", "hall") or ""),
        "professor_name": str(_pick(raw, "professor", "professor_name", "teacher", "instructor") or ""),
    }


def extract_schedule_rows(body) -> list[dict]:
    """پشتیبانی از چند شکل پاسخ: فهرست خام، {items}, {schedule}, {data}."""
    if isinstance(body, list):
        rows = body
    elif isinstance(body, dict):
        rows = None
        for key in ("items", "schedule", "data", "rows", "lessons"):
            if isinstance(body.get(key), list):
                rows = body[key]
                break
        if rows is None and isinstance(body.get("days"), dict):
            merged: list[dict] = []
            for day, lst in body["days"].items():
                if isinstance(lst, list):
                    for r in lst:
                        if isinstance(r, dict):
                            merged.append({"day": day, **r})
            rows = merged
        if rows is None:
            rows = []
    else:
        rows = []
    return [row for row in (parse_schedule_row(r) for r in rows) if row]


# ---------- نمونهٔ قطعی (وقتی سرویس در دسترس نیست) ----------


def _seed_of(ext_id: str) -> int:
    return int(hashlib.sha256(str(ext_id).encode("utf-8")).hexdigest()[:8], 16)


def demo_schedule(professor: dict, course_pool: list[dict],
                  term: str | None = None) -> dict:
    """برنامهٔ قطعی ترم جاری برای استاد — تکرارپذیر بر پایهٔ شناسهٔ استاد."""
    seed = _seed_of(professor.get("ext_id") or professor.get("name") or "x")
    pool = course_pool or [{"title": "درس تخصصی نیم‌سال جاری", "code": "GEN101"}]
    n_sessions = 3 + (seed % 3)  # ۳ تا ۵ جلسه در هفته
    entries, used = [], set()
    for i in range(min(n_sessions, len(pool) * 2)):
        c = pool[(seed >> (i * 3)) % len(pool)]
        day = DAYS[(seed >> (i * 2)) % len(DAYS)]
        si = (seed >> (i + 4)) % len(SLOTS)
        if (day, si) in used:
            continue
        used.add((day, si))
        start, end = SLOTS[si]
        entries.append({
            "day": day, "start": start, "end": end,
            "course_title": c["title"],
            "course_code": c.get("code") or "",
            "group": f"گروه {fa_digits(1 + (i % 2))}",
            "place": PLACES[(seed >> i) % len(PLACES)],
            "professor_name": professor.get("name") or "",
        })
    return {
        "term": term or current_term_label(),
        "entries": entries,
        "total_weekly_hours": round(len(entries) * 1.5),
    }


def course_pool_for(db, limit: int = 24) -> list[dict]:
    """استخر درس‌های سامانه برای ساخت برنامهٔ نمونه — از مدل Course محلی."""
    from app.models.courses import Course
    pool: dict[str, dict] = {}
    for c in db.query(Course).order_by(Course.title).limit(limit).all():
        if c.title and c.title not in pool:
            pool[c.title] = {"title": c.title, "code": c.code or ""}
    return list(pool.values())


class ProgramyarClient:
    """کلاینت HTTP برنامه‌یار۳۶۰ با تلاش بی‌توکن و سپس لاگین."""

    def __init__(self, base_url: str | None = None, timeout: float = 12.0,
                 transport: httpx.BaseTransport | None = None):
        s = get_settings()
        self.base_url = (base_url or s.programyar_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._transport = transport  # فقط برای تست

    def _client(self):
        return httpx.Client(base_url=self.base_url, timeout=self.timeout,
                                  transport=self._transport, follow_redirects=True)

    def login(self, client, username: str, password: str) -> str | None:
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        if resp.status_code != 200:
            return None
        data = resp.json() if resp.content else {}
        return _pick(data, "access_token", "token", "jwt")

    def _candidate_paths(self, ext_id: str) -> list[str]:
        from urllib.parse import quote
        safe = quote(str(ext_id), safe="")
        return [
            f"/api/schedules?professor={safe}&term=current",
            f"/api/v1/schedules/current/{safe}",
            f"/api/professors/{safe}/schedule",
        ]

    def fetch_schedule(self, ext_id: str, username: str | None = None,
                       password: str | None = None) -> dict | None:
        """واکشی زندهٔ برنامهٔ ترم جاری استاد؛ در هر خطا/عدم‌دسترسی None.

        اعتبارنامه: آرگومان صریح > متغیر محیطی S360_PROGRAMYAR_* — اگر سرویس
        احراز هویت خواست و اعتباری نبود، None برمی‌گردد (نمونهٔ قطعی در UI)."""
        s = get_settings()
        username = username or s.programyar_username or None
        password = password or s.programyar_password or None
        headers = {"Accept": "application/json"}
        try:
            with self._client() as client:
                for path in self._candidate_paths(ext_id):
                    resp = client.get(path, headers=headers)
                    if resp.status_code in (401, 403) and username and password:
                        token = self.login(client, username, password)
                        if not token:
                            continue
                        resp = client.get(path, headers={**headers,
                                                         "Authorization": f"Bearer {token}"})
                    if resp.status_code != 200:
                        continue
                    rows = extract_schedule_rows(resp.json() if resp.content else None)
                    if rows:
                        return {"entries": rows, "term": current_term_label()}
        except httpx.HTTPError:
            return None
        return None
