"""گزارش جامع سامانه در چهار فرمت PDF / DOCX / HTML / PPTX با نمودارهای فارسی.

آمار کاربران و گردش‌کار تایید، درس‌ها و سرفصل‌ها، محتوا و انتشار، آزمون و
استفاده از هوش مصنوعی — همه با اعداد فارسی و نمودار matplotlib با فونت وزیرمتن.
"""
import base64
import io
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.content import ContentDocument, ContentVersion
from app.models.courses import Course, Enrollment
from app.models.identity import User
from app.models.ops import AIRun, AuditLog, JobRun
from app.models.questions import Question
from app.models.syllabus import SyllabusVersion
from app.models.tutor import TutorMessage, TutorSession
from app.services.export_service import fa

FONTS_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "assets" / "fonts"
PALETTE = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#3b82f6", "#a855f7"]

ROLE_LABELS = {
    "STUDENT": "دانشجو", "PROFESSOR": "استاد", "ASSISTANT": "دستیار آموزشی",
    "GROUP_ADMIN": "مدیرگروه", "EDUCATION_ADMIN": "مدیر آموزشی",
    "QUALITY_REVIEWER": "کارشناس تضمین کیفیت", "TECH_ADMIN": "مدیر فنی",
}
STATUS_LABELS = {
    "DRAFT": "پیش‌نویس", "PENDING_REVIEW": "در انتظار بررسی", "APPROVED": "تایید‌شده",
    "SUPERSEDED": "جایگزین‌شده", "GENERATED": "تولید‌شده", "UNDER_REVIEW": "در حال بررسی",
    "PUBLISHED": "منتشر‌شده", "NEEDS_REVISION": "نیازمند اصلاح", "ACTIVE": "فعال",
    "PENDING": "در انتظار تایید", "REJECTED": "رد‌شده", "SUCCEEDED": "موفق", "FAILED": "ناموفق",
}


def _label(key: str) -> str:
    return STATUS_LABELS.get(key) or ROLE_LABELS.get(key) or key


def collect_stats(db: Session) -> dict:
    """جمع‌آوری آمار کامل سامانه در یک دیکشنری ساختاریافته."""
    users_total = db.query(func.count(User.id)).scalar() or 0
    users_by_role = dict(db.query(User.role, func.count(User.id)).group_by(User.role).all())
    users_by_approval = dict(db.query(User.approval_status, func.count(User.id))
                             .group_by(User.approval_status).all())
    syllabus_by_status = dict(db.query(SyllabusVersion.status, func.count(SyllabusVersion.id))
                              .group_by(SyllabusVersion.status).all())
    versions_by_status = dict(db.query(ContentVersion.status, func.count(ContentVersion.id))
                              .group_by(ContentVersion.status).all())
    jobs_rows = db.query(JobRun.kind, JobRun.status, func.count(JobRun.id)) \
        .group_by(JobRun.kind, JobRun.status).all()
    jobs_by_kind: dict[str, dict] = {}
    for kind, status_, count in jobs_rows:
        item = jobs_by_kind.setdefault(kind, {"total": 0, "SUCCEEDED": 0, "FAILED": 0})
        item["total"] += count
        if status_ in item:
            item[status_] = count
    programyar_imports = db.query(func.count(AuditLog.id)) \
        .filter(AuditLog.action == "COURSE_IMPORT_PROGRAMYAR").scalar() or 0
    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "users": {
            "total": users_total,
            "by_role": users_by_role,
            "by_approval": users_by_approval,
            "pending_approvals": users_by_approval.get("PENDING", 0),
        },
        "courses": {
            "total": db.query(func.count(Course.id)).scalar() or 0,
            "enrollments": db.query(func.count(Enrollment.id)).scalar() or 0,
        },
        "syllabus": {
            "versions": dict((_label(k), v) for k, v in syllabus_by_status.items()),
        },
        "content": {
            "documents": db.query(func.count(ContentDocument.id)).scalar() or 0,
            "versions": dict((_label(k), v) for k, v in versions_by_status.items()),
            "published": versions_by_status.get("PUBLISHED", 0),
        },
        "ai": {
            "questions": db.query(func.count(Question.id)).scalar() or 0,
            "tutor_sessions": db.query(func.count(TutorSession.id)).scalar() or 0,
            "tutor_messages": db.query(func.count(TutorMessage.id)).scalar() or 0,
            "ai_runs": db.query(func.count(AIRun.id)).scalar() or 0,
            "jobs_by_kind": jobs_by_kind,
            "programyar_imports": programyar_imports,
        },
    }


