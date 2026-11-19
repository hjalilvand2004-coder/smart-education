"""خط تولید خروجی: تبدیل کنترل‌شده محتوای ساختاریافته مرجع به PDF / PPTX / HTML / DOCX.

- یک محتوای ساختاریافته مرجع، چند قالب خروجی (بخش ۴.۳).
- PDF: ReportLab با فونت جاسازی‌شده فارسی (Vazirmatn) و شکل‌دهی صحیح حروف.
- PPTX: python-pptx با نسبت ۱۶:۹، یادداشت مدرس و متن قابل ویرایش.
- HTML: راست‌به‌چپ، واکنش‌گرا، فرمول با KaTeX و پاک‌سازی محتوا (AC-11).
- DOCX: python-docx با سبک RTL دانشگاهی.
"""
import html as html_module
import re
from datetime import datetime
from pathlib import Path

from app.core.database import utcnow

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
TEMPLATE_VERSION = "v1.0"


def latex_to_plain(expr: str | None) -> str:
    """تبدیل ساده LaTeX به متن قابل نمایش در PDF/PPTX/DOCX."""
    if not expr:
        return ""
    s = expr
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1) / (\2)", s)
    s = s.replace("\\lim", "lim").replace("\\to", "→").replace("\\cdot", "·").replace("\\circ", "∘")
    s = s.replace("\\left", "").replace("\\right", "").replace("\\,", " ")
    return s


def fa(text: str | None) -> str:
    """آماده‌سازی متن فارسی برای موتورهای PDF راست‌به‌چپ (شکل‌دهی + ترتیب دوسویه)."""
    if not text:
        return ""
    import arabic_reshaper
    from bidi.algorithm import get_display

    return get_display(arabic_reshaper.reshape(str(text)))


