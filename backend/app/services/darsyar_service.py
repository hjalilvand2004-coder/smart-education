"""یکپارچگی با درس‌یار۳۶۰ (darsyar360.ir) — مطلوبیات درسی و زمانی اساتید (v3.7.0).

جریان داده طبق درخواست محصول:
  پایه‌یار۳۶۰ (اساتید) → این سامانه ← درس‌یار۳۶۰ (مطلوبیات درسی/زمانی استاد)
  → نمایش به استاد → فهرست درس‌های متناسب برای تولید محتوا در استودیو.

قرارداد endpoint مصرف‌کننده (پیکربندی‌پذیر؛ در نبود مستند رسمی چند مسیر مرسوم
امتحان می‌شود):
  GET {S360_DARSYAR_BASE_URL}/api/v1/services/instructor-preferences/{ext_id}
  GET {S360_DARSYAR_BASE_URL}/api/v1/instructors/{ext_id}/preferences
  هدر: X-API-Key (S360_DARSYAR_API_KEY) — پاسخ موردانتظار:
  {ok, item:{subjects:[{title, weekly_hours, level}], time_slots:[{day, start, end, preference}], constraints:[...]}}

اگر سرویس در دسترس نبود/کلید نبود → «حالت نمونهٔ قطعی» (deterministic demo)
بر پایهٔ شناسه استاد و درس‌های موجود؛ source="demo" با پیام شفاف در UI —
هم‌قرارداد با الگوی baseyar_service.
"""
import hashlib
from datetime import timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.models.journey import DarsyarPreference, PayehyarRecord

CACHE_TTL_HOURS = 12
DARSYAR_SYSTEM = "درس‌یار۳۶۰"

DAYS = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه")
SLOTS = (("۸:۰۰", "۱۰:۰۰"), ("۱۰:۰۰", "۱۲:۰۰"), ("۱۳:۰۰", "۱۵:۰۰"), ("۱۵:۰۰", "۱۷:۰۰"))
PREF_LEVELS = ("preferred", "acceptable", "avoided")
PREF_LABELS = {"preferred": "مطلوب", "acceptable": "قابل‌قبول", "avoided": "غیرمطلوب"}
SUBJECT_LEVELS = ("تخصصی", "مرتبط", "مکمل")

_DEMO_CONSTRAINTS = (
    "حداکثر ۲ روز در هفته تدریس حضوری؛ بقیه ظرفیت برای تولید محتوای الکترونیک",
    "ترجیح کلاس‌های زودهنگام صبح؛ از بازهٔ بعدازظهر پرهیز شود",
    "روزهای همگام‌سازی جلسات گروه آموزشی: دوشنبه — درس قرار نگیرد",
    "سقف ۶ ساعت تدریس هفتگی تا تمرکز بر پژوهش و تولید محتوا حفظ شود",
)


def _norm(text) -> str:
    """نرمال‌سازی متن برای تطبیق عنوان درس/موضوع (ZWNJ، فاصله، کشیدگی)."""
    return (str(text or "").replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
            .strip().lower())


def _seed_of(ext_id: str) -> int:
    return int(hashlib.sha256(str(ext_id).encode("utf-8")).hexdigest()[:8], 16)


def _candidate_paths(ext_id: str) -> list[str]:
    from urllib.parse import quote
    safe = quote(str(ext_id), safe="")
    return [
        f"/api/v1/services/instructor-preferences/{safe}",
        f"/api/v1/instructors/{safe}/preferences",
        f"/api/v1/instructor-preferences/{safe}",
    ]


def _extract_item(body) -> dict | None:
    """پشتیبانی از چند شکل پاسخ: {item}, {items:[...]}, خودِ شیء."""
    if not isinstance(body, dict):
        return None
    if isinstance(body.get("item"), dict):
        return body["item"]
    items = body.get("items")
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    if ("subjects" in body) or ("time_slots" in body):
        return body
    return None


def _normalize_item(item: dict) -> dict:
    subjects = []
    for s in item.get("subjects") or []:
        if isinstance(s, dict) and s.get("title"):
            subjects.append({
                "title": str(s["title"]),
                "course_code": str(s.get("course_code") or s.get("code") or ""),
                "weekly_hours": int(s.get("weekly_hours") or s.get("hours") or 4),
                "level": str(s.get("level") or "تخصصی"),
            })
    slots = []
    for t in item.get("time_slots") or item.get("slots") or []:
        if isinstance(t, dict):
            pref = str(t.get("preference") or t.get("level") or "preferred")
            if pref not in PREF_LEVELS:
                pref = "acceptable"
            slots.append({
                "day": str(t.get("day") or ""),
                "start": str(t.get("start") or ""),
                "end": str(t.get("end") or ""),
                "preference": pref,
                "preference_label": PREF_LABELS.get(pref, pref),
            })
    constraints = [str(c) for c in (item.get("constraints") or item.get("notes") or []) if c]
    return {"subjects": subjects, "time_slots": slots, "constraints": constraints}