def _setup_matplotlib():
    import matplotlib.font_manager as fm
    import matplotlib
    matplotlib.use("Agg")
    for name in ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf"):
        fm.fontManager.addfont(str(FONTS_DIR / name))
    fm.fontManager.addfont("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Vazirmatn", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _fa_chart(text: str) -> str:
    """شکل‌دهی حروف فارسی برای matplotlib."""
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(text))


def _render_chart(title: str, pairs: list[tuple[str, int]]) -> bytes:
    plt = _setup_matplotlib()
    fig, ax = plt.subplots(figsize=(7.0, 3.2), constrained_layout=True)
    labels = [_fa_chart(_label(l) if len(l) < 24 else l) for l, _ in pairs][::-1]
    values = [v for _, v in pairs][::-1]
    colors = (PALETTE * 3)[:len(values)][::-1]
    bars = ax.barh(labels, values, color=colors, height=0.62)
    ax.bar_label(bars, padding=4, fontsize=10)
    ax.set_title(_fa_chart(title), fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=10)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def build_charts(stats: dict) -> list[tuple[str, bytes]]:
    charts = []
    roles = sorted(stats["users"]["by_role"].items(), key=lambda x: -x[1])
    if roles:
        charts.append(("کاربران سامانه به تفکیک نقش", _render_chart("کاربران سامانه به تفکیک نقش", roles)))
    approvals = sorted(stats["users"]["by_approval"].items())
    if approvals:
        charts.append(("وضعیت حساب‌های کاربری", _render_chart("وضعیت حساب‌های کاربری", approvals)))
    jobs = sorted(((k, v["total"]) for k, v in stats["ai"]["jobs_by_kind"].items()),
                  key=lambda x: -x[1])[:8]
    if jobs:
        charts.append(("حجم اجرای فرایندهای هوش مصنوعی", _render_chart("حجم اجرای فرایندهای هوش مصنوعی", jobs)))
    versions = sorted(stats["content"]["versions"].items())
    if versions:
        charts.append(("نسخه‌های محتوا به تفکیک وضعیت", _render_chart("نسخه‌های محتوا به تفکیک وضعیت", versions)))
    return charts


def _table_rows(stats: dict) -> list[tuple[str, list[tuple[str, int]]]]:
    s = stats
    return [
        ("کاربران", [("جمع کل", s["users"]["total"])]
         + [(ROLE_LABELS.get(k, k), v) for k, v in sorted(s["users"]["by_role"].items())]
         + [("در انتظار تایید", s["users"]["pending_approvals"])])
        ,
        ("درس‌ها", [("تعداد درس‌ها", s["courses"]["total"]),
                    ("ثبت‌نام‌ها", s["courses"]["enrollments"])]),
        ("محتوا", [("اسناد آموزشی", s["content"]["documents"]),
                   ("نسخه منتشر‌شده", s["content"]["published"])]
         + [(k, v) for k, v in sorted(s["content"]["versions"].items()) if k != "منتشر‌شده"]),
        ("هوش مصنوعی", [("سوالات بانک سوال", s["ai"]["questions"]),
                        ("جلسات استاد هوشمند", s["ai"]["tutor_sessions"]),
                        ("پیام‌های استاد هوشمند", s["ai"]["tutor_messages"]),
                        ("واردات از برنامه‌یار۳۶۰", s["ai"]["programyar_imports"])]),
    ]


def render_html(stats: dict, charts: list[tuple[str, bytes]]) -> bytes:
    rows_html = ""
    for section, rows in _table_rows(stats):
        cells = "".join(f"<tr><td>{fa(str(k))}</td><td>{fa(str(v))}</td></tr>" for k, v in rows)
        rows_html += f'<div class="card"><h3>{fa(section)}</h3><table>{cells}</table></div>'
    imgs = "".join(
        f'<div class="card"><h3>{fa(t)}</h3><img src="data:image/png;base64,{base64.b64encode(b).decode()}"/></div>'
        for t, b in charts)
    html = f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>گزارش جامع سامانه</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css">
