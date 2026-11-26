"""تست‌های «برنامهٔ ترم جاری» از برنامه‌یار۳۶۰ (با سرور mock، بدون شبکه واقعی) — v3.9.0.

تصمیم محصول: از برنامه‌یار۳۶۰ فقط برنامهٔ ترم جاری متناسب با استاد مصرف می‌شود؛
دروس یکتا/سرفصل‌ها از پایه‌یار۳۶۰ می‌آیند — endpointهای قدیمی واردات حذف شده‌اند.
"""
import httpx
import pytest

from app.services.programyar import (ProgramyarClient, current_term_label,
                                     demo_schedule, extract_schedule_rows,
                                     parse_schedule_row)


def _mock_app_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/auth/login":
        return httpx.Response(200, json={"access_token": "tok123"})
    if request.url.path == "/api/schedules":
        if request.headers.get("authorization") == "Bearer tok123":
            return httpx.Response(200, json={"items": [
                {"course_title": "برنامه‌سازی پایه", "course_code": "CS101",
                 "day": "شنبه", "start": "۸:۰۰", "end": "۹:۳۰",
                 "group": "گروه ۱", "place": "کلاس ۱۰۱"},
                {"title": "ریاضی گسسته", "weekday": "دوشنبه",
                 "start_time": "۱۰:۰۰", "end_time": "۱۱:۳۰", "room": "کلاس ۲۰۳"},
                {"bad": "record"},
            ]})
        return httpx.Response(401, json={"detail": "برای دسترسی باید وارد شوید."})
    return httpx.Response(404)


def _mock_client() -> ProgramyarClient:
    return ProgramyarClient(base_url="http://mock",
                            transport=httpx.MockTransport(_mock_app_handler))


def test_parse_schedule_row_defensive():
    row = parse_schedule_row({"course_name": "شبکه", "weekday": "دوشنبه",
                              "start_time": "۸:۰۰", "end_time": "۹:۳۰", "room": "کلاس ۲"})
    assert row["course_title"] == "شبکه" and row["day"] == "دوشنبه"
    assert row["start"] == "۸:۰۰" and row["place"] == "کلاس ۲"
    assert parse_schedule_row({"day": "شنبه"}) is None  # بدون عنوان درس
    assert parse_schedule_row("not-dict") is None


def test_extract_schedule_rows_shapes():
    rows = extract_schedule_rows([{"course_title": "الف", "day": "شنبه"}])
    assert len(rows) == 1
    rows2 = extract_schedule_rows({"days": {"دوشنبه": [{"course_title": "ب"}]}})
    assert rows2 and rows2[0]["day"] == "دوشنبه"
    assert extract_schedule_rows(None) == []


def test_current_term_label_seasons():
    from datetime import datetime
    assert "نیم‌سال اول" in current_term_label(datetime(2026, 11, 26))
    assert "نیم‌سال اول" in current_term_label(datetime(2026, 3, 15))   # اسفند
    assert "نیم‌سال دوم" in current_term_label(datetime(2026, 5, 1))    # اردیبهشت
    assert "تابستان" in current_term_label(datetime(2026, 7, 10))       # تیر
    # ارقام فارسی
    assert "۱۴۰۵" in current_term_label(datetime(2026, 11, 26))


def test_demo_schedule_deterministic():
    prof = {"ext_id": "P-1", "name": "دکتر تست"}
    pool = [{"title": "ریاضیات گسسته", "code": "MA201"}]
    d1 = demo_schedule(prof, pool)
    d2 = demo_schedule(prof, pool)
    assert d1["entries"] == d2["entries"]  # قطعی/تکرارپذیر
    assert d1["term"] == current_term_label()
    for e in d1["entries"]:
        assert e["day"] in ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه")
        assert e["course_title"]


def test_client_live_schedule_with_login():
    """واکشی زندهٔ برنامهٔ ترم جاری با جریان لاگین به برنامه‌یار mock."""
    res = _mock_client().fetch_schedule("P-1", username="u", password="p")
    assert res is not None
    titles = {e["course_title"] for e in res["entries"]}
    assert "برنامه‌سازی پایه" in titles and "ریاضی گسسته" in titles
    assert res["entries"][0]["group"] == "گروه ۱"  # نگاشت defensive


def test_client_without_credentials_falls_back():
    """سرویس احراز هویت خواست اما اعتباری پیکربندی نشده → None (نمونه در UI)."""
    res = _mock_client().fetch_schedule("P-1")
    assert res is None


def test_client_unreachable_returns_none():
    res = ProgramyarClient(base_url="http://127.0.0.1:1", timeout=1.0).fetch_schedule("P-1")
    assert res is None


def test_schedule_requires_staff(client, st_headers):
    """برنامهٔ ترم برای دانشجو ممنوع است."""
    r = client.get("/api/v1/integration/programyar/schedule", headers=st_headers)
    assert r.status_code == 403


def test_schedule_endpoint_demo_fallback(client, prof_headers, ctx):
    """سرویس در دسترس نیست → نمونهٔ قطعی با برچسب شفاف + ترم جاری."""
    r = client.get("/api/v1/integration/programyar/schedule", headers=prof_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["source"] == "demo"
    assert "نمونهٔ قطعی" in data["message"]
    assert data["term"] == current_term_label()
    assert data["professor"]["ext_id"]  # خودِ استاد یا جانشین
    assert isinstance(data["entries"], list)
    assert data["days"][0] == "شنبه"


@pytest.fixture()
def mock_programyar(monkeypatch):
    """کلاینت API برنامه‌یار در مسیر endpoint با transport mock جایگزین می‌شود
    و اعتبارنامهٔ سامانهٔ مقصد در تنظیمات تزریق می‌گردد."""
    import app.api.v1.integration as integ
    from app.core.config import get_settings

    class MockClient(ProgramyarClient):
        def __init__(self, base_url=None, **kw):
            super().__init__(base_url=base_url,
                             transport=httpx.MockTransport(_mock_app_handler))

    monkeypatch.setattr(integ, "ProgramyarClient", MockClient)
    s = get_settings()
    monkeypatch.setattr(s, "programyar_username", "u", raising=False)
    monkeypatch.setattr(s, "programyar_password", "p", raising=False)


def test_schedule_endpoint_live(client, prof_headers, ctx, mock_programyar):
    """مسیر زندهٔ endpoint با کلاینت mock."""
    r = client.get("/api/v1/integration/programyar/schedule?refresh=true",
                   headers=prof_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["source"] == "live"
    assert data["total_weekly_hours"] >= 3  # ۲ جلسه × ۱٫۵ ساعت
    assert any(e["course_title"] == "برنامه‌سازی پایه" for e in data["entries"])


def test_status_endpoint(client, prof_headers):
    r = client.get("/api/v1/integration/programyar/status", headers=prof_headers)
    assert r.status_code == 200
    data = r.json()
    assert "base_url" in data and "scope" in data