def _block_text(b: dict) -> str:
    parts = [b.get("title") or "", b.get("body") or "", b.get("question") or ""]
    parts += [str(i) for i in (b.get("items") or [])]
    parts += [str(s) for s in (b.get("steps") or [])]
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------- HTML

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ meta.document_title }}</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self' https://cdn.jsdelivr.net; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:;">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css">
<style>
  :root { --ink:#1f2937; --brand:#2563eb; --soft:#f3f4f6; --line:#e5e7eb; }
  * { box-sizing: border-box; }
  body { font-family: Vazirmatn, "Segoe UI", Tahoma, sans-serif; color:var(--ink);
         margin:0; background:#f8fafc; line-height:1.9; }
  .page { max-width: 860px; margin: 0 auto; padding: clamp(16px, 4vw, 48px); background:#fff; }
  header.cover { border-bottom: 3px solid var(--brand); padding-bottom: 24px; margin-bottom: 28px; }
  h1 { font-size: clamp(1.4rem, 4vw, 2rem); margin: 0 0 8px; color: var(--brand); }
  .meta { color:#6b7280; font-size: .9rem; }
  .block { margin: 22px 0; padding: 14px 18px; border: 1px solid var(--line); border-radius: 12px; background:#fff; }
  .block.heading { background: var(--soft); border: 0; border-right: 4px solid var(--brand); }
  .block.definition { background:#eff6ff; border-color:#bfdbfe; }
  .block.note { background:#fffbeb; border-color:#fde68a; }
  .block.worked_example { background:#f0fdf4; border-color:#bbf7d0; }
  .block.exercise { background:#fdf2f8; border-color:#fbcfe8; }
  .block.self_check { background:#f5f3ff; border-color:#ddd6fe; }
  .block.summary { background:var(--soft); }
  .block h3 { margin: 4px 0 10px; font-size: 1.05rem; }
  ol.steps, ul.items { padding-right: 1.4rem; padding-left: 0; margin: 8px 0; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; }
  th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: right; }
  th { background: var(--soft); }
  .formula { direction: ltr; text-align: center; font-size: 1.1rem; background: var(--soft);
             padding: 12px; border-radius: 8px; overflow-x: auto; }
  code, pre { direction: ltr; font-family: monospace; background:#0f172a; color:#e2e8f0; padding: 2px 6px; border-radius: 6px; }
  pre { padding: 14px; overflow-x: auto; }
  .answer { color:#166534; }
  .citations { font-size: .82rem; color:#6b7280; margin-top: 6px; }
  footer { margin-top: 40px; border-top: 1px solid var(--line); padding-top: 12px;
           color:#9ca3af; font-size: .8rem; }
  @media print {
    body { background:#fff; }
    .block { break-inside: avoid; border-color: #ddd; }
    .page { max-width: none; padding: 0; }
  }
</style>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body,{delimiters:[{left:'$$',right:'$$',display:true}]});"></script>
</head>
<body>
<div class="page">
  <header class="cover">
    <h1>{{ meta.document_title }}</h1>
    <div class="meta">درس: {{ meta.course_title }} ({{ meta.course_code }})
      | استاد: {{ meta.professor }}
      | نسخه محتوا: {{ meta.version_number }}
      | نسخه سرفصل: {{ meta.syllabus_version_number }}
      | تاریخ تولید: {{ meta.generated_at }}</div>
  </header>
{% for b in blocks %}
  {% if b.type == 'heading' %}
  <div class="block heading"><h2>{{ b.title }}</h2>{% if b.body %}<p>{{ b.body }}</p>{% endif %}</div>
  {% elif b.type == 'formula' %}
  <div class="block"><div class="formula">$${{ b.formula }}$$</div></div>
  {% elif b.type == 'table' %}
  <div class="block">
    {% if b.title %}<h3>{{ b.title }}</h3>{% endif %}
    <table><thead><tr>{% for c in b.columns %}<th>{{ c }}</th>{% endfor %}</tr></thead>
    <tbody>{% for r in b.rows %}<tr>{% for cell in r %}<td>{{ cell }}</td>{% endfor %}</tr>{% endfor %}</tbody></table>
  </div>
  {% elif b.type == 'worked_example' %}
  <div class="block worked_example"><h3>{{ b.title }}</h3>
    <p>{{ b.question }}</p>
    <ol class="steps">{% for s in b.steps %}<li>{{ s }}</li>{% endfor %}</ol>
  </div>
  {% elif b.type == 'exercise' %}
  <div class="block exercise"><h3>{{ b.title }}</h3><p>{{ b.question }}</p>
    {% if b['items'] %}<ul class="items">{% for i in b['items'] %}<li>{{ i }}</li>{% endfor %}</ul>{% endif %}
  </div>
  {% elif b.type == 'self_check' %}
  <div class="block self_check"><h3>{{ b.title }}</h3><p>{{ b.question }}</p>
    {% if b.answer %}<p class="answer">پاسخ: {{ b.answer }}</p>{% endif %}
    {% if b.explanation %}<p class="citations">{{ b.explanation }}</p>{% endif %}
  </div>
  {% elif b.type == 'code' %}
  <div class="block">{% if b.title %}<h3>{{ b.title }}</h3>{% endif %}
    <pre><code>{{ b.body }}</code></pre>
  </div>
  {% elif b.type == 'image' %}
  <div class="block"><h3>{{ b.title }}</h3><p>{{ b.body }}</p><p class="citations">[تصویر: {{ b.formula }}]</p></div>
  {% elif b.type in ('text', 'definition', 'note', 'summary', 'reference') %}
  <div class="block {{ b.type }}">{% if b.title %}<h3>{{ b.title }}</h3>{% endif %}
    {% if b.body %}<p>{{ b.body }}</p>{% endif %}
    {% if b['items'] %}<ul class="items">{% for i in b['items'] %}<li>{{ i }}</li>{% endfor %}</ul>{% endif %}
  </div>
  {% endif %}
{% endfor %}
  <footer>سامانه سرویس‌های یادگیری هوشمند دانشجو۳۶۰ — این سند از نسخه تأییدشده محتوا تولید شده است.</footer>
</div>
</body></html>"""


def render_html(blocks: list[dict], meta: dict) -> bytes:
    """Pاک‌سازی: متن‌ها با Jinja autoescape فرار داده می‌شوند؛ ساختار خودمان می‌سازیم."""
    from jinja2 import Template

    # نرمال‌سازی بلوک‌ها برای جلوگیری از برخورد Jinja با متد dict.items
    safe_blocks = []
    for b in blocks:
        nb = dict(b)
        for field in ("items", "steps", "columns", "rows"):
            nb[field] = nb.get(field) or []
        nb.setdefault("title", "")
        safe_blocks.append(nb)
    tpl = Template(HTML_TEMPLATE, autoescape=True)
    html_out = tpl.render(blocks=safe_blocks, meta=meta)
    return html_out.encode("utf-8")


# ---------------------------------------------------------------- PDF

def render_pdf(blocks: list[dict], meta: dict, options: dict | None = None) -> bytes:
    import io

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether,
                                    PageTemplate, Paragraph, Spacer, Table, TableStyle)

    pdfmetrics.registerFont(TTFont("Vazir", str(FONTS_DIR / "Vazirmatn-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Vazir-Bold", str(FONTS_DIR / "Vazirmatn-Bold.ttf")))

    body_style = ParagraphStyle("body", fontName="Vazir", fontSize=11, leading=19,
                                alignment=TA_RIGHT, wordWrap="RTL")
    h2 = ParagraphStyle("h2", parent=body_style, fontName="Vazir-Bold", fontSize=16, leading=24,
                        textColor=colors.HexColor("#1d4ed8"), spaceBefore=10, spaceAfter=6)
    h3 = ParagraphStyle("h3", parent=body_style, fontName="Vazir-Bold", fontSize=13, leading=20,
                        spaceBefore=8, spaceAfter=4)
    cover_title = ParagraphStyle("cover", parent=body_style, fontName="Vazir-Bold",
                                 fontSize=24, leading=36, alignment=TA_CENTER)
    cover_meta = ParagraphStyle("cmeta", parent=body_style, fontSize=12, leading=22,
                                alignment=TA_CENTER, textColor=colors.HexColor("#4b5563"))
    box_style = ParagraphStyle("box", parent=body_style, backColor=colors.HexColor("#f3f4f6"),
                               borderColor=colors.HexColor("#d1d5db"), borderWidth=0.7,
                               borderPadding=8, borderRadius=6, spaceAfter=8)
    note_style = ParagraphStyle("note", parent=body_style, textColor=colors.HexColor("#92400e"),
                                backColor=colors.HexColor("#fffbeb"), borderColor=colors.HexColor("#fde68a"),
                                borderWidth=0.7, borderPadding=8, spaceAfter=8)

    options = options or {}
    skip_first_page_number = bool(options.get("skip_first_page_number", True))

    buf = io.BytesIO()

    def on_page(canvas, doc_):
        page_num = canvas.getPageNumber()
        if page_num == 1 and skip_first_page_number:
            return
        canvas.saveState()
        canvas.setFont("Vazir", 9)
        canvas.drawCentredString(A4[0] / 2, 12 * mm, fa(f"صفحه {page_num}"))
        canvas.restoreState()

    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title=meta.get("document_title", ""))
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=on_page)])

    story = []
    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph(fa(meta.get("document_title", "")), cover_title))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(fa(f"درس: {meta.get('course_title', '')} ({meta.get('course_code', '')})"), cover_meta))
    story.append(Paragraph(fa(f"استاد: {meta.get('professor', '')}"), cover_meta))
    story.append(Paragraph(fa(f"نسخه محتوا: {meta.get('version_number', '')} — نسخه سرفصل: {meta.get('syllabus_version_number', '')}"), cover_meta))
    story.append(Paragraph(fa(f"تاریخ تولید: {meta.get('generated_at', '')}"), cover_meta))
    story.append(Spacer(1, 30 * mm))
    # فهرست ساده
    headings = [b for b in blocks if b.get("type") == "heading"]
    if headings:
        story.append(Paragraph(fa("فهرست"), h2))
        for hb in headings:
            story.append(Paragraph(fa("• " + (hb.get("title") or "")), body_style))
    from reportlab.platypus import PageBreak

    story.append(PageBreak())

    def add_bullets(items, style):
        for it in items:
            story.append(Paragraph(fa("– " + str(it)), style))

    for b in blocks:
        t = b.get("type")
        title = fa(b.get("title") or "")
        if t == "heading":
            story.append(Paragraph(title, h2))
        elif t in ("text", "definition", "summary", "reference"):
            if title:
                story.append(Paragraph(title, h3))
            if b.get("body"):
                story.append(Paragraph(fa(b["body"]), box_style))
            if b.get("items"):
                add_bullets(b["items"], body_style)
        elif t == "note":
            story.append(Paragraph(fa(f"{b.get('title') or 'نکته'}: {b.get('body') or ''}"), note_style))
        elif t == "worked_example":
            elems = [Paragraph(fa(f"مثال حل‌شده: {b.get('question') or ''}"), h3)]
            for i, s in enumerate(b.get("steps") or []):
                elems.append(Paragraph(fa(f"گام {to_fa_digits(i + 1)}: {s}"), body_style))
            story.append(KeepTogether(elems))
        elif t == "exercise":
            elems = [Paragraph(fa(f"تمرین: {b.get('question') or ''}"), h3)]
            add_bullets(b.get("items") or [], body_style)
            story.append(KeepTogether(elems))
        elif t == "self_check":
            elems = [Paragraph(fa("خودارزیابی: " + (b.get("question") or "")), box_style),
                     Paragraph(fa("پاسخ: " + (b.get("answer") or "")), body_style)]
            story.append(KeepTogether(elems))
        elif t == "formula":
            story.append(Paragraph(fa(latex_to_plain(b.get("formula"))), box_style))
        elif t == "code":
            story.append(Paragraph("<font name='Courier' size='9'>"
                                   + html_module.escape(b.get("body") or "") + "</font>", box_style))
        elif t == "table":
            cell_style = ParagraphStyle("cell", parent=body_style, fontName="Vazir",
                                        fontSize=9, leading=14, wordWrap="RTL")
            head_style = ParagraphStyle("cellh", parent=cell_style, fontName="Vazir-Bold")
            cols = b.get("columns") or []
            rows = b.get("rows") or []
            data = [[Paragraph(fa(str(c)), head_style) for c in reversed(cols)]] + \
                   [[Paragraph(fa(str(cell)), cell_style) for cell in reversed(r)] for r in rows]
            tbl = Table(data, colWidths=[doc.width / max(1, len(cols))] * max(1, len(cols)))
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, -1), "Vazir"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ]))
            if title:
                story.append(Paragraph(title, h3))
            story.append(tbl)
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 4))

    doc.build(story)
    return buf.getvalue()


FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa_digits(n) -> str:
    return str(n).translate(FA_DIGITS)


# ---------------------------------------------------------------- PPTX

def _split_bullets(text: str, max_len: int = 110) -> list[str]:
    """تقسیم هوشمند محتوای طولانی به بولت‌ها (کنترل تراکم متن)."""
    parts = re.split(r"(?<=[.؟!؛])\s+", text or "")
    bullets, buf = [], ""
    for p in parts:
        cand = (buf + " " + p).strip()
        if len(cand) > max_len and buf:
            bullets.append(buf)
            buf = p
        else:
            buf = cand
    if buf:
        bullets.append(buf)
    return bullets or [""]


def render_pptx(blocks: list[dict], meta: dict, options: dict | None = None) -> bytes:
    import io

    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    options = options or {}
    aspect = options.get("aspect", "16:9")
    prs = Presentation()
    if aspect == "4:3":
        prs.slide_width, prs.slide_height = Inches(10), Inches(7.5)
    else:
        prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    BRAND = RGBColor(0x1D, 0x4E, 0xD8)
    INK = RGBColor(0x1F, 0x29, 0x37)
    MUTED = RGBColor(0x6B, 0x72, 0x80)

    def blank_slide():
        return prs.slides.add_slide(prs.slide_layouts[6])

    def add_text(slide, text, left, top, width, height, size=18, bold=False,
                 color=INK, align=PP_ALIGN.RIGHT):
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = "Vazirmatn"
        return box

    def add_bullets_tf(slide, bullets, left, top, width, height, size=16):
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        first = True
        for item in bullets:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.alignment = PP_ALIGN.RIGHT
            run = p.add_run()
            run.text = "• " + str(item)
            run.font.size = Pt(size)
            run.font.color.rgb = INK
            run.font.name = "Vazirmatn"
        return box

    def set_notes(slide, note: str):
        slide.notes_slide.notes_text_frame.text = note

    W, H = prs.slide_width, prs.slide_height
    margin = Inches(0.6)

    # اسلاید عنوان
    s = blank_slide()
    add_text(s, meta.get("document_title", ""), margin, H / 3, W - 2 * margin, Inches(1.2), size=32, bold=True, color=BRAND)
    add_text(s, f"{meta.get('course_title', '')} ({meta.get('course_code', '')}) — استاد: {meta.get('professor', '')}",
             margin, H / 3 + Inches(1.1), W - 2 * margin, Inches(0.6), size=16, color=MUTED)
    add_text(s, f"نسخه محتوا {meta.get('version_number', '')} — سرفصل نسخه {meta.get('syllabus_version_number', '')} — {meta.get('generated_at', '')}",
             margin, H / 3 + Inches(1.7), W - 2 * margin, Inches(0.5), size=12, color=MUTED)
    set_notes(s, "این ارائه از نسخه تأییدشده محتوای درس تولید شده است. فرمول‌ها به‌صورت متن قابل ویرایش درج شده‌اند.")

    body_width = W - 2 * margin
    for b in blocks:
        t = b.get("type")
        if t == "heading":
            s = blank_slide()
            add_text(s, b.get("title") or "", margin, H / 3, body_width, Inches(1), size=28, bold=True, color=BRAND)
            if b.get("body"):
                add_text(s, b["body"], margin, H / 3 + Inches(1), body_width, Inches(1), size=16, color=MUTED)
        elif t in ("text", "definition", "summary", "reference"):
            chunks = _split_bullets(b.get("body") or "")
            page_i = 0
            while page_i * 6 < max(1, len(chunks)) or page_i == 0:
                group = chunks[page_i * 6:(page_i + 1) * 6] or [""]
                s = blank_slide()
                suffix = f" ({to_fa_digits(page_i + 1)}/{to_fa_digits((len(chunks) - 1) // 6 + 1)})" if len(chunks) > 6 else ""
                add_text(s, (b.get("title") or t) + suffix, margin, Inches(0.4), body_width, Inches(0.7), size=22, bold=True)
                items = group if b.get("type") in ("reference", "summary") and not b.get("body") else \
                        [f"• {c}" for c in group]
                if b.get("items"):
                    items += [f"– {i}" for i in b["items"]]
                add_bullets_tf(s, items, margin, Inches(1.2), body_width, H - Inches(2))
                set_notes(s, f"منبع: سند «{meta.get('document_title')}» نسخه {meta.get('version_number')}")
                page_i += 1
                if page_i * 6 >= max(1, len(chunks)):
                    break
        elif t == "note":
            s = blank_slide()
            add_text(s, "نکته: " + (b.get("title") or ""), margin, Inches(0.5), body_width, Inches(0.7), size=22, bold=True, color=RGBColor(0x92, 0x40, 0x0E))
            add_bullets_tf(s, _split_bullets(b.get("body") or ""), margin, Inches(1.3), body_width, H - Inches(2.5), size=16)
        elif t == "worked_example":
            s = blank_slide()
            add_text(s, "مثال حل‌شده", margin, Inches(0.4), body_width, Inches(0.6), size=22, bold=True, color=BRAND)
            add_text(s, b.get("question") or "", margin, Inches(1.0), body_width, Inches(0.8), size=15)
            add_bullets_tf(s, [f"گام {to_fa_digits(i + 1)}: {st}" for i, st in enumerate(b.get("steps") or [])],
                           margin, Inches(1.9), body_width, H - Inches(3.2), size=14)
            set_notes(s, "برای هر گام، بخش مربوط از تعریف را یادآوری کنید؛ زمان پیشنهادی: ۵ دقیقه.")
        elif t == "exercise":
            s = blank_slide()
            add_text(s, "تمرین", margin, Inches(0.5), body_width, Inches(0.6), size=22, bold=True, color=RGBColor(0xBE, 0x18, 0x56))
            add_text(s, b.get("question") or "", margin, Inches(1.2), body_width, Inches(1.4), size=16)
            if b.get("items"):
                add_bullets_tf(s, [str(i) for i in b["items"]], margin, Inches(2.8), body_width, Inches(2), size=14)
            set_notes(s, "پاسخ تمرین را پس از ۱۰ دقیقه کار گروهی طرح کنید.")
        elif t == "self_check":
            s = blank_slide()
            add_text(s, "خودارزیابی", margin, Inches(0.5), body_width, Inches(0.6), size=22, bold=True, color=BRAND)
            add_text(s, b.get("question") or "", margin, Inches(1.2), body_width, Inches(1.6), size=16)
            set_notes(s, "پاسخ (فقط یادداشت مدرس): " + (b.get("answer") or "") + " " + (b.get("explanation") or ""))
        elif t == "formula":
            s = blank_slide()
            add_text(s, b.get("title") or "فرمول", margin, Inches(0.5), body_width, Inches(0.6), size=20, bold=True)
            expr = latex_to_plain(b.get("formula"))
            box = add_text(s, expr, margin, H / 3, body_width, Inches(1.4), size=26, bold=True, align=PP_ALIGN.CENTER)
            box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            set_notes(s, "محدودیت: فرمول به‌صورت متن ساده درج شده و قابل ویرایش است؛ نسخه پیچیده ریاضی در خروجی HTML با KaTeX نمایش داده می‌شود.")
        elif t == "table":
            s = blank_slide()
            cols = b.get("columns") or []
            rows = b.get("rows") or []
            n_rows = len(rows) + 1
            n_cols = max(1, len(cols))
            add_text(s, b.get("title") or "", margin, Inches(0.4), body_width, Inches(0.6), size=20, bold=True)
            gf = s.shapes.add_table(n_rows, n_cols, margin, Inches(1.1), body_width,
                                    Inches(0.5 + 0.5 * n_rows)).table
            for ci, c in enumerate(cols):
                cell = gf.cell(0, ci)
                cell.text = str(c)
            for ri, r in enumerate(rows):
                for ci, cellval in enumerate(r[:n_cols]):
                    gf.cell(ri + 1, ci).text = str(cellval)
            set_notes(s, "جدول به‌صورت قابل ویرایش درج شده است.")
        elif t == "code":
            s = blank_slide()
            add_text(s, b.get("title") or "کد", margin, Inches(0.4), body_width, Inches(0.6), size=18, bold=True)
            add_bullets_tf(s, (b.get("body") or "").split("\n")[:12], margin, Inches(1.0), body_width, H - Inches(2), size=12)
        elif t == "image":
            s = blank_slide()
            add_text(s, b.get("title") or "تصویر", margin, Inches(0.4), body_width, Inches(0.6), size=20, bold=True)
            add_text(s, b.get("body") or "", margin, Inches(1.0), body_width, Inches(1), size=14)
            set_notes(s, "فایل تصویر در بسته ZIP منابع درج می‌شود.")

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- DOCX

def render_docx(blocks: list[dict], meta: dict) -> bytes:
    import io

    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Vazirmatn"
    style.font.size = Pt(11)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Vazirmatn")

    def set_rtl(paragraph):
        pPr = paragraph._p.get_or_add_pPr()
        bidi = pPr.makeelement(qn("w:bidi"), {})
        pPr.append(bidi)

    def p(text, bold=False, size=11, color=None, align=WD_ALIGN_PARAGRAPH.RIGHT):
        para = doc.add_paragraph()
        para.alignment = align
        set_rtl(para)
        run = para.add_run(text or "")
        run.font.size = Pt(size)
        run.bold = bold
        if color:
            run.font.color.rgb = color
        return para

    h = doc.add_heading(level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h.add_run(meta.get("document_title", ""))
    run.font.name = "Vazirmatn"
    set_rtl(h)
    p(f"درس: {meta.get('course_title', '')} ({meta.get('course_code', '')}) — استاد: {meta.get('professor', '')}")
    p(f"نسخه محتوا: {meta.get('version_number', '')} — نسخه سرفصل: {meta.get('syllabus_version_number', '')} — تاریخ: {meta.get('generated_at', '')}")
    doc.add_paragraph()

    BRAND = RGBColor(0x1D, 0x4E, 0xD8)
    for b in blocks:
        t = b.get("type")
        if t == "heading":
            hp = doc.add_heading(level=1)
            set_rtl(hp)
            r = hp.add_run(b.get("title") or "")
            r.font.color.rgb = BRAND
        elif t == "table":
            if b.get("title"):
                p(b["title"], bold=True)
            cols = b.get("columns") or []
            rows = b.get("rows") or []
            table = doc.add_table(rows=len(rows) + 1, cols=max(1, len(cols)))
            table.style = "Light Grid Accent 1"
            for ci, c in enumerate(reversed(cols)):
                table.rows[0].cells[ci].text = str(c)
            for ri, row in enumerate(rows):
                for ci, val in enumerate(reversed(row)):
                    table.rows[ri + 1].cells[ci].text = str(val)
        elif t == "formula":
            p(latex_to_plain(b.get("formula")), bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        elif t in ("text", "definition", "note", "summary", "reference"):
            if b.get("title"):
                p(b["title"], bold=True, color=BRAND)
            if b.get("body"):
                p(b["body"])
            for it in b.get("items") or []:
                p("– " + str(it))
        elif t == "worked_example":
            p("مثال حل‌شده: " + (b.get("question") or ""), bold=True, color=BRAND)
            for i, s in enumerate(b.get("steps") or []):
                p(f"گام {to_fa_digits(i + 1)}: {s}")
        elif t == "exercise":
            p("تمرین: " + (b.get("question") or ""), bold=True)
            for it in b.get("items") or []:
                p("راهنما: " + str(it))
        elif t == "self_check":
            p("خودارزیابی: " + (b.get("question") or ""), bold=True)
            p("پاسخ: " + (b.get("answer") or ""))
        elif t == "code":
            cp = doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = cp.add_run(b.get("body") or "")
            r.font.name = "Courier New"
            r.font.size = Pt(9)
        doc.add_paragraph()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- اجرای خروجی

MIME = {"PDF": "application/pdf", "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "HTML": "text/html; charset=utf-8", "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def build_meta(db, version) -> dict:
    from app.models.content import ContentDocument
    from app.models.courses import Course
    from app.models.identity import User
    from app.models.syllabus import SyllabusVersion

    doc = db.get(ContentDocument, version.document_id)
    course = db.get(Course, doc.course_id)
    sv = db.get(SyllabusVersion, version.syllabus_version_id)
    professor = db.get(User, course.created_by) if course.created_by else None
    if professor is None:
        from app.core.permissions import Role

        from app.models.identity import CourseRole

        cr = db.query(CourseRole).filter(CourseRole.course_id == course.id,
                                         CourseRole.role == Role.PROFESSOR.value).first()
        professor = db.get(User, cr.user_id) if cr else None
    return {
        "document_title": doc.title,
        "course_title": course.title,
        "course_code": course.code,
        "professor": professor.full_name if professor else "استاد درس",
        "version_number": version.version_number,
        "syllabus_version_number": sv.version_number if sv else "-",
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "template_version": TEMPLATE_VERSION,
    }


def render_export(db, version, fmt: str, options: dict | None = None) -> tuple[bytes, str]:
    """خروجی خام برای آزمایش‌ها — بازگشت (بایت‌ها، mime)."""
    from app.core.errors import validation_error

    blocks = (version.structured_content or {}).get("blocks", [])
    meta = build_meta(db, version)
    fmt = (fmt or "").upper()
    if fmt == "HTML":
        return render_html(blocks, meta), MIME["HTML"]
    if fmt == "PDF":
        return render_pdf(blocks, meta, options), MIME["PDF"]
    if fmt == "PPTX":
        return render_pptx(blocks, meta, options), MIME["PPTX"]
    if fmt == "DOCX":
        return render_docx(blocks, meta), MIME["DOCX"]
    raise validation_error(f"قالب خروجی پشتیبانی نمی‌شود: {fmt}")