<style>
body{{font-family:Vazirmatn,Tahoma,sans-serif;background:#f4f5fb;color:#1e2235;margin:0;padding:26px}}
h1{{text-align:center;color:#4338ca}} .meta{{text-align:center;color:#6b7280;font-size:.85rem;margin-bottom:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;max-width:1000px;margin:0 auto}}
.card{{background:#fff;border:1px solid #e6e8f2;border-radius:14px;padding:14px 16px;box-shadow:0 2px 10px rgba(30,27,75,.06)}}
.card h3{{margin:0 0 10px;color:#4f46e5}} table{{width:100%;border-collapse:collapse;font-size:.9rem}}
td{{padding:6px 8px;border-bottom:1px dashed #e6e8f2}} td:last-child{{text-align:left;font-weight:700}}
img{{width:100%;height:auto}}
</style></head><body>
<h1>📊 گزارش جامع سامانه یادگیری هوشمند</h1>
<div class="meta">تاریخ تولید: {fa(stats["generated_at"])} — دانشجو۳۶۰</div>
<div class="grid">{imgs}{rows_html}</div>
</body></html>"""
    return html.encode("utf-8")


def render_pdf(stats: dict, charts: list[tuple[str, bytes]]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)
    pdfmetrics.registerFont(TTFont("Vazir", str(FONTS_DIR / "Vazirmatn-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Vazir-Bold", str(FONTS_DIR / "Vazirmatn-Bold.ttf")))
    title_style = ParagraphStyle("t", fontName="Vazir-Bold", fontSize=16, alignment=1,
                                 textColor=colors.HexColor("#4338ca"))
    h_style = ParagraphStyle("h", fontName="Vazir-Bold", fontSize=12, textColor=colors.HexColor("#4f46e5"))
    cell = ParagraphStyle("c", fontName="Vazir", fontSize=10)
    cell_b = ParagraphStyle("cb", fontName="Vazir-Bold", fontSize=10, alignment=2)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm)
    story = [Paragraph("گزارش جامع سامانه یادگیری هوشمند", title_style),
             Spacer(1, 4), Paragraph(f"تاریخ تولید: {fa(stats['generated_at'])} — دانشجو۳۶۰",
                                     ParagraphStyle("m", fontName="Vazir", fontSize=9, alignment=1,
                                                    textColor=colors.HexColor("#6b7280"))),
             Spacer(1, 12)]
    for section, rows in _table_rows(stats):
        story.append(Paragraph(fa(section), h_style))
        data = [[Paragraph(fa(str(k)), cell), Paragraph(fa(str(v)), cell_b)] for k, v in rows]
        t = Table(data, colWidths=[110 * mm, 50 * mm], hAlign="CENTER")
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e6e8f2")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f7f8ff")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([t, Spacer(1, 10)])
    for title, png in charts:
        story.append(Paragraph(fa(title), h_style))
        img = Image(io.BytesIO(png), width=160 * mm, height=73 * mm)
        story.extend([img, Spacer(1, 10)])
    doc.build(story)
    return buf.getvalue()


def render_docx(stats: dict, charts: list[tuple[str, bytes]]) -> bytes:
    from docx import Document
    from docx.shared import Inches
    doc = Document()
    doc.add_heading("گزارش جامع سامانه یادگیری هوشمند", level=0)
    p = doc.add_paragraph(f"تاریخ تولید: {stats['generated_at']} — دانشجو۳۶۰")
    p.runs[0].font.name = "Vazirmatn"
    for section, rows in _table_rows(stats):
        doc.add_heading(section, level=1)
        table = doc.add_table(rows=0, cols=2)
        table.style = "Light Grid Accent 1"
        for k, v in rows:
            cells = table.add_row().cells
            cells[0].text = f"{k}"
            cells[1].text = f"{v}"
    for title, png in charts:
        doc.add_heading(title, level=1)
        doc.add_picture(io.BytesIO(png), width=Inches(6.0))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_pptx(stats: dict, charts: list[tuple[str, bytes]]) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "گزارش جامع سامانه یادگیری هوشمند"
    slide.placeholders[1].text = f"دانشجو۳۶۰ — {stats['generated_at']}"
    for section, rows in _table_rows(stats):
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = section
        body = s.placeholders[1].text_frame
        lines = [f"{k}: {v}" for k, v in rows[:10]]
        body.text = lines[0] if lines else ""
        for line in lines[1:]:
            body.add_paragraph().text = line
            body.paragraphs[-1].font.size = Pt(16)
    for title, png in charts:
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = title
        s.shapes.add_picture(io.BytesIO(png), Inches(1.2), Inches(1.6), width=Inches(7.5))
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


FORMATS = ("pdf", "docx", "html", "pptx")


def build_report(db: Session, fmt: str) -> tuple[bytes, str, str]:
    fmt = (fmt or "").lower().strip(".")
    if fmt not in FORMATS:
        raise ValueError(f"فرمت پشتیبانی‌نشده: {fmt}")
    stats = collect_stats(db)
    charts = build_charts(stats)
    renderer = {"html": render_html, "pdf": render_pdf,
                "docx": render_docx, "pptx": render_pptx}[fmt]
    content = renderer(stats, charts)
    media = {"html": "text/html", "pdf": "application/pdf",
             "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}[fmt]
    return content, f"smart-learning-report.{fmt}", media
