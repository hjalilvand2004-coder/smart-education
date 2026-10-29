# -*- coding: utf-8 -*-
"""
=====================================================================
HTML Report — خروجی HTML تک‌فایلی با گرافیک کامل
=====================================================================
تمام CSS و نمودارهای SVG داخل همان فایل قرار می‌گیرند تا بدون
اینترنت و بدون وابستگی بیرونی، در هر مرورگری زیبا نمایش داده شود
و برای چاپ (Print to PDF) هم بهینه است.
=====================================================================
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .theme import CHART_COLORS, PALETTE, fa_num


def _esc(text: Any) -> str:
    s = str(text or "")
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ------------------------------------------------------------------
# نمودار دونات (SVG خالص)
# ------------------------------------------------------------------
def _donut_svg(items: List[Dict[str, Any]], size: int = 210) -> str:
    total = sum(i["value"] for i in items)
    radius = size / 2 - 16
    cx = cy = size / 2
    stroke = 28

    if total <= 0:
        return (
            f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
            f'stroke="{PALETTE["line"]}" stroke-width="{stroke}"/>'
            f'<text x="{cx}" y="{cy + 6}" text-anchor="middle" '
            f'font-size="13" fill="{PALETTE["muted"]}">داده‌ای نیست</text></svg>'
        )

    circ = 2 * math.pi * radius
    offset = 0.0
    parts = []
    for idx, item in enumerate(items):
        frac = item["value"] / total
        dash = frac * circ
        color = CHART_COLORS[idx % len(CHART_COLORS)]
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" '
            f'stroke-dasharray="{dash:.1f} {circ - dash:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" '
            f'transform="rotate(-90 {cx} {cy})">'
            f'<title>{_esc(item["label"])}: {fa_num(item["value"])}</title></circle>'
        )
        offset += dash

    center = (
        f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" '
        f'font-size="28" font-weight="800" fill="{PALETTE["ink"]}">'
        f'{fa_num(total)}</text>'
        f'<text x="{cx}" y="{cy + 22}" text-anchor="middle" '
        f'font-size="11" fill="{PALETTE["muted"]}">کل سؤال‌ها</text>'
    )
    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        + "".join(parts)
        + center
        + "</svg>"
    )


# ------------------------------------------------------------------
# نمودار میله‌ای افقی (CSS خالص — سازگار کامل با RTL)
# ------------------------------------------------------------------
def _hbar_html(items: List[Dict[str, Any]]) -> str:
    max_val = max((i["value"] for i in items), default=0) or 1
    rows = []
    for idx, item in enumerate(items):
        frac = max(2.0, item["value"] / max_val * 100)
        color = CHART_COLORS[idx % len(CHART_COLORS)]
        rows.append(
            '<div class="hbar-row">'
            f'<div class="hbar-label" title="{_esc(item["label"])}">'
            f'{_esc(item["label"])}</div>'
            '<div class="hbar-track">'
            f'<div class="hbar-fill" style="width:{frac:.1f}%;background:{color};"></div>'
            '</div>'
            f'<div class="hbar-val">{fa_num(item["value"])}</div>'
            '</div>'
        )
    return '<div class="hbar">' + "".join(rows) + "</div>"


# ------------------------------------------------------------------
# کارت‌های شاخص (KPI)
# ------------------------------------------------------------------
def _kpi_card(icon: str, value: int, label: str, color: str) -> str:
    return f"""
    <div class="kpi">
      <div class="kpi-icon" style="background:{color}1a;color:{color};">{icon}</div>
      <div class="kpi-num" style="color:{color};">{fa_num(value)}</div>
      <div class="kpi-label">{_esc(label)}</div>
    </div>"""


# ------------------------------------------------------------------
# ساخت سند کامل HTML
# ------------------------------------------------------------------
def build_html(data: Dict[str, Any]) -> tuple[str, str]:
    kpis: Dict[str, int] = data["kpis"]
    courses: List[Dict[str, Any]] = data["courses"]
    quizzes: List[Dict[str, Any]] = data["quizzes"]
    top_courses: List[Dict[str, Any]] = data["top_courses"]
    scheduler: Dict[str, Any] | None = data.get("scheduler")
    scheduler_courses: List[Dict[str, Any]] = data.get("scheduler_courses") or []

    p = PALETTE

    # ---- KPI کارت‌ها ----
    kpi_html = "".join(
        [
            _kpi_card("📚", kpis["courses"], "درس ثبت‌شده", p["primary"]),
            _kpi_card("🗂", kpis["topics"], "سرفصل آموزشی", p["cyan"]),
            _kpi_card("⏱", kpis["minutes"], "دقیقه آموزش", p["amber"]),
            _kpi_card("📄", kpis["contents"], "محتوای آموزشی", p["teal"]),
            _kpi_card("📝", kpis["quizzes"], "آزمون", p["accent"]),
            _kpi_card("❓", kpis["questions"], "سؤال", p["rose"]),
        ]
    )

    # ---- جدول دروس ----
    course_trs = []
    for idx, c in enumerate(courses):
        status_badge = (
            '<span class="badge badge-on">فعال</span>'
            if c["is_active"]
            else '<span class="badge badge-off">غیرفعال</span>'
        )
        course_trs.append(
            f"<tr>"
            f'<td class="c-muted">{fa_num(idx + 1)}</td>'
            f'<td class="c-strong">{_esc(c["title"])}</td>'
            f"<td>{fa_num(c['topic_count'])}</td>"
            f"<td>{fa_num(c['minutes'])}</td>"
            f"<td>{fa_num(c['content_count'])}</td>"
            f"<td>{fa_num(c['quiz_count'])}</td>"
            f"<td>{fa_num(c['question_count'])}</td>"
            f"<td>{status_badge}</td>"
            f"</tr>"
        )
    courses_table = "".join(course_trs) or (
        '<tr><td colspan="8" class="c-empty">هنوز درسی ثبت نشده است</td></tr>'
    )

    # ---- سرفصل‌ها per درس (تاشو) ----
    topics_html = []
    for c in top_courses:
        if not c["topics"]:
            continue
        rows = "".join(
            f'<li><span class="t-title">{_esc(t["title"])}</span>'
            f'<span class="t-min">{fa_num(t["minutes"])} دقیقه</span></li>'
            for t in c["topics"][:10]
        )
        more = (
            f'<li class="t-more">و {fa_num(len(c["topics"]) - 10)} سرفصل دیگر…</li>'
            if len(c["topics"]) > 10
            else ""
        )
        topics_html.append(
            f'<details class="course-box">'
            f'<summary><span class="cb-title">{_esc(c["title"])}</span>'
            f'<span class="cb-meta">{fa_num(c["topic_count"])} سرفصل · '
            f'{fa_num(c["minutes"])} دقیقه</span></summary>'
            f'<ul class="topic-list">{rows}{more}</ul></details>'
        )
    topics_section = "".join(topics_html) or (
        '<p class="c-empty">هنوز سرفصلی ثبت نشده است.</p>'
    )

    # ---- آزمون‌ها ----
    quiz_trs = "".join(
        f"<tr><td class='c-strong'>{_esc(q['title'])}</td>"
        f"<td>{_esc(q['course'])}</td>"
        f"<td>{fa_num(q['question_count'])}</td></tr>"
        for q in quizzes[:15]
    ) or '<tr><td colspan="3" class="c-empty">هنوز آزمونی ساخته نشده است</td></tr>'

    # ---- بخش سرویس بیرونی ----
    if scheduler:
        if scheduler.get("available"):
            integ_status = (
                f'<span class="badge badge-on">متصل ✓</span>'
                f'<span class="integ-url">{_esc(scheduler["base_url"])}</span>'
            )
            integ_desc = (
                f"فهرست دروس از «سامانه هوشمند برنامه‌ریزی درسی» با موفقیت "
                f"خوانده شد ({fa_num(scheduler.get('course_count', 0))} درس)."
            )
        else:
            integ_status = (
                f'<span class="badge badge-off">قطع</span>'
                f'<span class="integ-url">{_esc(scheduler["base_url"])}</span>'
            )
            integ_desc = (
                "در زمان تولید گزارش، سرویس برنامه‌ریزی درسی پاسخ نداد؛ "
                "گزارش صرفاً بر پایهٔ داده‌های محلی سامانه ساخته شده است."
            )

        sc_rows = "".join(
            f"<tr><td class='c-strong'>{_esc(c['title'])}</td>"
            f"<td>{_esc(c.get('code') or '—')}</td>"
            f"<td>{fa_num(c.get('credits', '—'))}</td></tr>"
            for c in scheduler_courses
        ) or '<tr><td colspan="3" class="c-empty">فهرستی دریافت نشد</td></tr>'
    else:
        integ_status = '<span class="badge badge-off">غیرفعال</span>'
        integ_desc = "بخش یکپارچگی سرویس‌ها در این گزارش لحاظ نشده است."
        sc_rows = ""

    scheduler_section = f"""
    <section class="card">
      <div class="card-head">
        <h2><span class="h-dot" style="background:{p['teal']};"></span>
            یکپارچگی سرویس‌ها <small>Service Integration</small></h2>
        <div>{integ_status}</div>
      </div>
      <p class="card-desc">{integ_desc}</p>
      <table>
        <thead><tr>
          <th>عنوان درس (از سرویس scheduler)</th><th>کد</th><th>واحد</th>
        </tr></thead>
        <tbody>{sc_rows}</tbody>
      </table>
    </section>"""

    # ---- نمودار دونات + برچسب ----
    legend_items = "".join(
        f'<span class="lg-item"><i style="background:{CHART_COLORS[i % len(CHART_COLORS)]};">'
        f"</i>{_esc(it['label'])} — {fa_num(it['value'])}</span>"
        for i, it in enumerate(data["question_split"])
    )

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(data['title'])}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: "Vazirmatn", "Estedad", "Segoe UI", Tahoma, sans-serif;
    background:{p['bg']}; color:{p['ink']}; line-height:1.9;
  }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:28px 20px 60px; }}

  /* هدر گرادیانی */
  .hero {{
    background:linear-gradient(135deg,{p['primary_dark']} 0%,{p['primary']} 55%,{p['accent']} 100%);
    border-radius:24px; padding:44px 40px; color:#fff;
    box-shadow:0 20px 50px -18px {p['primary']}66; position:relative; overflow:hidden;
  }}
  .hero::after {{
    content:""; position:absolute; inset:0;
    background:radial-gradient(circle at 85% 20%, #ffffff22 0%, transparent 45%),
               radial-gradient(circle at 10% 90%, #ffffff14 0%, transparent 40%);
    pointer-events:none;
  }}
  .hero h1 {{ font-size:30px; font-weight:800; letter-spacing:-0.3px; }}
  .hero .sub {{ font-size:14px; opacity:.85; margin-top:8px; font-weight:400;
    font-family:"Segoe UI",sans-serif; letter-spacing:.5px; }}
  .hero .meta {{ display:flex; gap:18px; margin-top:22px; flex-wrap:wrap; }}
  .hero .chip {{
    background:#ffffff1f; border:1px solid #ffffff38; border-radius:999px;
    padding:6px 16px; font-size:12.5px; backdrop-filter:blur(4px);
  }}

  /* کارت KPI */
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:14px; margin-top:-26px; position:relative; z-index:2; padding:0 6px; }}
  .kpi {{
    background:#fff; border-radius:16px; padding:18px 14px; text-align:center;
    box-shadow:0 8px 24px -10px #1e293b26; border:1px solid {p['line']};
  }}
  .kpi-icon {{ width:44px; height:44px; border-radius:12px; display:flex;
    align-items:center; justify-content:center; margin:0 auto 8px; font-size:20px; }}
  .kpi-num {{ font-size:26px; font-weight:800; }}
  .kpi-label {{ font-size:12px; color:{p['muted']}; margin-top:2px; }}

  /* کارت‌های بخش */
  .card {{
    background:#fff; border:1px solid {p['line']}; border-radius:20px;
    padding:26px 28px; margin-top:22px; box-shadow:0 6px 20px -12px #1e293b1f;
  }}
  .card-head {{ display:flex; justify-content:space-between; align-items:center;
    flex-wrap:wrap; gap:10px; margin-bottom:14px; }}
  .card-head h2 {{ font-size:17px; font-weight:800; display:flex; align-items:center; gap:10px; }}
  .card-head h2 small {{ font-size:11px; color:{p['muted']}; font-weight:400;
    font-family:"Segoe UI",sans-serif; }}
  .h-dot {{ width:10px; height:10px; border-radius:3px; display:inline-block; }}
  .card-desc {{ font-size:13px; color:{p['muted']}; margin-bottom:14px; }}

  .charts {{ display:grid; grid-template-columns:1fr 1.4fr; gap:22px; align-items:start; }}
  @media (max-width:760px) {{ .charts {{ grid-template-columns:1fr; }} }}
  .legend {{ margin-top:12px; display:flex; flex-direction:column; gap:8px; }}
  .lg-item {{ font-size:12.5px; display:flex; align-items:center; gap:8px; }}
  .lg-item i {{ width:12px; height:12px; border-radius:4px; display:inline-block; }}

  /* نمودار میله‌ای CSS */
  .hbar {{ display:flex; flex-direction:column; gap:9px; }}
  .hbar-row {{ display:grid; grid-template-columns:minmax(90px,150px) 1fr 48px;
    align-items:center; gap:10px; }}
  .hbar-label {{ font-size:12px; color:{p['ink']}; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; }}
  .hbar-track {{ background:{p['primary_light']}; border-radius:999px;
    height:18px; overflow:hidden; }}
  .hbar-fill {{ height:100%; border-radius:999px; min-width:6px; }}
  .hbar-val {{ font-size:11px; color:{p['muted']}; text-align:left; }}

  /* جدول‌ها */
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  thead th {{
    background:{p['primary_light']}; color:{p['primary_dark']};
    padding:10px 12px; text-align:right; font-weight:700; font-size:12.5px;
  }}
  thead th:first-child {{ border-radius:0 10px 10px 0; }}
  thead th:last-child {{ border-radius:10px 0 0 10px; }}
  tbody td {{ padding:10px 12px; border-bottom:1px solid {p['line']}; }}
  tbody tr:hover td {{ background:#fafbff; }}
  .c-strong {{ font-weight:700; }}
  .c-muted {{ color:{p['muted']}; }}
  .c-empty {{ text-align:center; color:{p['muted']}; padding:22px !important; }}

  .badge {{ display:inline-block; padding:3px 12px; border-radius:999px;
    font-size:11px; font-weight:700; }}
  .badge-on {{ background:#DCFCE7; color:#15803D; }}
  .badge-off {{ background:#FEE2E2; color:#B91C1C; }}
  .integ-url {{ font-size:11.5px; color:{p['muted']}; margin-right:10px;
    direction:ltr; unicode-bidi:embed; font-family:"Segoe UI",monospace; }}

  /* سرفصل‌ها */
  .course-box {{ border:1px solid {p['line']}; border-radius:14px;
    margin-bottom:10px; overflow:hidden; background:#fff; }}
  .course-box summary {{
    padding:12px 16px; cursor:pointer; display:flex; justify-content:space-between;
    align-items:center; gap:10px; list-style:none; background:{p['bg']};
  }}
  .course-box summary::-webkit-details-marker {{ display:none; }}
  .cb-title {{ font-weight:700; font-size:13.5px; }}
  .cb-meta {{ font-size:11.5px; color:{p['muted']}; white-space:nowrap; }}
  .topic-list {{ list-style:none; padding:8px 18px 14px; }}
  .topic-list li {{ display:flex; justify-content:space-between; padding:7px 0;
    border-bottom:1px dashed {p['line']}; font-size:12.5px; }}
  .topic-list li:last-child {{ border-bottom:none; }}
  .t-min {{ color:{p['muted']}; font-size:11.5px; white-space:nowrap; }}
  .t-more {{ justify-content:center !important; color:{p['primary']};
    font-size:11.5px !important; }}

  footer {{ text-align:center; margin-top:34px; color:{p['muted']};
    font-size:11.5px; }}

  @media print {{
    body {{ background:#fff; }}
    .hero {{ border-radius:0; box-shadow:none; }}
    .card, .kpi {{ box-shadow:none; break-inside:avoid; }}
    details {{ break-inside:avoid; }}
    details:not([open]) summary ~ * {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <h1>{_esc(data['title'])}</h1>
    <div class="sub">{_esc(data['subtitle'])}</div>
    <div class="meta">
      <span class="chip">🗓 {fa_num(data['date_fa'])}</span>
      <span class="chip">🕒 {_esc(data['generated_at'])}</span>
      <span class="chip">🎓 Smart Education v2.2</span>
    </div>
  </div>

  <div class="kpis">{kpi_html}</div>

  <section class="card">
    <div class="card-head">
      <h2><span class="h-dot" style="background:{p['primary']};"></span>
          تصویر کلی آماری <small>Analytics Overview</small></h2>
    </div>
    <div class="charts">
      <div>
        <h3 style="font-size:13.5px; margin-bottom:6px;">ترکیب سؤال‌ها بر اساس نوع</h3>
        <div style="display:flex; justify-content:center;">{_donut_svg(data['question_split'])}</div>
        <div class="legend">{legend_items}</div>
      </div>
      <div>
        <h3 style="font-size:13.5px; margin-bottom:10px;">حجم آموزش هر درس (دقیقه)</h3>
        {_hbar_html([{"label": c["title"], "value": c["minutes"]} for c in top_courses])}
      </div>
    </div>
  </section>

  <section class="card">
    <div class="card-head">
      <h2><span class="h-dot" style="background:{p['cyan']};"></span>
          فهرست دروس و شاخص‌ها <small>Courses Overview</small></h2>
    </div>
    <table>
      <thead><tr>
        <th>#</th><th>عنوان درس</th><th>سرفصل</th><th>دقیقه</th>
        <th>محتوا</th><th>آزمون</th><th>سؤال</th><th>وضعیت</th>
      </tr></thead>
      <tbody>{courses_table}</tbody>
    </table>
  </section>

  <section class="card">
    <div class="card-head">
      <h2><span class="h-dot" style="background:{p['amber']};"></span>
          سرفصل‌های آموزشی <small>Course Topics</small></h2>
    </div>
    {topics_section}
  </section>

  <section class="card">
    <div class="card-head">
      <h2><span class="h-dot" style="background:{p['accent']};"></span>
          آزمون‌های سامانه <small>Quizzes</small></h2>
    </div>
    <table>
      <thead><tr><th>عنوان آزمون</th><th>درس</th><th>تعداد سؤال</th></tr></thead>
      <tbody>{quiz_trs}</tbody>
    </table>
  </section>

  {scheduler_section}

  <footer>
    این گزارش به‌صورت خودکار توسط «سامانه هوشمند آموزش» تولید شده است —
    {fa_num(data['date_fa'])}
  </footer>
</div>
</body>
</html>"""

    filename = f"smart-education-report-{data['generated_at'].replace('-', '').replace(':', '').replace(' ', '-')}.html"
    return html, filename