def _demo_preferences(professor: dict, course_pool: list[dict]) -> dict:
    """نمونهٔ قطعی بر پایهٔ شناسه استاد + درس‌های موجود (بدون شبکه، تکرارپذیر)."""
    seed = _seed_of(professor.get("ext_id") or professor.get("name") or "x")
    pool = course_pool or [{"title": "درس اصلی تخصصی", "code": "GEN101"}]
    n_sub = 2 + (seed % 2)  # ۲ یا ۳ موضوع
    subjects = []
    for i in range(min(n_sub, len(pool))):
        c = pool[(seed >> (i * 3)) % len(pool)]
        subjects.append({
            "title": c["title"],
            "course_code": c.get("code") or "",
            "weekly_hours": (2, 4, 6)[(seed >> (i * 2)) % 3],
            "level": SUBJECT_LEVELS[i % len(SUBJECT_LEVELS)],
        })
    slots = []
    for di in range(len(DAYS)):
        for si, (s, e) in enumerate(SLOTS):
            roll = (seed >> ((di * 4 + si) % 28)) % 10
            if roll >= 7:
                pref = "preferred"
            elif roll >= 4:
                pref = "acceptable"
            else:
                pref = "avoided"
            if pref != "avoided":
                slots.append({"day": DAYS[di], "start": s, "end": e,
                              "preference": pref, "preference_label": PREF_LABELS[pref]})
    return {
        "subjects": subjects,
        "time_slots": slots,
        "constraints": [_DEMO_CONSTRAINTS[seed % len(_DEMO_CONSTRAINTS)],
                        _DEMO_CONSTRAINTS[(seed // 7) % len(_DEMO_CONSTRAINTS)]],
    }


def _course_pool(db: Session, limit: int = 24) -> list[dict]:
    """استخر دانش درس‌ها برای تطبیق مطلوبیات: درس‌های سامانه + دروس یکتای پایه‌یار."""
    pool: dict[str, dict] = {}
    from app.models.courses import Course
    for c in db.query(Course).order_by(Course.title).limit(limit).all():
        pool[_norm(c.title)] = {"title": c.title, "code": c.code}
    for rec in (db.query(PayehyarRecord)
                .filter(PayehyarRecord.domain == "unique-courses",
                        PayehyarRecord.is_deleted == False)  # noqa: E712
                .limit(limit).all()):
        p = rec.payload or {}
        title = p.get("title") or rec.title or ""
        if title and _norm(title) not in pool:
            pool[_norm(title)] = {"title": title, "code": p.get("code") or rec.code or ""}
    return list(pool.values())[: limit * 2]


def _fetch_live(professor: dict, base_url: str | None = None,
                api_key: str | None = None, timeout: int | None = None) -> dict | None:
    """واکشی زنده از درس‌یار۳۶۰؛ در هر خطا None (تماس‌کننده به نمونه برمی‌گردد).

    آرگومان‌های override برای تست/مسیرهای خاص؛ پیش‌فرض از تنظیمات مؤثر
    (دیتابیس > متغیر محیطی > پیش‌فرض کد) خوانده می‌شود."""
    s = get_settings()
    base = (base_url or s.darsyar_base_url or "").rstrip("/")
    if not base:
        return None
    headers = {"Accept": "application/json"}
    key = api_key or s.darsyar_api_key
    if key:
        headers["X-API-Key"] = key
    seconds = float(timeout or s.darsyar_timeout_seconds)
    for path in _candidate_paths(professor.get("ext_id") or ""):
        try:
            resp = httpx.get(base + path, headers=headers,
                             timeout=seconds, follow_redirects=True)
            if resp.status_code != 200:
                continue
            body = resp.json()
            item = _extract_item(body)
            if item:
                return _normalize_item(item)
        except Exception:  # noqa: BLE001 — شبکه/JSON هر خطا → fallback نمونه
            continue
    return None


def _effective_fetch_kwargs(db: Session) -> dict:
    """override های دیتابیس تنظیمات اتصال درس‌یار (فقط مقادیر صریح ذخیره‌شده)."""
    from app.services import darsyar_connection
    eff = darsyar_connection.effective_connection(db)
    kw: dict = {}
    if eff["base_url_source"] == "DB":
        kw["base_url"] = eff["base_url"]
    if eff["key_source"] == "DB":
        kw["api_key"] = eff["api_key"]
    if eff["timeout_source"] == "DB":
        kw["timeout"] = eff["timeout_seconds"]
    return kw


def get_preferences(db: Session, professor: dict, refresh: bool = False) -> dict:
    """مطلوبیات استاد: کش → زنده از درس‌یار → نمونهٔ قطعی. خروجی قرارداد صفحه."""
    ext_id = str(professor.get("ext_id") or "")
    cached = (db.query(DarsyarPreference)
              .filter(DarsyarPreference.professor_ext_id == ext_id).first())
    # SQLite زمان را naive ذخیره می‌کند — برای مقایسه به UTC فرض می‌شود
    fetched_at = cached.fetched_at if cached else None
    if fetched_at is not None and fetched_at.tzinfo is None:
        from datetime import timezone
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    fresh = (fetched_at is not None
             and (utcnow() - fetched_at) < timedelta(hours=CACHE_TTL_HOURS))
    if cached is not None and fresh and not refresh:
        return {"ok": True, "source": cached.source, "cached": True,
                "fetched_at": cached.fetched_at.isoformat() if cached.fetched_at else None,
                "instructor": {"ext_id": ext_id, "name": professor.get("name")},
                **(cached.payload or {})}

    live = _fetch_live(professor, **_effective_fetch_kwargs(db))
    source = "live" if live else "demo"
    data = live or _demo_preferences(professor, _course_pool(db))
    now = utcnow()
    if cached is None:
        cached = DarsyarPreference(professor_ext_id=ext_id,
                                   professor_name=professor.get("name"))
        db.add(cached)
    cached.payload = data
    cached.source = source
    cached.professor_name = professor.get("name")
    cached.fetched_at = now
    cached.content_hash = hashlib.sha256(
        str(sorted((s["title"], s["weekly_hours"]) for s in data["subjects"])).encode()
    ).hexdigest()[:32]
    db.commit()
    message = ("مطلوبیات به‌صورت زنده از درس‌یار۳۶۰ واکشی شد."
               if source == "live" else
               "سرویس درس‌یار۳۶۰ در دسترس/پیکربندی نیست؛ نمونهٔ قطعی توسعه نمایش داده "
               "می‌شود (S360_DARSYAR_BASE_URL و S360_DARSYAR_API_KEY را تنظیم کنید).")
    return {"ok": True, "source": source, "cached": False,
            "fetched_at": now.isoformat(), "message": message,
            "instructor": {"ext_id": ext_id, "name": professor.get("name")},
            **data}


def _match_subject(subject: dict, pool: list[dict]) -> dict | None:
    """تطبیق یک موضوع مطلوب با درس‌های موجود (کد دقیق > نرمال عنوان > شامل)."""
    code = _norm(subject.get("course_code"))
    title = _norm(subject.get("title"))
    if code:
        for c in pool:
            if _norm(c.get("code")) == code:
                return c
    for c in pool:
        if title and _norm(c.get("title")) == title:
            return c
    for c in pool:
        t = _norm(c.get("title"))
        if t and title and (title in t or t in title):
            return c
    return None


def matching_courses(db: Session, payload: dict) -> list[dict]:
    """درس‌های متناسب با مطلوبیات درسی استاد — لینک مستقیم به استودیو تولید محتوا."""
    from app.models.courses import Course
    from app.models.syllabus import SyllabusTopic, SyllabusVersion

    pool = _course_pool(db)
    results: dict[str, dict] = {}
    for subject in payload.get("subjects", []):
        m = _match_subject(subject, pool)
        if not m:
            continue
        key = _norm(m["title"]) or _norm(m.get("code"))
        if key in results:
            results[key]["matched_subjects"].append(subject["title"])
            continue
        course = (db.query(Course).filter(Course.code == (m.get("code") or "")).first()
                  if m.get("code") else None)
        if course is None:
            course = db.query(Course).filter(Course.title == m["title"]).first()
        topics = 0
        if course is not None:
            sv = (db.query(SyllabusVersion)
                  .filter(SyllabusVersion.course_id == course.id)
                  .order_by(SyllabusVersion.created_at.desc()).first())
            if sv is not None:
                topics = (db.query(SyllabusTopic)
                          .filter(SyllabusTopic.syllabus_version_id == sv.id).count())
        results[key] = {
            "course_id": str(course.id) if course else None,
            "title": m["title"],
            "code": m.get("code") or "",
            "matched_subjects": [subject["title"]],
            "weekly_hours": subject.get("weekly_hours"),
            "level": subject.get("level"),
            "syllabus_topics": topics,
            "studio_url": f"/studio/{course.id}" if course else None,
            "has_course": course is not None,
        }
    return list(results.values())


def professor_summary(db: Session, rec: PayehyarRecord) -> dict:
    """خلاصهٔ یک استاد از رکورد پایه‌یار برای کارت صفحهٔ اساتید."""
    p = rec.payload or {}
    name = (p.get("full_name") or p.get("name") or p.get("title")
            or rec.title or "استاد")
    dept = (p.get("department") or p.get("academic_group")
            or p.get("group") or "")
    return {
        "ext_id": rec.external_id,
        "name": name,
        "department": dept,
        "code": p.get("code") or "",
        "email": p.get("email") or "",
        "degree": p.get("degree") or p.get("rank") or "",
        "payload": p,
        "last_synced_at": rec.last_synced_at.isoformat() if rec.last_synced_at else None,
    }


def professors_from_db(db: Session, limit: int = 200) -> list[dict]:
    """فهرست اساتید همگام‌شده از پایه‌یار برای واکشی گروهی مطلوبیات."""
    rows = (db.query(PayehyarRecord)
            .filter(PayehyarRecord.domain == "professors",
                    PayehyarRecord.is_deleted == False)  # noqa: E712
            .order_by(PayehyarRecord.title.is_(None), PayehyarRecord.title)
            .limit(min(500, max(1, limit))).all())
    return [professor_summary(db, r) for r in rows]


def sync_all_preferences(db: Session, refresh: bool = True, limit: int = 100) -> dict:
    """همگام‌سازی گروهی مطلوبیات همهٔ اساتید از درس‌یار۳۶۰.

    هر استاد مستقل واکشی می‌شود؛ شکست هر مورد فقط هشدار است و بقیه ادامه
    می‌یابند. منبع هر رکورد (live/demo) در پاسخ شفاف گزارش می‌شود — مالک داده
    درس‌یار است و اینجا فقط رونوشت همگام‌شده نگه داشته می‌شود."""
    profs = professors_from_db(db, limit=limit)
    if not profs:
        return {"ok": False, "message": "هیچ استادی از پایه‌یار۳۶۰ همگام‌سازی نشده است؛ "
                                        "ابتدا از صفحهٔ «اساتید و مطلوبیات» اساتید را همگام کنید.",
                "total": 0, "live": 0, "demo": 0, "items": []}
    kw = _effective_fetch_kwargs(db)
    items, live_count, demo_count = [], 0, 0
    for prof in profs:
        try:
            payload = get_preferences(db, prof, refresh=refresh)
            source = payload.get("source") or "demo"
            if source == "live":
                live_count += 1
            else:
                demo_count += 1
            items.append({
                "ext_id": prof["ext_id"], "name": prof["name"],
                "department": prof.get("department") or "",
                "source": source,
                "subjects_count": len(payload.get("subjects") or []),
                "time_slots_count": len(payload.get("time_slots") or []),
                "constraints_count": len(payload.get("constraints") or []),
                "fetched_at": payload.get("fetched_at"),
            })
        except Exception as exc:  # noqa: BLE001 — یک استاد نباید همه را بیندازد
            items.append({"ext_id": prof["ext_id"], "name": prof.get("name"),
                          "department": prof.get("department") or "",
                          "source": "error", "error": str(exc)[:160],
                          "subjects_count": 0, "time_slots_count": 0,
                          "constraints_count": 0, "fetched_at": None})
    return {"ok": True,
            "message": f"همگام‌سازی انجام شد: {live_count} استاد زنده از درس‌یار۳۶۰، "
                       f"{demo_count} مورد نمونهٔ قطعی (سرویس در دسترس/پیکربندی نیست).",
            "total": len(items), "live": live_count, "demo": demo_count,
            "items": items}


def preferences_overview(db: Session) -> dict:
    """رونوشت‌های ذخیره‌شدهٔ مطلوبیات برای جدول صفحهٔ درس‌یار۳۶۰."""
    rows = (db.query(DarsyarPreference).order_by(DarsyarPreference.professor_name).all())
    items = []
    for r in rows:
        p = r.payload or {}
        items.append({
            "ext_id": r.professor_ext_id,
            "name": r.professor_name or "استاد",
            "source": r.source,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            "subjects": p.get("subjects") or [],
            "time_slots_count": len(p.get("time_slots") or []),
            "constraints_count": len(p.get("constraints") or []),
            "constraints": p.get("constraints") or [],
        })
    return {"ok": True, "total": len(items), "items": items}
