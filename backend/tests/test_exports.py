"""AC-04 / AC-11: خروجی‌های چندقالب فارسی و امنیت HTML."""
import time


def _make_published_version(client, ctx, prof_headers, title="سند خروجی"):
    doc = client.post("/api/v1/content-documents", headers=prof_headers, json={
        "course_id": ctx["course_id"], "syllabus_version_id": ctx["syllabus_version_id"],
        "title": title, "scope": {"concept_ids": [ctx["base_concept"]]},
        "source_resource_ids": [ctx["resource_id"]],
    }).json()
    job = client.post(f"/api/v1/content-documents/{doc['id']}/generation-jobs",
                      headers=prof_headers, json={"mode": "FULL"}).json()
    for _ in range(40):
        j = client.get(f"/api/v1/jobs/{job['job_id']}", headers=prof_headers).json()
        if j["status"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.2)
    vid = j["result"]["content_version_id"]
    client.post(f"/api/v1/content-versions/{vid}/reviews", headers=prof_headers,
                json={"decision": "APPROVE"})
    client.post(f"/api/v1/content-versions/{vid}/publish", headers=prof_headers)
    return vid


def _export(client, prof_headers, vid, fmt):
    resp = client.post(f"/api/v1/content-versions/{vid}/exports", headers=prof_headers,
                       json={"format": fmt})
    assert resp.status_code == 202, resp.text
    for _ in range(40):
        j = client.get(f"/api/v1/jobs/{resp.json()['job_id']}", headers=prof_headers).json()
        if j["status"] in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.2)
    assert j["status"] == "SUCCEEDED", j.get("error")
    export_job_id = j["result"]["export_job_id"]
    dl = client.get(f"/api/v1/exports/{export_job_id}/download", headers=prof_headers)
    assert dl.status_code == 200
    return dl


def test_pdf_export_persian(client, ctx, prof_headers):
    """AC-04: PDF فارسی با فونت جاسازی‌شده و متن قابل استخراج."""
    vid = _make_published_version(client, ctx, prof_headers, "سند PDF")
    dl = _export(client, prof_headers, vid, "PDF")
    assert dl.content[:5] == b"%PDF-" and len(dl.content) > 20000
    import io

    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(dl.content))
    text = "".join(page.extract_text() or "" for page in reader.pages)
    assert len(text) > 100  # متن قابل استخراج (نه تصویر)
    fonts = set()
    for page in reader.pages:
        res = page.get("/Resources") or {}
        for f in (res.get("/Font") or {}).values():
            fonts.add(str(f.get_object().get("/BaseFont", "")))
    assert any("Vazirmatn" in f for f in fonts), f"فونت فارسی جاسازی نشده: {fonts}"


def test_pptx_export_editable(client, ctx, prof_headers):
    """AC-04: PPTX با اسلاید، یادداشت مدرس و متن قابل ویرایش."""
    vid = _make_published_version(client, ctx, prof_headers, "سند اسلاید")
    dl = _export(client, prof_headers, vid, "PPTX")
    assert dl.content[:2] == b"PK"  # zip container
    import io

    from pptx import Presentation

    prs = Presentation(io.BytesIO(dl.content))
    assert len(prs.slides) >= 5
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
        if slide.has_notes_slide:
            texts.append(slide.notes_slide.notes_text_frame.text)
    joined = " ".join(texts)
    assert len(joined) > 200  # متن زنده و قابل ویرایش (نه تصویر)


def test_html_export_safe_and_rtl(client, ctx, prof_headers):
    """AC-11: HTML واکنش‌گرا با CSP و بدون اجرای کد ناامن."""
    vid = _make_published_version(client, ctx, prof_headers, "سند HTML")
    # تزریق محتوای ناامن توسط استاد
    version = client.get(f"/api/v1/content-versions/{vid}", headers=prof_headers).json()
    first_text = next(b for b in version["blocks"] if b["type"] == "text")
    patched = client.patch(f"/api/v1/content-versions/{vid}/blocks/{first_text['id']}",
                           headers=prof_headers,
                           json={"patch": {"body": "متنی سالم <script>alert(1)</script> و <img src=x onerror=alert(2)>"},
                                 "expected_revision": version["revision"]})
    assert patched.status_code == 200
    dl = _export(client, prof_headers, vid, "HTML")
    html = dl.content.decode("utf-8")
    assert "<script>alert(1)</script>" not in html  # escape شده
    assert "onerror=alert(2)" not in html
    assert "Content-Security-Policy" in html
    assert 'dir="rtl"' in html
    assert "viewport" in html


def test_docx_export(client, ctx, prof_headers):
    vid = _make_published_version(client, ctx, prof_headers, "سند Word")
    dl = _export(client, prof_headers, vid, "DOCX")
    assert dl.content[:2] == b"PK"
    import io

    from docx import Document

    doc = Document(io.BytesIO(dl.content))
    assert len(doc.paragraphs) > 10


def test_student_cannot_export(client, ctx, prof_headers, st_headers):
    vid = _make_published_version(client, ctx, prof_headers, "سند مجوز خروجی")
    r = client.post(f"/api/v1/content-versions/{vid}/exports", headers=st_headers,
                    json={"format": "PDF"})
    assert r.status_code == 403
