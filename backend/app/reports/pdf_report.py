# -*- coding: utf-8 -*-
"""
=====================================================================
PDF Report — گزارش PDF گرافیکی با پشتیبانی کامل فارسی
=====================================================================
فونت وزیرمتن باندل‌شده + arabic-reshaper + python-bidi برای رندر
درست حروف فارسی. شامل جلد رنگی، کارت‌های KPI، نمودار میله‌ای بومی
ReportLab، جدول‌های راه‌راه و پانوشت صفحه‌بندی‌شده.
=====================================================================
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .theme import CHART_COLORS, PALETTE, fa_num, fa_text, register_pdf_fonts

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

p = PALETTE


def _c(hex_color: str) -> colors.Color:
    return colors.HexColor(hex_color)


# ------------------------------------------------------------------
# استایل‌های پاراگراف
# ------------------------------------------------------------------
def _styles(regular: str, bold: str) -> Dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName=bold, fontSize=21, leading=30,
            textColor=_c("#FFFFFF"), alignment=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=regular, fontSize=11, leading=16,
            textColor=colors.HexColor("#E0E7FF"), alignment=2,
        ),
        "h2": ParagraphStyle(
            "h2", fontName=bold, fontSize=14, leading=20,
            textColor=_c(p["primary_dark"]), alignment=2, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", fontName=regular, fontSize=9.5, leading=15,
            textColor=_c(p["ink"]), alignment=2,
        ),
        "muted": ParagraphStyle(
            "muted", fontName=regular, fontSize=8, leading=12,
            textColor=_c(p["muted"]), alignment=2,
        ),
        "cell": ParagraphStyle(
            "cell", fontName=regular, fontSize=8.5, leading=12,
            textColor=_c(p["ink"]), alignment=2,
        ),
        "cell_bold": ParagraphStyle(
            "cell_bold", fontName=bold, fontSize=8.5, leading=12,
            textColor=_c(p["ink"]), alignment=2,
        ),
    }


# ------------------------------------------------------------------
# جلد و کادرهای تزئینی هر صفحه
# ------------------------------------------------------------------
def _on_page(canvas, doc, regular: str, bold: str, data_meta: Dict[str, str]):
    canvas.saveState()

    if doc.page == 1:
        # بنر جلد
        banner_h = 72 * mm
        canvas.setFillColor(_c(p["primary_dark"]))
        canvas.rect(0, PAGE_H - banner_h, PAGE_W, banner_h, fill=1, stroke=0)
        canvas.setFillColor(_c(p["primary"]))
        canvas.rect(0, PAGE_H - banner_h - 3 * mm, PAGE_W, 3 * mm,
                    fill=1, stroke=0)
        canvas.setFillColor(_c(p["accent"]))
        canvas.rect(0, PAGE_H - banner_h - 6 * mm, PAGE_W, 3 * mm,
                    fill=1, stroke=0)

        t = fa_text(data_meta["title"])
        size = 22
        while stringWidth(t, bold, size) > CONTENT_W - 20 and size > 12:
            size -= 1
        canvas.setFillColor(colors.white)
        canvas.setFont(bold, size)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 34 * mm, t)

        canvas.setFont(regular, 11)
        canvas.setFillColor(colors.HexColor("#E0E7FF"))
        canvas.drawRightString(
            PAGE_W - MARGIN, PAGE_H - 44 * mm,
            fa_text(data_meta["subtitle"]),
        )

        canvas.setFont(regular, 9.5)
        canvas.setFillColor(colors.HexColor("#C7D2FE"))
        canvas.drawRightString(
            PAGE_W - MARGIN, PAGE_H - 56 * mm,
            fa_text(f"🗓 {data_meta['date_fa']}   ·   🕒 {data_meta['generated_at']}"),
        )

        # دایره‌های تزئینی
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.06))
        canvas.circle(PAGE_W - 30, PAGE_H - banner_h + 6, 46, fill=1, stroke=0)
        canvas.circle(52, PAGE_H - banner_h - 10, 30, fill=1, stroke=0)
    else:
        # نوار باریک بالای صفحات بعدی
        canvas.setFillColor(_c(p["primary"]))
        canvas.rect(0, PAGE_H - 9 * mm, PAGE_W, 9 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont(bold, 8.5)
        canvas.drawRightString(
            PAGE_W - MARGIN, PAGE_H - 6.2 * mm,
            fa_text("گزارش جامع سامانه هوشمند آموزش"),
        )

    # پانوشت
    canvas.setStrokeColor(_c(p["line"]))
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
    canvas.setFillColor(_c(p["muted"]))
    canvas.setFont(regular, 7.5)
    canvas.drawRightString(
        PAGE_W - MARGIN, 7.5 * mm,
        fa_text(f"سامانه هوشمند آموزش — {data_meta['date_fa']}"),
    )
    canvas.drawCentredString(PAGE_W / 2, 7.5 * mm, fa_text(f"صفحه {doc.page}"))
    canvas.restoreState()


# ------------------------------------------------------------------
# نمودار میله‌ای بومی ReportLab
# ------------------------------------------------------------------
def _bar_chart(items: List[Dict[str, Any]], width: float, height: float,
               font: str) -> Drawing:
    d = Drawing(width, height)
    label_w = 118
    value_w = 34
    bar_area = width - label_w - value_w
    n = len(items)
    row_h = height / max(n, 1)
    max_val = max((i["value"] for i in items), default=0) or 1

    for idx, item in enumerate(items):
        y = height - (idx + 1) * row_h + row_h * 0.18
        bar_h = row_h * 0.55
        # برچسب
        label = fa_text(item["label"][:16])
        d.add(
            String(label_w - 4, y + 3, label, fontName=font, fontSize=7.5,
                   fillColor=_c(p["ink"]), textAnchor="end")
        )
        # ریل
        d.add(
            Rect(label_w, y, bar_area, bar_h, rx=bar_h / 2, ry=bar_h / 2,
                 fillColor=_c(p["primary_light"]), strokeColor=None)
        )
        # میله
        w = max(6, (item["value"] / max_val) * bar_area)
        d.add(
            Rect(label_w, y, w, bar_h, rx=bar_h / 2, ry=bar_h / 2,
                 fillColor=_c(CHART_COLORS[idx % len(CHART_COLORS)]),
                 strokeColor=None)
        )
        d.add(
            String(label_w + w + 4, y + 3, fa_num(item["value"]),
                   fontName=font, fontSize=7, fillColor=_c(p["muted"]))
        )
    return d


def build_pdf(data: Dict[str, Any]) -> tuple[bytes, str, str]:
    regular, bold = register_pdf_fonts()
    S = _styles(regular, bold)

    kpis: Dict[str, int] = data["kpis"]
    courses: List[Dict[str, Any]] = data["courses"]
    top_courses: List[Dict[str, Any]] = data["top_courses"]
    quizzes: List[Dict[str, Any]] = data["quizzes"]
    scheduler: Dict[str, Any] | None = data.get("scheduler")
    scheduler_courses: List[Dict[str, Any]] = data.get("scheduler_courses") or []

    meta = {
        "title": data["title"],
        "subtitle": data["subtitle"],
        "date_fa": data["date_fa"],
        "generated_at": data["generated_at"],
    }

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=14 * mm, bottomMargin=17 * mm,
        title=data["title"], author="Smart Education",
    )

    def on_page(canvas, doc_):
        _on_page(canvas, doc_, regular, bold, meta)

    frame_first = Frame(MARGIN, 17 * mm, CONTENT_W, PAGE_H - 88 * mm - 17 * mm, id="f1")
    frame_rest = Frame(MARGIN, 17 * mm, CONTENT_W, PAGE_H - 12 * mm - 17 * mm, id="f2")
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[frame_first], onPage=on_page),
            PageTemplate(id="page", frames=[frame_rest], onPage=on_page),
        ]
    )

    story: List[Any] = []
    from reportlab.platypus import NextPageTemplate

    story.append(NextPageTemplate("page"))
    story.append(Spacer(1, 4 * mm))

    # ---- KPI ----
    kpi_defs = [
        (fa_num(kpis["courses"]), "درس", p["primary"]),
        (fa_num(kpis["topics"]), "سرفصل", p["cyan"]),
        (fa_num(kpis["minutes"]), "دقیقه", p["amber"]),
        (fa_num(kpis["contents"]), "محتوا", p["teal"]),
        (fa_num(kpis["quizzes"]), "آزمون", p["accent"]),
        (fa_num(kpis["questions"]), "سؤال", p["rose"]),
    ]
    card_gap = 3 * mm
    card_w = (CONTENT_W - card_gap * 5) / 6
    row = []
    for value, label, color in kpi_defs:
        inner = Table(
            [[Paragraph(value, ParagraphStyle(
                "kv", fontName=bold, fontSize=15, leading=19,
                textColor=_c(color), alignment=1))],
             [Paragraph(fa_text(label), ParagraphStyle(
                 "kl", fontName=regular, fontSize=7.5, leading=11,
                 textColor=_c(p["muted"]), alignment=1))]],
            colWidths=[card_w],
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, _c(p["line"])),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, 1), 1),
        ]))
        row.append(inner)

    kpi_table = Table([row], colWidths=[card_w + card_gap] * 6)
    kpi_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (-1, -1), card_gap - card_gap + 1.5),
        ("RIGHTPADDING", (1, 0), (-1, -1), 1.5),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 7 * mm))

    # ---- نمودارها ----
    story.append(Paragraph(fa_text("تصویر کلی آماری"), S["h2"]))
    story.append(
        HRFlowable(width="100%", thickness=1, color=_c(p["line"]),
                   spaceAfter=6)
    )
    split = data["question_split"]
    total_q = sum(i["value"] for i in split) or 1
    legend_txt = "   ·   ".join(
        f"{fa_text(i['label'])}: {fa_num(i['value'])} "
        f"({fa_num(round(i['value'] / total_q * 100))}٪)"
        for i in split
    )
    story.append(Paragraph(fa_text("ترکیب سؤال‌ها بر اساس نوع: ") + fa_text(legend_txt), S["body"]))
    story.append(Spacer(1, 3 * mm))
    story.append(_bar_chart(
        [{"label": c["title"], "value": c["minutes"]} for c in top_courses],
        CONTENT_W, max(20, 9 * min(len(top_courses), 8)), regular,
    ))
    story.append(Spacer(1, 8 * mm))

    # ---- جدول دروس ----
    def section(title: str):
        return [
            Paragraph(fa_text(title), S["h2"]),
            HRFlowable(width="100%", thickness=1, color=_c(p["line"]),
                       spaceAfter=6),
        ]

    if courses:
        head = ["#", "عنوان درس", "سرفصل", "دقیقه", "محتوا", "آزمون", "سؤال", "وضعیت"]
        rows = [[Paragraph(fa_text(h), S["cell_bold"]) for h in head]]
        for idx, c in enumerate(courses[:20]):
            rows.append([
                Paragraph(fa_num(idx + 1), S["cell"]),
                Paragraph(fa_text(c["title"]), S["cell_bold"]),
                Paragraph(fa_num(c["topic_count"]), S["cell"]),
                Paragraph(fa_num(c["minutes"]), S["cell"]),
                Paragraph(fa_num(c["content_count"]), S["cell"]),
                Paragraph(fa_num(c["quiz_count"]), S["cell"]),
                Paragraph(fa_num(c["question_count"]), S["cell"]),
                Paragraph(fa_text("فعال" if c["is_active"] else "غیرفعال"),
                          S["cell"]),
            ])
        col_w = [10 * mm, 52 * mm, 14 * mm, 14 * mm, 14 * mm, 14 * mm, 14 * mm, 18 * mm]
        t = Table(rows, colWidths=col_w, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _c(p["primary_light"])),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, _c(p["bg"])]),
            ("GRID", (0, 0), (-1, -1), 0.5, _c(p["line"])),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend(section("فهرست دروس و شاخص‌ها"))
        story.append(t)
        story.append(Spacer(1, 8 * mm))

    # ---- آزمون‌ها ----
    if quizzes:
        rows = [[
            Paragraph(fa_text("عنوان آزمون"), S["cell_bold"]),
            Paragraph(fa_text("درس"), S["cell_bold"]),
            Paragraph(fa_text("تعداد سؤال"), S["cell_bold"]),
        ]]
        for q in quizzes[:12]:
            rows.append([
                Paragraph(fa_text(q["title"]), S["cell_bold"]),
                Paragraph(fa_text(q["course"]), S["cell"]),
                Paragraph(fa_num(q["question_count"]), S["cell"]),
            ])
        t = Table(rows, colWidths=[70 * mm, 60 * mm, 22 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _c(p["primary_light"])),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _c(p["bg"])]),
            ("GRID", (0, 0), (-1, -1), 0.5, _c(p["line"])),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend(section("آزمون‌های سامانه"))
        story.append(t)
        story.append(Spacer(1, 8 * mm))

    # ---- سرویس بیرونی ----
    if scheduler:
        story.extend(section("یکپارچگی سرویس‌ها (Service Integration)"))
        if scheduler.get("available"):
            status_txt = (
                f"وضعیت اتصال به سامانه برنامه‌ریزی درسی: متصل ✓ — "
                f"{fa_num(scheduler.get('course_count', 0))} درس از سرویس خوانده شد "
                f"({scheduler.get('base_url', '')})"
            )
            status_color = colors.HexColor("#F0FDF4")
            status_border = _c(p["green"])
        else:
            status_txt = (
                f"در زمان تولید گزارش، سرویس برنامه‌ریزی درسی پاسخ نداد؛ "
                f"گزارش بر پایهٔ داده‌های محلی ساخته شد. "
                f"({scheduler.get('base_url', '')})"
            )
            status_color = colors.HexColor("#FEF2F2")
            status_border = _c(p["rose"])
        banner = Table(
            [[Paragraph(fa_text(status_txt), S["body"])]],
            colWidths=[CONTENT_W],
        )
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), status_color),
            ("BOX", (0, 0), (-1, -1), 0.9, status_border),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(banner)
        story.append(Spacer(1, 4 * mm))

        if scheduler_courses:
            rows = [[
                Paragraph(fa_text("درس (از سرویس scheduler)"), S["cell_bold"]),
                Paragraph(fa_text("کد"), S["cell_bold"]),
                Paragraph(fa_text("واحد"), S["cell_bold"]),
            ]]
            for c in scheduler_courses[:10]:
                rows.append([
                    Paragraph(fa_text(c["title"]), S["cell_bold"]),
                    Paragraph(fa_text(c.get("code") or "—"), S["cell"]),
                    Paragraph(fa_num(c.get("credits", "—")), S["cell"]),
                ])
            t = Table(rows, colWidths=[92 * mm, 32 * mm, 24 * mm], repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#CCFBF1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, _c(p["bg"])]),
                ("GRID", (0, 0), (-1, -1), 0.5, _c(p["line"])),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)

    story.append(Spacer(1, 9 * mm))
    story.append(Paragraph(
        fa_text(f"این گزارش به‌صورت خودکار توسط «سامانه هوشمند آموزش» تولید شده است — {data['date_fa']}"),
        S["muted"],
    ))

    doc.build(story)

    filename = (
        f"smart-education-report-"
        f"{data['generated_at'].replace('-', '').replace(':', '').replace(' ', '-')}.pdf"
    )
    return buf.getvalue(), filename, "application/pdf"
