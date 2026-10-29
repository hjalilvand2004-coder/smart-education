# -*- coding: utf-8 -*-
"""
=====================================================================
PowerPoint Report — ارائهٔ پاورپوینت گرافیکی
=====================================================================
اسلایدها: جلد گرادیانی ← شاخص‌های کلیدی ← نمودار بومی قابل ویرایش ←
جدول دروس ← سرفصل‌های نمونه ← سرویس بیرونی ← اختتامیه
ابعاد 16:9 و پالت رنگ هماهنگ با سایر خروجی‌ها.
=====================================================================
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from .theme import PALETTE, fa_num

# 16:9
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _rgb(hex_color: str) -> RGBColor:
    hex_color = hex_color.lstrip("#")
    return RGBColor(
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _set_text(shape, text: str, size: int, color: str, bold: bool = False,
              align=PP_ALIGN.CENTER, font: str = "Vazirmatn") -> None:
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.name = font
    f.color.rgb = _rgb(color)


def _add_textbox(slide, x, y, w, h, text, size, color, bold=False,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.vertical_anchor = anchor
    _set_text(box, text, size, color, bold, align)
    return box


def _add_rect(slide, x, y, w, h, fill: str, line=None, radius=None):
    from pptx.enum.shapes import MSO_SHAPE

    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    if line:
        shape.line.color.rgb = _rgb(line)
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    if radius:
        try:
            shape.adjustments[0] = radius
        except Exception:  # noqa: BLE001
            pass
    shape.shadow.inherit = False
    return shape


def _gradient_cover(slide, prs):
    """پس‌زمینه گرادیانی جلد (به‌صورت دستی با نوارهای رنگی)."""
    bands = ["#312E81", "#3730A3", "#4338CA", "#4F46E5", "#6D28D9", "#7C3AED"]
    n = len(bands)
    band_w = SLIDE_W // n
    for i, c in enumerate(bands):
        _add_rect(slide, i * band_w, 0, band_w + Emu(9525), SLIDE_H, c)
    # دایره‌های تزئینی نیمه‌شفاف
    from pptx.enum.shapes import MSO_SHAPE

    for cx, cy, r in [(Inches(11.2), Inches(-0.8), Inches(3.4)),
                      (Inches(0.4), Inches(5.6), Inches(2.6))]:
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, cx, cy, r, r)
        circ.fill.solid()
        circ.fill.fore_color.rgb = _rgb("#FFFFFF")
        circ.fill.transparency = 0.88  # noqa
        try:
            from pptx.oxml.ns import qn

            solid = circ.fill._xPr.find(qn("a:solidFill"))
            clr = solid.find(qn("a:srgbClr"))
            alpha = clr.makeelement(qn("a:alpha"), {"val": "12000"})
            clr.append(alpha)
        except Exception:  # noqa: BLE001
            pass
        circ.line.fill.background()
        circ.shadow.inherit = False


def build_pptx(data: Dict[str, Any]) -> tuple[bytes, str, str]:
    p = PALETTE
    kpis: Dict[str, int] = data["kpis"]
    courses: List[Dict[str, Any]] = data["courses"]
    top_courses: List[Dict[str, Any]] = data["top_courses"]
    quizzes: List[Dict[str, Any]] = data["quizzes"]
    scheduler: Dict[str, Any] | None = data.get("scheduler")

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # ==============================================================
    # اسلاید ۱ — جلد
    # ==============================================================
    slide = prs.slides.add_slide(blank)
    _gradient_cover(slide, prs)
    _add_textbox(slide, Inches(1), Inches(2.15), Inches(11.3), Inches(1.2),
                 data["title"], 40, "#FFFFFF", bold=True)
    _add_textbox(slide, Inches(1), Inches(3.35), Inches(11.3), Inches(0.6),
                 data["subtitle"], 17, "#E0E7FF", align=PP_ALIGN.CENTER)
    _add_textbox(slide, Inches(1), Inches(4.15), Inches(11.3), Inches(0.5),
                 f"🗓 {data['date_fa']}   ·   🕒 {data['generated_at']}",
                 14, "#C7D2FE")

    # ==============================================================
    # اسلاید ۲ — شاخص‌های کلیدی (KPI)
    # ==============================================================
    slide = prs.slides.add_slide(blank)
    _add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, "#FFFFFF")
    _add_rect(slide, 0, 0, SLIDE_W, Inches(1.15), p["primary_dark"])
    _add_textbox(slide, Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.8),
                 "شاخص‌های کلیدی سامانه  |  Key Performance Indicators",
                 24, "#FFFFFF", bold=True, align=PP_ALIGN.RIGHT)

    items = [
        (f"{kpis['courses']}", "درس ثبت‌شده", p["primary"]),
        (f"{kpis['topics']}", "سرفصل آموزشی", p["cyan"]),
        (f"{kpis['minutes']}", "دقیقه آموزش", p["amber"]),
        (f"{kpis['contents']}", "محتوای آموزشی", p["teal"]),
        (f"{kpis['quizzes']}", "آزمون", p["accent"]),
        (f"{kpis['questions']}", "سؤال", p["rose"]),
    ]
    card_w, card_h = Inches(3.75), Inches(1.85)
    gap = Inches(0.35)
    start_x = (SLIDE_W - (card_w * 3 + gap * 2)) / 2
    for idx, (num, label, color) in enumerate(items):
        row, col = divmod(idx, 3)
        x = start_x + col * (card_w + gap)
        y = Inches(1.7) + row * (card_h + Inches(0.45))
        _add_rect(slide, x, y, card_w, card_h, "#FFFFFF", line="#E2E8F0",
                  radius=0.12)
        _add_rect(slide, x, y, Inches(0.12), card_h, color)
        _add_textbox(slide, x, y + Inches(0.22), card_w, Inches(0.85),
                     fa_num(num), 40, color, bold=True)
        _add_textbox(slide, x, y + Inches(1.15), card_w, Inches(0.5),
                     label, 15, p["ink"])

    # ==============================================================
    # اسلاید ۳ — نمودار بومی (قابل ویرایش)
    # ==============================================================
    slide = prs.slides.add_slide(blank)
    _add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, "#FFFFFF")
    _add_rect(slide, 0, 0, SLIDE_W, Inches(1.15), p["primary_dark"])
    _add_textbox(slide, Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.8),
                 "حجم آموزش هر درس (دقیقه)", 24, "#FFFFFF", bold=True,
                 align=PP_ALIGN.RIGHT)

    if top_courses:
        chart_data = CategoryChartData()
        chart_data.categories = [c["title"][:16] for c in top_courses]
        chart_data.add_series("دقیقه", [c["minutes"] for c in top_courses])
        gf = slide.shapes.add_chart(
            XL_CHART_TYPE.BAR_CLUSTERED,
            Inches(0.6), Inches(1.5), Inches(12.1), Inches(5.5),
            chart_data,
        )
        chart = gf.chart
        chart.has_legend = False
        plot = chart.plots[0]
        plot.gap_width = 60
        series = plot.series[0]
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = _rgb(p["primary"])
        chart.font.size = Pt(12)
        chart.font.name = "Vazirmatn"
        chart.font.color.rgb = _rgb(p["ink"])
    else:
        _add_textbox(slide, Inches(2), Inches(3), Inches(9), Inches(1),
                     "داده‌ای برای نمایش وجود ندارد", 18, p["muted"])

    # ==============================================================
    # اسلاید ۴ — جدول دروس
    # ==============================================================
    slide = prs.slides.add_slide(blank)
    _add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, "#FFFFFF")
    _add_rect(slide, 0, 0, SLIDE_W, Inches(1.15), p["primary_dark"])
    _add_textbox(slide, Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.8),
                 "فهرست دروس و شاخص‌ها", 24, "#FFFFFF", bold=True,
                 align=PP_ALIGN.RIGHT)

    rows_n = min(len(courses) + 1, 10)
    table_shape = slide.shapes.add_table(
        rows_n, 6, Inches(0.6), Inches(1.5), Inches(12.1),
        Inches(0.5) * rows_n,
    )
    tbl = table_shape.table
    headers = ["عنوان درس", "سرفصل", "دقیقه", "محتوا", "آزمون", "سؤال"]
    for col, h in enumerate(headers):
        cell = tbl.cell(0, col)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(p["primary_light"])
        _set_text(cell, h, 13, p["primary_dark"], bold=True)

    for r, c in enumerate(courses[: rows_n - 1], start=1):
        values = [
            c["title"][:22],
            fa_num(c["topic_count"]),
            fa_num(c["minutes"]),
            fa_num(c["content_count"]),
            fa_num(c["quiz_count"]),
            fa_num(c["question_count"]),
        ]
        for col, v in enumerate(values):
            cell = tbl.cell(r, col)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(
                "#FFFFFF" if r % 2 else "#F8FAFC"
            )
            _set_text(cell, str(v), 12, p["ink"],
                      bold=(col == 0), align=PP_ALIGN.RIGHT)

    # ==============================================================
    # اسلاید ۵ — آزمون‌ها + ترکیب سؤال
    # ==============================================================
    slide = prs.slides.add_slide(blank)
    _add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, "#FFFFFF")
    _add_rect(slide, 0, 0, SLIDE_W, Inches(1.15), p["primary_dark"])
    _add_textbox(slide, Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.8),
                 "آزمون‌ها و ترکیب سؤال‌ها", 24, "#FFFFFF", bold=True,
                 align=PP_ALIGN.RIGHT)

    split = data["question_split"]
    total_q = sum(i["value"] for i in split) or 1
    card_x = Inches(0.6)
    _add_rect(slide, card_x, Inches(1.6), Inches(4.6), Inches(4.9),
              "#F8FAFC", line="#E2E8F0", radius=0.08)
    _add_textbox(slide, card_x, Inches(1.85), Inches(4.6), Inches(0.5),
                 "ترکیب سؤال‌ها بر اساس نوع", 16, p["ink"], bold=True)
    bar_w_max = Inches(3.4)
    y = Inches(2.7)
    for idx, item in enumerate(split):
        frac = item["value"] / total_q
        color = [p["primary"], p["cyan"]][idx]
        _add_textbox(slide, card_x + Inches(0.25), y, Inches(4.1),
                     Inches(0.4),
                     f"{item['label']} — {fa_num(item['value'])} سؤال "
                     f"({fa_num(round(frac * 100))}٪)",
                     13, p["ink"], align=PP_ALIGN.RIGHT)
        _add_rect(slide, card_x + Inches(0.25), y + Inches(0.45),
                  Inches(3.9), Inches(0.28), "#E2E8F0", radius=0.5)
        _add_rect(slide, card_x + Inches(0.25), y + Inches(0.45),
                  max(Inches(0.2), Emu(int(Inches(3.9) * frac))),
                  Inches(0.28), color, radius=0.5)
        y += Inches(1.0)

    quiz_x = Inches(5.55)
    _add_rect(slide, quiz_x, Inches(1.6), Inches(7.2), Inches(4.9),
              "#F8FAFC", line="#E2E8F0", radius=0.08)
    _add_textbox(slide, quiz_x, Inches(1.85), Inches(7.2), Inches(0.5),
                 "آزمون‌های ساخته‌شده", 16, p["ink"], bold=True)
    if quizzes:
        quiz_rows = min(len(quizzes), 6)
        t = slide.shapes.add_table(
            quiz_rows + 1, 3, quiz_x + Inches(0.25), Inches(2.55),
            Inches(6.7), Inches(0.45) * (quiz_rows + 1),
        ).table
        for col, h in enumerate(["آزمون", "درس", "سؤال"]):
            cell = t.cell(0, col)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(p["primary_light"])
            _set_text(cell, h, 12, p["primary_dark"], bold=True)
        for r, q in enumerate(quizzes[:quiz_rows], start=1):
            for col, v in enumerate(
                [q["title"][:20], q["course"][:14], fa_num(q["question_count"])]
            ):
                cell = t.cell(r, col)
                cell.fill.solid()
                cell.fill.fore_color.rgb = _rgb("#FFFFFF")
                _set_text(cell, str(v), 11, p["ink"], align=PP_ALIGN.RIGHT)
    else:
        _add_textbox(slide, quiz_x + Inches(0.3), Inches(3.2), Inches(6.6),
                     Inches(0.6), "هنوز آزمونی ساخته نشده است", 14, p["muted"])

    # ==============================================================
    # اسلاید ۶ — یکپارچگی سرویس‌ها
    # ==============================================================
    slide = prs.slides.add_slide(blank)
    _add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, "#FFFFFF")
    _add_rect(slide, 0, 0, SLIDE_W, Inches(1.15), p["teal"])
    _add_textbox(slide, Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.8),
                 "یکپارچگی سرویس‌ها  |  Service Integration", 24, "#FFFFFF",
                 bold=True, align=PP_ALIGN.RIGHT)

    if scheduler:
        status_fa = "متصل ✓" if scheduler.get("available") else "قطع ✗"
        status_color = p["green"] if scheduler.get("available") else p["rose"]
        _add_rect(slide, Inches(0.6), Inches(1.55), Inches(12.1),
                  Inches(1.05), "#F0FDF4" if scheduler.get("available")
                  else "#FEF2F2", line=status_color, radius=0.12)
        _add_textbox(slide, Inches(0.9), Inches(1.72), Inches(8.5),
                     Inches(0.7),
                     f"سامانه برنامه‌ریزی درسی (university-scheduler): {status_fa}"
                     f" — {scheduler.get('base_url', '')}",
                     14, status_color, bold=True, align=PP_ALIGN.RIGHT,
                     anchor=MSO_ANCHOR.MIDDLE)
        _add_textbox(slide, Inches(9.6), Inches(1.72), Inches(2.8),
                     Inches(0.7), f"{fa_num(scheduler.get('course_count', 0))} درس",
                     16, p["ink"], bold=True, anchor=MSO_ANCHOR.MIDDLE)

        sc = data.get("scheduler_courses") or []
        if sc:
            rows_n = min(len(sc), 8)
            t = slide.shapes.add_table(
                rows_n + 1, 3, Inches(0.6), Inches(2.9), Inches(12.1),
                Inches(0.42) * (rows_n + 1),
            ).table
            for col, h in enumerate(["درس (از سرویس scheduler)", "کد", "واحد"]):
                cell = t.cell(0, col)
                cell.fill.solid()
                cell.fill.fore_color.rgb = _rgb("#CCFBF1")
                _set_text(cell, h, 12, "#134E4A", bold=True)
            for r, c in enumerate(sc[:rows_n], start=1):
                for col, v in enumerate(
                    [c["title"][:34], str(c.get("code") or "—"),
                     fa_num(c.get("credits", "—"))]
                ):
                    cell = t.cell(r, col)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = _rgb("#FFFFFF")
                    _set_text(cell, str(v), 11, p["ink"],
                              align=PP_ALIGN.RIGHT)
    else:
        _add_textbox(slide, Inches(2), Inches(3), Inches(9), Inches(1),
                     "بخش یکپارچگی در این گزارش غیرفعال است.", 15, p["muted"])

    # ==============================================================
    # اسلاید ۷ — اختتامیه
    # ==============================================================
    slide = prs.slides.add_slide(blank)
    _gradient_cover(slide, prs)
    _add_textbox(slide, Inches(1), Inches(2.6), Inches(11.3), Inches(1),
                 "پایان گزارش", 36, "#FFFFFF", bold=True)
    _add_textbox(slide, Inches(1), Inches(3.7), Inches(11.3), Inches(0.6),
                 f"تولید خودکار توسط سامانه هوشمند آموزش — {data['date_fa']}",
                 15, "#C7D2FE")

    # ==============================================================
    # ذخیره در حافظه
    # ==============================================================
    buf = io.BytesIO()
    prs.save(buf)
    filename = (
        f"smart-education-report-"
        f"{data['generated_at'].replace('-', '').replace(':', '').replace(' ', '-')}.pptx"
    )
    return (
        buf.getvalue(),
        filename,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
