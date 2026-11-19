"""تست‌های یکپارچه‌سازی با برنامه‌یار۳۶۰ (با سرور mock، بدون شبکه واقعی)."""
import httpx
import pytest

from app.services.programyar import ProgramyarClient, parse_unique_course


def _mock_app_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/auth/login":
        body = request.read()
        assert b"username" in body
        return httpx.Response(200, json={"access_token": "tok123"})
    if request.url.path == "/api/courses/unique":
        if request.headers.get("authorization") == "Bearer tok123":
            return httpx.Response(200, json=[
                {"course_code": "CS101", "course_name": "برنامه‌سازی پایه",
                 "units": "3", "department": "مهندسی کامپیوتر", "term": "نیم‌سال اول"},
                {"code": "MA201", "name": "ریاضی گسسته", "credits": 2},
                {"bad": "record"},
            ])
        return httpx.Response(401, json={"detail": "برای دسترسی به سامانه باید وارد شوید."})
    return httpx.Response(404)


def _mock_client() -> ProgramyarClient:
    return ProgramyarClient(base_url="http://mock", transport=httpx.MockTransport(_mock_app_handler))


def test_parse_unique_course_defensive():
    parsed = parse_unique_course({"course_code": "CS101", "course_name": "برنامه‌سازی پایه", "units": "3"})
    assert parsed["code"] == "CS101"
    assert parsed["title"] == "برنامه‌سازی پایه"
    assert parsed["units"] == 3
    parsed2 = parse_unique_course({"code": "X1", "name": "عنوان"})
    assert parsed2["code"] == "X1" and parsed2["title"] == "عنوان"


def test_fetch_requires_credentials(client, st_headers):
    """واکشی برای دانشجو ممنوع است."""
    r = client.post("/api/v1/integration/programyar/courses", headers=st_headers, json={})
    assert r.status_code == 403


@pytest.fixture()
def mock_programyar(monkeypatch):
    """کلاینت API برنامه‌یار در مسیر endpoint با transport mock جایگزین می‌شود."""
    import app.api.v1.integration as integ

    class MockClient(ProgramyarClient):
        def __init__(self, base_url=None, **kw):
            super().__init__(base_url=base_url, transport=httpx.MockTransport(_mock_app_handler))

    monkeypatch.setattr(integ, "ProgramyarClient", MockClient)


def test_fetch_courses_with_login_flow(client, prof_headers, mock_programyar):
    """لاگین به برنامه‌یار mock و نگاشت درس‌های یکتا."""
    r = client.post("/api/v1/integration/programyar/courses", headers=prof_headers,
                    json={"username": "u", "password": "p"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["reachable"] is True, r.text
    assert data["auth_used"] is True, f"message={data.get('message')} items={data.get('total')}"
    assert data["total"] == 2
    codes = [i["code"] for i in data["items"]]
    assert codes == ["CS101", "MA201"]
    assert data["items"][0]["units"] == 3


def test_import_course_with_topics(client, prof_headers, ctx):
    """ثبت درس + فرم اطلاعات + سرفصل‌ها و اتصال به نسخه سرفصل."""
    payload = {
        "code": "IMP550", "title": "ساختمان داده‌های یکتا",
        "department": "مهندسی کامپیوتر", "credits": 3, "term": "ترم ۱",
        "degree_level": "کارشناسی", "description": "درس واکشی‌شده از برنامه‌یار",
        "prerequisites_note": "پیش‌نیاز: برنامه‌سازی پایه",
        "source_ref": "CS101",
        "topics": [
            {"title": "آرایه‌ها و لیست‌ها", "description": "انواع آرایه و پیاده‌سازی", "suggested_hours": 4},
            {"title": "درخت‌ها", "suggested_hours": 6},
            {"title": "گراف", "description": "پیمایش و الگوریتم‌ها"},
        ],
    }
    r = client.post("/api/v1/integration/programyar/import", headers=prof_headers, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["topics_count"] == 3
    # درس برای استاد واردکننده قابل مشاهده است و سرفصل آن موجود است
    lst = client.get("/api/v1/courses", headers=prof_headers).json()
    assert any(c["code"] == "IMP550" for c in lst)
    sv = client.get(f"/api/v1/syllabus-versions/{data['syllabus_version_id']}", headers=prof_headers).json()
    chapter_titles = [ch["title"] for ch in sv["chapters"]]
    assert "درخت‌ها" in chapter_titles
    # کد تکراری → 409
    r2 = client.post("/api/v1/integration/programyar/import", headers=prof_headers, json=payload)
    assert r2.status_code == 409


def test_import_requires_staff(client, st_headers):
    r = client.post("/api/v1/integration/programyar/import", headers=st_headers,
                    json={"code": "S1", "title": "درس دانشجویی"})
    assert r.status_code == 403


def test_unreachable_service(client, prof_headers):
    """پیام شفاف وقتی مقصد در دسترس نیست."""
    client_bad = ProgramyarClient(base_url="http://127.0.0.1:1", timeout=1.0)
    res = client_bad.get_unique_courses("u", "p")
    assert res["reachable"] is False and res["items"] == []
    assert "دستی" in res["message"]
