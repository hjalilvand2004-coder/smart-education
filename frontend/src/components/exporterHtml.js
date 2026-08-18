// =============================================================
// exporterHtml.js
// خروجی HTML مستقل، مدرن، RTL، Dark Theme با افکت‌های پیشرفته
// دارای کارت، افکت Neon، Scroll Reveal، تیترهای رنگی و انیمیشن‌های چشمگیر
// =============================================================

import {
  DEFAULT_TITLE,
  escapeHtml,
  isHtmlContent,
  getBodyLines,
  isHeading,
  isBullet,
  isNumbered,
  cleanHeading,
  getBulletText,
  getNumberedText,
  getNumber,
} from "./exporterUtils";

/* ------------------------------------------------------------------
   بهینه‌سازی HTML برای پس‌زمینه Dark
   - تبدیل متن‌های تیره به روشن
   - اصلاح بک‌گراندهای روشن
   - آماده‌سازی تصویر و لینک
   ------------------------------------------------------------------ */
function optimizeHtmlForDarkExport(html) {
  if (!html || typeof html !== "string" || html.trim() === "") {
    return html || "";
  }

  // حالت SSR یا محیطی که document ندارد
  if (typeof document === "undefined") {
    return html.replace(
      /color:\s*(black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0,\s*[01]\))/gi,
      "color: #f8fafc"
    );
  }

  try {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;

    function isDarkColor(colorValue) {
      if (!colorValue) return false;

      const color = colorValue.trim().toLowerCase();

      const darkNamedColors = [
        "black",
        "navy",
        "maroon",
        "darkblue",
        "darkgreen",
        "darkred",
        "darkorange",
        "darkviolet",
        "darkslategray",
        "dimgray",
        "dimgrey",
        "midnightblue",
        "olive",
        "teal",
        "darkcyan",
        "darkmagenta",
        "darkgray",
      ];

      if (darkNamedColors.includes(color)) return true;
      if (color.startsWith("dark")) return true;

      let r;
      let g;
      let b;

      const rgbMatch = color.match(
        /rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i
      );

      if (rgbMatch) {
        r = parseInt(rgbMatch[1], 10);
        g = parseInt(rgbMatch[2], 10);
        b = parseInt(rgbMatch[3], 10);
      } else if (color.startsWith("#")) {
        const hex = color.replace("#", "");

        if (hex.length === 3) {
          r = parseInt(hex[0] + hex[0], 16);
          g = parseInt(hex[1] + hex[1], 16);
          b = parseInt(hex[2] + hex[2], 16);
        } else if (hex.length === 6) {
          r = parseInt(hex.slice(0, 2), 16);
          g = parseInt(hex.slice(2, 4), 16);
          b = parseInt(hex.slice(4, 6), 16);
        } else {
          return false;
        }
      } else {
        return false;
      }

      if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) {
        return false;
      }

      const brightness = (r * 299 + g * 587 + b * 114) / 1000;

      return brightness < 135;
    }

    const elements = wrapper.querySelectorAll("*");

    elements.forEach((element) => {
      // تبدیل رنگ inline تیره به سفید
      const inlineColor = element.style?.color;

      if (inlineColor && isDarkColor(inlineColor)) {
        element.style.color = "#f8fafc";
        element.style.textShadow = "0 0 10px rgba(255,255,255,0.08)";
      }

      // اصلاح بک‌گراندهای روشن
      const inlineBackground = element.style?.backgroundColor;

      if (inlineBackground) {
        const bg = inlineBackground.trim().toLowerCase();

        const isLightBackground =
          bg === "white" ||
          bg === "#fff" ||
          bg === "#ffffff" ||
          bg === "yellow" ||
          bg === "#ffff00" ||
          bg.includes("rgb(255, 255, 255)") ||
          bg.includes("rgb(255, 255, 0)") ||
          bg.includes("rgba(255, 255, 255,");

        if (isLightBackground) {
          element.style.backgroundColor = "rgba(255, 255, 255, 0.10)";
          element.style.padding = "0.08em 0.35em";
          element.style.borderRadius = "0.35em";
        }
      }

      // کلاس‌های رنگ Quill
      if (element.classList) {
        const classes = Array.from(element.classList);

        classes.forEach((className) => {
          if (className.startsWith("ql-color-")) {
            const colorName = className.replace("ql-color-", "");

            const darkColors = [
              "black",
              "dark",
              "gray",
              "grey",
              "navy",
              "darkblue",
              "darkgreen",
              "darkred",
              "darkorange",
              "darkviolet",
              "darkslategray",
              "dimgray",
              "dimgrey",
              "midnightblue",
              "olive",
              "teal",
            ];

            if (darkColors.includes(colorName)) {
              element.classList.remove(className);
              element.classList.add("ql-color-white");
            }
          }

          if (className.startsWith("ql-bg-")) {
            const backgroundName = className.replace("ql-bg-", "");

            const lightBackgrounds = [
              "white",
              "yellow",
              "lightyellow",
              "lightgray",
              "lightgrey",
            ];

            if (lightBackgrounds.includes(backgroundName)) {
              element.classList.remove(className);
              element.classList.add("ql-bg-transparent-dark");
            }
          }
        });
      }
    });

    // بهینه‌سازی تصاویر
    wrapper.querySelectorAll("img").forEach((image) => {
      if (!image.hasAttribute("loading")) {
        image.setAttribute("loading", "lazy");
      }

      if (!image.hasAttribute("decoding")) {
        image.setAttribute("decoding", "async");
      }
    });

    // امنیت لینک‌های خارجی
    wrapper.querySelectorAll("a[target='_blank']").forEach((link) => {
      if (!link.getAttribute("rel")) {
        link.setAttribute("rel", "noopener noreferrer");
      }
    });

    return wrapper.innerHTML;
  } catch (error) {
    console.warn("optimizeHtmlForDarkExport failed:", error);
    return html;
  }
}

/* ------------------------------------------------------------------
   تبدیل متن ساده به HTML
   ------------------------------------------------------------------ */
function bodyToHtml(bodyLines) {
  if (!bodyLines || !bodyLines.length) {
    return `
      <div class="empty-content-state">
        <i class="fas fa-file-circle-xmark" aria-hidden="true"></i>
        <p>محتوایی ثبت نشده است.</p>
      </div>
    `;
  }

  let html = "";
  let inList = false;
  let listType = "";

  bodyLines.forEach((line) => {
    if (isHeading(line)) {
      if (inList) {
        html += `</${listType}>`;
        inList = false;
        listType = "";
      }

      html += `
        <h2 class="content-heading scroll-reveal" data-delay="50">
          <span class="heading-dot"></span>
          ${escapeHtml(cleanHeading(line))}
        </h2>
      `;

      return;
    }

    if (isBullet(line)) {
      if (!inList || listType !== "ul") {
        if (inList) {
          html += `</${listType}>`;
        }

        html += `<ul class="styled-list scroll-reveal" data-delay="30">`;
        inList = true;
        listType = "ul";
      }

      html += `
        <li>
          <span class="bullet-icon" aria-hidden="true">
            <i class="fas fa-sparkles"></i>
          </span>
          <span>${escapeHtml(getBulletText(line))}</span>
        </li>
      `;

      return;
    }

    if (isNumbered(line)) {
      if (!inList || listType !== "ol") {
        if (inList) {
          html += `</${listType}>`;
        }

        html += `<ol class="styled-list numbered scroll-reveal" data-delay="30">`;
        inList = true;
        listType = "ol";
      }

      html += `
        <li>
          <span class="number-badge">${escapeHtml(getNumber(line))}</span>
          <span>${escapeHtml(getNumberedText(line))}</span>
        </li>
      `;

      return;
    }

    if (inList) {
      html += `</${listType}>`;
      inList = false;
      listType = "";
    }

    html += `
      <p class="content-paragraph scroll-reveal" data-delay="20">
        ${escapeHtml(line)}
      </p>
    `;
  });

  if (inList) {
    html += `</${listType}>`;
  }

  return html;
}

/* ------------------------------------------------------------------
   استخراج امن بدنه محتوا
   ------------------------------------------------------------------ */
function getContentBody(content) {
  const rawBodyValue =
    content?.body ??
    content?.content ??
    content?.html ??
    content?.text ??
    content?.data ??
    content?.value ??
    "";

  if (typeof rawBodyValue === "string") {
    return rawBodyValue;
  }

  if (Array.isArray(rawBodyValue)) {
    return rawBodyValue.filter(Boolean).join("\n");
  }

  // پشتیبانی محدود از Quill Delta
  if (rawBodyValue && typeof rawBodyValue === "object" && rawBodyValue.ops) {
    try {
      return rawBodyValue.ops
        .map((operation) =>
          operation?.insert && typeof operation.insert === "string"
            ? operation.insert
            : ""
        )
        .join("");
    } catch (error) {
      return "";
    }
  }

  return "";
}

/* ------------------------------------------------------------------
   تابع اصلی ساخت فایل HTML
   ------------------------------------------------------------------ */
export function getExportHtml({ topic = {}, content = {}, topicId } = {}) {
  const title = escapeHtml(
    content?.title || topic?.title || DEFAULT_TITLE
  );

  const topicTitle = escapeHtml(topic?.title || "بدون عنوان");

  const description = escapeHtml(
    topic?.description ||
      "محتوای آموزشی تولیدشده توسط سامانه هوشمند آموزش"
  );

  const summary = content?.summary
    ? escapeHtml(content.summary)
    : "";

  const objectives = Array.isArray(content?.learning_objectives)
    ? content.learning_objectives
        .filter(Boolean)
        .map((item) => String(item))
    : [];

  const objectivesHtml = objectives.length
    ? `
      <section class="glass-card objectives-section scroll-reveal" data-delay="250">
        <div class="card-header">
          <span class="card-icon icon-objective" aria-hidden="true">🎯</span>
          <h3 class="header-objectives">اهداف یادگیری</h3>
        </div>

        <div class="badge-container">
          ${objectives
            .map(
              (item) => `
                <span class="badge scroll-reveal" data-delay="30">
                  <i class="fas fa-check" aria-hidden="true"></i>
                  ${escapeHtml(item)}
                </span>
              `
            )
            .join("")}
        </div>
      </section>
    `
    : "";

  const bodyRaw = getContentBody(content);
  const bodyTrimmed = bodyRaw.trim();

  const looksLikeHtml =
    bodyTrimmed.length > 0 &&
    (isHtmlContent(bodyTrimmed) || /<\/?[a-z][\s\S]*>/i.test(bodyTrimmed));

  let bodyHtml = "";

  if (!bodyTrimmed) {
    bodyHtml = `
      <div class="empty-content-state">
        <i class="fas fa-file-circle-xmark" aria-hidden="true"></i>
        <p>محتوایی برای نمایش وجود ندارد.</p>
        <small>بررسی کنید که محتوا در فیلد body یا content ذخیره شده باشد.</small>
      </div>
    `;
  } else if (looksLikeHtml) {
    const optimizedBody = optimizeHtmlForDarkExport(bodyTrimmed);

    bodyHtml = `
      <div class="html-content-wrapper" dir="rtl">
        ${optimizedBody}
      </div>
    `;
  } else {
    let bodyLines = [];

    try {
      bodyLines = getBodyLines({
        ...content,
        body: bodyTrimmed,
      });
    } catch (error) {
      console.warn("getBodyLines failed, fallback is used:", error);
    }

    if (!Array.isArray(bodyLines) || bodyLines.length === 0) {
      bodyLines = bodyTrimmed
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
    }

    bodyHtml = bodyToHtml(bodyLines);
  }

  return `<!doctype html>
<html lang="fa" dir="rtl" class="no-js">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="${description}">
  <title>${title}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link
    href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800;900&display=swap"
    rel="stylesheet"
  >
  <link
    rel="stylesheet"
    href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"
  >

  <script>
    document.documentElement.classList.remove("no-js");
    document.documentElement.classList.add("js-enabled");
  </script>

  <style>
    :root {
      --bg-primary: #070b14;
      --bg-secondary: #101827;
      --bg-card: rgba(15, 23, 42, 0.72);
      --bg-card-hover: rgba(25, 38, 65, 0.82);

      --text-primary: #f8fafc;
      --text-secondary: #cbd5e1;
      --text-muted: #94a3b8;

      --accent-cyan: #22d3ee;
      --accent-blue: #60a5fa;
      --accent-indigo: #818cf8;
      --accent-violet: #a78bfa;
      --accent-pink: #f472b6;
      --accent-rose: #fb7185;
      --accent-amber: #fbbf24;
      --accent-emerald: #34d399;

      --border-color: rgba(148, 163, 184, 0.16);
      --border-bright: rgba(34, 211, 238, 0.40);

      --shadow-card: 0 20px 55px rgba(0, 0, 0, 0.42);
      --shadow-neon: 0 0 32px rgba(34, 211, 238, 0.14);

      --font-family: "Vazirmatn", Tahoma, "Segoe UI", sans-serif;
      --radius-card: 1.35rem;
      --radius-sm: 0.65rem;
      --max-width: 1180px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    html {
      scroll-behavior: smooth;
    }

    body {
      min-height: 100vh;
      overflow-x: hidden;
      padding: 2rem 1rem;
      direction: rtl;
      color: var(--text-primary);
      background:
        radial-gradient(circle at 8% 4%, rgba(99, 102, 241, 0.20), transparent 28%),
        radial-gradient(circle at 90% 24%, rgba(34, 211, 238, 0.12), transparent 30%),
        radial-gradient(circle at 48% 90%, rgba(168, 85, 247, 0.16), transparent 36%),
        var(--bg-primary);
      font-family: var(--font-family);
      line-height: 2;
      -webkit-font-smoothing: antialiased;
    }

    /* پس‌زمینه متحرک با رنگ‌های شادتر */
    .bg-orbs {
      position: fixed;
      z-index: 0;
      inset: 0;
      overflow: hidden;
      pointer-events: none;
    }

    .orb {
      position: absolute;
      border-radius: 50%;
      filter: blur(90px);
      opacity: 0.25;
      animation: floatOrb 15s ease-in-out infinite alternate;
    }

    .orb-1 {
      top: -180px;
      right: -130px;
      width: 480px;
      height: 480px;
      background: #4f46e5;
      animation-duration: 18s;
    }

    .orb-2 {
      bottom: -220px;
      left: -150px;
      width: 550px;
      height: 550px;
      background: #ec4899;
      animation-delay: -5s;
      animation-duration: 20s;
    }

    .orb-3 {
      top: 42%;
      left: 37%;
      width: 310px;
      height: 310px;
      background: #06b6d4;
      opacity: 0.15;
      animation-delay: -10s;
      animation-duration: 16s;
    }

    @keyframes floatOrb {
      from {
        transform: translate3d(0, 0, 0) scale(1);
      }

      to {
        transform: translate3d(45px, -30px, 0) scale(1.15);
      }
    }

    .container {
      position: relative;
      z-index: 1;
      width: min(100%, var(--max-width));
      margin: 0 auto;
      padding: 1.5rem 0;
    }

    /* ============================================================
       Hero با انیمیشن شیمِر
       ============================================================ */
    .hero {
      padding: 3.5rem 1rem 3rem;
      text-align: center;
    }

    .hero-title {
      margin-bottom: 1.15rem;
      font-size: clamp(2.2rem, 6vw, 4.1rem);
      font-weight: 900;
      line-height: 1.35;
      letter-spacing: -0.04em;
      background: linear-gradient(
        120deg,
        #ffffff 0%,
        var(--accent-cyan) 30%,
        var(--accent-violet) 60%,
        var(--accent-pink) 90%,
        #ffffff 100%
      );
      background-size: 300% auto;
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
      animation: shimmerTitle 8s ease-in-out infinite;
      filter: drop-shadow(0 0 25px rgba(34, 211, 238, 0.20));
    }

    @keyframes shimmerTitle {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
    }

    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 0.75rem 1.4rem;
      color: var(--text-secondary);
    }

    .meta-item {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.42rem 0.9rem;
      border: 1px solid rgba(148, 163, 184, 0.12);
      border-radius: 2rem;
      background: rgba(15, 23, 42, 0.42);
      backdrop-filter: blur(8px);
      transition: transform 0.25s ease, background 0.25s ease;
    }

    .meta-item:hover {
      transform: translateY(-2px);
      background: rgba(34, 211, 238, 0.08);
      border-color: var(--accent-cyan);
    }

    .meta-item i {
      color: var(--accent-cyan);
    }

    .meta-item strong {
      color: var(--text-primary);
    }

    /* ============================================================
       Glass Card با انیمیشن و تیترهای رنگی بزرگ
       ============================================================ */
    .glass-card {
      position: relative;
      overflow: hidden;
      margin-bottom: 2rem;
      padding: 1.8rem 2rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-card);
      background:
        linear-gradient(
          135deg,
          rgba(255, 255, 255, 0.055),
          rgba(255, 255, 255, 0.012)
        ),
        var(--bg-card);
      box-shadow: var(--shadow-card);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      transition:
        transform 0.4s cubic-bezier(0.16, 1, 0.3, 1),
        border-color 0.4s ease,
        box-shadow 0.4s ease,
        background 0.4s ease;
    }

    .glass-card::before {
      position: absolute;
      top: 0;
      right: 0;
      left: 0;
      height: 3px;
      content: "";
      background: linear-gradient(
        90deg,
        transparent,
        var(--accent-cyan),
        var(--accent-violet),
        var(--accent-pink),
        transparent
      );
      opacity: 0.7;
      animation: shimmerBorder 6s ease-in-out infinite;
    }

    @keyframes shimmerBorder {
      0% { background-position: -300% 0; }
      100% { background-position: 300% 0; }
    }

    .glass-card:hover {
      border-color: var(--border-bright);
      background: var(--bg-card-hover);
      box-shadow: var(--shadow-card), var(--shadow-neon);
      transform: translateY(-8px) scale(1.005);
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      margin-bottom: 1.1rem;
    }

    .card-icon {
      display: inline-grid;
      width: 2.7rem;
      height: 2.7rem;
      place-items: center;
      border: 1px solid rgba(34, 211, 238, 0.25);
      border-radius: 0.85rem;
      background: rgba(34, 211, 238, 0.10);
      box-shadow: 0 0 20px rgba(34, 211, 238, 0.10);
      font-size: 1.35rem;
      flex-shrink: 0;
    }

    .icon-summary {
      border-color: rgba(251, 191, 36, 0.30);
      background: rgba(251, 191, 36, 0.10);
    }

    .icon-objective {
      border-color: rgba(52, 211, 153, 0.30);
      background: rgba(52, 211, 153, 0.10);
    }

    /* تیترهای رنگی با پس‌زمینه و فونت بزرگ */
    .card-header h3 {
      display: inline-block;
      padding: 0.3rem 1.4rem;
      border-radius: 2rem;
      font-size: clamp(1.6rem, 3vw, 2.2rem);
      font-weight: 900;
      color: #ffffff;
      text-shadow: 0 2px 12px rgba(0,0,0,0.3);
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
      backdrop-filter: blur(4px);
      transition: transform 0.3s ease, box-shadow 0.3s ease;
      letter-spacing: 0.02em;
    }

    .card-header h3:hover {
      transform: scale(1.04);
      box-shadow: 0 6px 30px rgba(0,0,0,0.35);
    }

    .header-intro {
      background: linear-gradient(135deg, #4f46e5, #7c3aed);
    }

    .header-summary {
      background: linear-gradient(135deg, #f59e0b, #ea580c);
    }

    .header-objectives {
      background: linear-gradient(135deg, #10b981, #059669);
    }

    .header-content {
      background: linear-gradient(135deg, #ec4899, #8b5cf6);
    }

    .glass-card > p {
      color: var(--text-secondary);
      font-size: 1.05rem;
      text-align: justify;
    }

    .summary-card {
      border-right: 4px solid var(--accent-amber);
    }

    .summary-card::before {
      background: linear-gradient(
        90deg,
        transparent,
        var(--accent-amber),
        var(--accent-rose),
        transparent
      );
    }

    /* ============================================================
       Objectives
       ============================================================ */
    .badge-container {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.5rem 1rem;
      border: 1px solid rgba(52, 211, 153, 0.24);
      border-radius: 2rem;
      color: #d1fae5;
      background: rgba(52, 211, 153, 0.09);
      font-size: 0.94rem;
      transition: transform 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
    }

    .badge i {
      color: var(--accent-emerald);
      font-size: 0.78rem;
    }

    .badge:hover {
      background: rgba(52, 211, 153, 0.22);
      transform: translateY(-4px) scale(1.02);
      box-shadow: 0 8px 20px rgba(52, 211, 153, 0.20);
    }

    /* ============================================================
       Plain Text Content
       ============================================================ */
    .content-heading {
      position: relative;
      display: flex;
      align-items: center;
      gap: 0.7rem;
      margin: 2.8rem 0 1.3rem;
      padding: 0.7rem 1rem;
      border: 1px solid rgba(34, 211, 238, 0.20);
      border-right: 5px solid var(--accent-cyan);
      border-radius: 0.8rem;
      color: #ffffff;
      background: linear-gradient(
        90deg,
        rgba(34, 211, 238, 0.13),
        rgba(139, 92, 246, 0.08),
        transparent
      );
      box-shadow: 0 8px 30px rgba(34, 211, 238, 0.06);
      font-size: clamp(1.35rem, 3vw, 2rem);
      font-weight: 900;
      line-height: 1.5;
      transition: transform 0.3s ease, box-shadow 0.3s ease;
    }

    .content-heading:hover {
      transform: translateX(-6px);
      box-shadow: 0 8px 40px rgba(34, 211, 238, 0.15);
    }

    .heading-dot {
      display: inline-block;
      width: 0.7rem;
      height: 0.7rem;
      flex: 0 0 auto;
      border-radius: 50%;
      background: var(--accent-cyan);
      box-shadow: 0 0 15px var(--accent-cyan);
      animation: pulseDot 2s ease-in-out infinite;
    }

    @keyframes pulseDot {
      0%, 100% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.5); opacity: 0.6; }
    }

    .content-paragraph {
      margin-bottom: 1.2rem;
      padding: 0.9rem 1rem;
      border-right: 2px solid rgba(96, 165, 250, 0.30);
      border-radius: 0.6rem;
      color: var(--text-secondary);
      background: rgba(255, 255, 255, 0.018);
      font-size: 1.05rem;
      line-height: 2.2;
      text-align: justify;
      transition: transform 0.25s ease, background 0.25s ease;
    }

    .content-paragraph:hover {
      background: rgba(255, 255, 255, 0.04);
      transform: translateX(-4px);
    }

    .styled-list {
      display: grid;
      gap: 0.7rem;
      margin: 1.2rem 0 1.8rem;
      padding: 0;
      list-style: none;
    }

    .styled-list li {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      padding: 0.8rem 0.9rem;
      border: 1px solid rgba(148, 163, 184, 0.10);
      border-radius: 0.8rem;
      color: var(--text-secondary);
      background: rgba(255, 255, 255, 0.025);
      transition: transform 0.3s ease, border-color 0.3s ease, background 0.3s ease;
    }

    .styled-list li:hover {
      border-color: rgba(34, 211, 238, 0.35);
      background: rgba(34, 211, 238, 0.06);
      transform: translateX(-6px);
    }

    .bullet-icon {
      display: inline-grid;
      width: 1.75rem;
      height: 1.75rem;
      flex: 0 0 auto;
      place-items: center;
      border-radius: 50%;
      color: #06101a;
      background: var(--accent-cyan);
      box-shadow: 0 0 15px rgba(34, 211, 238, 0.40);
      font-size: 0.65rem;
      transition: transform 0.3s ease;
    }

    .styled-list li:hover .bullet-icon {
      transform: rotate(20deg) scale(1.1);
    }

    .number-badge {
      display: inline-grid;
      width: 2rem;
      height: 2rem;
      flex: 0 0 auto;
      place-items: center;
      border: 1px solid rgba(129, 140, 248, 0.50);
      border-radius: 50%;
      color: #e0e7ff;
      background: rgba(99, 102, 241, 0.25);
      box-shadow: 0 0 16px rgba(129, 140, 248, 0.16);
      font-size: 0.88rem;
      font-weight: 800;
      transition: transform 0.3s ease, background 0.3s ease;
    }

    .styled-list li:hover .number-badge {
      transform: scale(1.15);
      background: rgba(99, 102, 241, 0.45);
    }

    /* ============================================================
       Quill / HTML Content
       ============================================================ */
    .html-content-wrapper {
      color: var(--text-secondary);
      font-size: 1.05rem;
      line-height: 2.2;
    }

    .html-content-wrapper h1,
    .html-content-wrapper h2,
    .html-content-wrapper h3,
    .html-content-wrapper h4,
    .html-content-wrapper h5,
    .html-content-wrapper h6 {
      position: relative;
      margin: 2.7rem 0 1.2rem;
      padding: 0.75rem 1rem;
      border-radius: 0.8rem;
      font-weight: 900;
      line-height: 1.55;
      transition: transform 0.3s ease;
    }

    .html-content-wrapper h1:hover,
    .html-content-wrapper h2:hover,
    .html-content-wrapper h3:hover,
    .html-content-wrapper h4:hover,
    .html-content-wrapper h5:hover,
    .html-content-wrapper h6:hover {
      transform: translateX(-4px);
    }

    .html-content-wrapper h1 {
      border-right: 6px solid var(--accent-pink);
      color: #ffffff;
      background: linear-gradient(
        90deg,
        rgba(244, 114, 182, 0.20),
        rgba(139, 92, 246, 0.10),
        transparent
      );
      font-size: clamp(1.8rem, 3.4vw, 2.65rem);
    }

    .html-content-wrapper h2 {
      border-right: 5px solid var(--accent-cyan);
      color: #cffafe;
      background: linear-gradient(
        90deg,
        rgba(34, 211, 238, 0.16),
        rgba(59, 130, 246, 0.08),
        transparent
      );
      font-size: clamp(1.5rem, 2.8vw, 2.15rem);
    }

    .html-content-wrapper h3 {
      border-right: 4px solid var(--accent-amber);
      color: #fde68a;
      background: linear-gradient(
        90deg,
        rgba(251, 191, 36, 0.14),
        transparent
      );
      font-size: clamp(1.3rem, 2.2vw, 1.75rem);
    }

    .html-content-wrapper h4,
    .html-content-wrapper h5,
    .html-content-wrapper h6 {
      border-right: 4px solid var(--accent-violet);
      color: #ddd6fe;
      background: linear-gradient(
        90deg,
        rgba(167, 139, 250, 0.14),
        transparent
      );
      font-size: clamp(1.1rem, 1.9vw, 1.45rem);
    }

    .html-content-wrapper p {
      margin-bottom: 1.15rem;
      padding: 0.7rem 0.95rem;
      border-right: 2px solid rgba(96, 165, 250, 0.26);
      border-radius: 0.5rem;
      background: rgba(255, 255, 255, 0.018);
      text-align: justify;
      transition: transform 0.25s ease, background 0.25s ease;
    }

    .html-content-wrapper p:hover {
      background: rgba(255, 255, 255, 0.04);
      transform: translateX(-4px);
    }

    .html-content-wrapper ul,
    .html-content-wrapper ol {
      display: grid;
      gap: 0.55rem;
      margin: 1.2rem 0 1.6rem;
      padding-right: 1.75rem;
    }

    .html-content-wrapper li {
      padding: 0.25rem 0.4rem;
      transition: transform 0.25s ease;
    }

    .html-content-wrapper li:hover {
      transform: translateX(-4px);
    }

    .html-content-wrapper li::marker {
      color: var(--accent-cyan);
      font-weight: 900;
    }

    .html-content-wrapper a {
      color: var(--accent-cyan);
      text-decoration-color: rgba(34, 211, 238, 0.45);
      text-underline-offset: 0.22em;
      transition: color 0.3s ease;
    }

    .html-content-wrapper a:hover {
      color: var(--accent-amber);
    }

    .html-content-wrapper blockquote {
      margin: 1.5rem 0;
      padding: 1rem 1.25rem;
      border: 1px solid rgba(167, 139, 250, 0.25);
      border-right: 5px solid var(--accent-violet);
      border-radius: 0.85rem;
      color: #e9d5ff;
      background: rgba(139, 92, 246, 0.10);
      transition: transform 0.3s ease, background 0.3s ease;
    }

    .html-content-wrapper blockquote:hover {
      transform: translateX(-4px);
      background: rgba(139, 92, 246, 0.18);
    }

    .html-content-wrapper img {
      display: block;
      max-width: 100%;
      height: auto;
      margin: 1.5rem auto;
      border: 1px solid rgba(34, 211, 238, 0.20);
      border-radius: 1rem;
      box-shadow: 0 15px 40px rgba(0, 0, 0, 0.40);
      transition: transform 0.4s ease, box-shadow 0.4s ease;
    }

    .html-content-wrapper img:hover {
      transform: scale(1.01);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.50);
    }

    .html-content-wrapper table {
      width: 100%;
      margin: 1.5rem 0;
      overflow: hidden;
      border: 1px solid rgba(148, 163, 184, 0.18);
      border-collapse: separate;
      border-spacing: 0;
      border-radius: 0.8rem;
      transition: box-shadow 0.3s ease;
    }

    .html-content-wrapper table:hover {
      box-shadow: 0 8px 30px rgba(0,0,0,0.3);
    }

    .html-content-wrapper th,
    .html-content-wrapper td {
      padding: 0.75rem 0.9rem;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
      text-align: right;
    }

    .html-content-wrapper th {
      color: #cffafe;
      background: rgba(34, 211, 238, 0.12);
      font-weight: 800;
    }

    .html-content-wrapper tr:last-child td {
      border-bottom: none;
    }

    .html-content-wrapper pre {
      direction: ltr;
      margin: 1.3rem 0;
      padding: 1rem 1.2rem;
      overflow-x: auto;
      border: 1px solid rgba(34, 211, 238, 0.14);
      border-radius: 0.8rem;
      color: #bae6fd;
      background: rgba(0, 0, 0, 0.38);
      font-family: Consolas, Monaco, monospace;
      text-align: left;
      transition: transform 0.3s ease;
    }

    .html-content-wrapper pre:hover {
      transform: scale(1.005);
    }

    .html-content-wrapper code {
      padding: 0.12rem 0.38rem;
      border-radius: 0.35rem;
      color: #a5f3fc;
      background: rgba(34, 211, 238, 0.10);
      font-family: Consolas, Monaco, monospace;
      font-size: 0.9em;
    }

    .html-content-wrapper iframe,
    .html-content-wrapper .ql-video {
      max-width: 100%;
      margin: 1.2rem 0;
      border: 0;
      border-radius: 0.85rem;
      box-shadow: 0 10px 35px rgba(0, 0, 0, 0.36);
      transition: transform 0.3s ease;
    }

    .html-content-wrapper iframe:hover,
    .html-content-wrapper .ql-video:hover {
      transform: scale(1.01);
    }

    /* Quill alignment */
    .html-content-wrapper .ql-align-center {
      text-align: center !important;
    }

    .html-content-wrapper .ql-align-right {
      text-align: right !important;
    }

    .html-content-wrapper .ql-align-left {
      text-align: left !important;
    }

    .html-content-wrapper .ql-align-justify {
      text-align: justify !important;
    }

    .html-content-wrapper .ql-direction-rtl {
      direction: rtl !important;
    }

    .html-content-wrapper .ql-direction-ltr {
      direction: ltr !important;
    }

    /* Quill indentation */
    .html-content-wrapper .ql-indent-1 { padding-right: 2.5rem !important; }
    .html-content-wrapper .ql-indent-2 { padding-right: 5rem !important; }
    .html-content-wrapper .ql-indent-3 { padding-right: 7.5rem !important; }
    .html-content-wrapper .ql-indent-4 { padding-right: 10rem !important; }
    .html-content-wrapper .ql-indent-5 { padding-right: 12.5rem !important; }
    .html-content-wrapper .ql-indent-6 { padding-right: 15rem !important; }
    .html-content-wrapper .ql-indent-7 { padding-right: 17.5rem !important; }
    .html-content-wrapper .ql-indent-8 { padding-right: 20rem !important; }

    /* Quill colors */
    .html-content-wrapper .ql-color-white { color: #f8fafc !important; }
    .html-content-wrapper .ql-color-red { color: #fb7185 !important; }
    .html-content-wrapper .ql-color-orange { color: #fb923c !important; }
    .html-content-wrapper .ql-color-yellow { color: #facc15 !important; }
    .html-content-wrapper .ql-color-green { color: #34d399 !important; }
    .html-content-wrapper .ql-color-blue { color: #60a5fa !important; }
    .html-content-wrapper .ql-color-purple { color: #c084fc !important; }
    .html-content-wrapper .ql-color-pink { color: #f472b6 !important; }

    .html-content-wrapper .ql-bg-transparent-dark {
      padding: 0.08em 0.3em;
      border-radius: 0.3em;
      background: rgba(255, 255, 255, 0.08) !important;
    }

    .html-content-wrapper .ql-bg-yellow {
      background: rgba(251, 191, 36, 0.17) !important;
    }

    .html-content-wrapper .ql-bg-red {
      background: rgba(251, 113, 133, 0.16) !important;
    }

    .html-content-wrapper .ql-bg-blue {
      background: rgba(96, 165, 250, 0.16) !important;
    }

    .html-content-wrapper .ql-bg-green {
      background: rgba(52, 211, 153, 0.16) !important;
    }

    /* ============================================================
       Empty State
       ============================================================ */
    .empty-content-state {
      display: grid;
      min-height: 190px;
      place-content: center;
      gap: 0.7rem;
      padding: 2rem;
      border: 1px dashed rgba(148, 163, 184, 0.30);
      border-radius: 1rem;
      color: var(--text-muted);
      background: rgba(255, 255, 255, 0.025);
      text-align: center;
    }

    .empty-content-state i {
      color: var(--accent-cyan);
      font-size: 2.4rem;
    }

    .empty-content-state p {
      color: var(--text-secondary);
    }

    .empty-content-state small {
      color: var(--text-muted);
    }

    /* ============================================================
       Safe Scroll Reveal Animation (با افکت‌های بیشتر)
       ============================================================ */
    .scroll-reveal {
      opacity: 1;
      transform: none;
    }

    @media (prefers-reduced-motion: no-preference) {
      .js-enabled.reveal-ready .scroll-reveal:not(.is-visible) {
        opacity: 0;
        transform: translateY(40px) scale(0.96);
      }

      .js-enabled.reveal-ready .scroll-reveal {
        transition:
          opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1),
          transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        will-change: opacity, transform;
      }

      .js-enabled.reveal-ready .scroll-reveal.is-visible {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }

    .always-visible {
      opacity: 1 !important;
      transform: none !important;
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
      }

      .scroll-reveal,
      .js-enabled.reveal-ready .scroll-reveal,
      .js-enabled.reveal-ready .scroll-reveal:not(.is-visible) {
        opacity: 1 !important;
        transform: none !important;
        transition: none !important;
      }
    }

    /* ============================================================
       Footer
       ============================================================ */
    .footer {
      margin-top: 3rem;
      padding: 2.4rem 1rem;
      border: 1px solid var(--border-color);
      border-radius: var(--radius-card);
      background: rgba(15, 23, 42, 0.55);
      text-align: center;
      transition: transform 0.3s ease, background 0.3s ease;
    }

    .footer:hover {
      transform: translateY(-4px);
      background: rgba(15, 23, 42, 0.75);
      border-color: var(--border-bright);
    }

    .footer .brand {
      display: inline-block;
      margin-bottom: 0.5rem;
      background: linear-gradient(
        120deg,
        var(--accent-cyan),
        var(--accent-violet),
        var(--accent-pink)
      );
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
      font-size: clamp(1.4rem, 3vw, 2rem);
      font-weight: 900;
      text-decoration: none;
      transition: transform 0.3s ease;
    }

    .footer .brand:hover {
      transform: scale(1.03);
    }

    .footer p {
      color: var(--text-muted);
    }

    .footer p span {
      color: var(--accent-cyan) !important;
    }

    /* ============================================================
       Buttons با انیمیشن
       ============================================================ */
    .print-btn,
    .back-to-top {
      display: none;
    }

    .js-enabled .print-btn,
    .js-enabled .back-to-top {
      position: fixed;
      z-index: 100;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: white;
      cursor: pointer;
      font-family: var(--font-family);
      backdrop-filter: blur(12px);
      transition: transform 0.3s ease, background 0.3s ease, box-shadow 0.3s ease;
    }

    .js-enabled .print-btn {
      right: 1.5rem;
      bottom: 1.5rem;
      gap: 0.5rem;
      padding: 0.65rem 1.1rem;
      border-radius: 2rem;
      background: rgba(15, 23, 42, 0.78);
    }

    .js-enabled .back-to-top {
      bottom: 1.5rem;
      left: 1.5rem;
      width: 3rem;
      height: 3rem;
      border-radius: 50%;
      background: var(--accent-indigo);
      box-shadow: 0 0 20px rgba(129, 140, 248, 0.35);
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      transition: opacity 0.4s ease, visibility 0.4s ease, transform 0.3s ease;
    }

    .js-enabled .back-to-top.visible {
      opacity: 1;
      visibility: visible;
      pointer-events: auto;
    }

    .js-enabled .print-btn:hover,
    .js-enabled .back-to-top:hover {
      background: var(--accent-violet);
      transform: translateY(-4px) scale(1.05);
      box-shadow: 0 8px 30px rgba(129, 140, 248, 0.45);
    }

    /* ============================================================
       Responsive
       ============================================================ */
    @media (max-width: 768px) {
      body {
        padding: 1rem 0.65rem;
      }

      .container {
        padding: 0.5rem 0;
      }

      .hero {
        padding: 2.4rem 0.5rem;
      }

      .hero-meta {
        flex-direction: column;
        align-items: center;
      }

      .glass-card {
        padding: 1.3rem 1rem;
      }

      .card-header h3 {
        font-size: clamp(1.3rem, 4vw, 1.6rem);
        padding: 0.2rem 1rem;
      }

      .content-paragraph,
      .html-content-wrapper p {
        text-align: right;
      }

      .html-content-wrapper .ql-indent-1 { padding-right: 1.2rem !important; }
      .html-content-wrapper .ql-indent-2 { padding-right: 2.4rem !important; }
      .html-content-wrapper .ql-indent-3 { padding-right: 3.6rem !important; }
      .html-content-wrapper .ql-indent-4 { padding-right: 4.8rem !important; }
      .html-content-wrapper .ql-indent-5 { padding-right: 6rem !important; }
      .html-content-wrapper .ql-indent-6 { padding-right: 7.2rem !important; }
      .html-content-wrapper .ql-indent-7 { padding-right: 8.4rem !important; }
      .html-content-wrapper .ql-indent-8 { padding-right: 9.6rem !important; }

      .js-enabled .print-btn {
        right: 1rem;
        bottom: 1rem;
        padding: 0.5rem 0.85rem;
        font-size: 0.82rem;
      }

      .js-enabled .back-to-top {
        bottom: 1rem;
        left: 1rem;
        width: 2.7rem;
        height: 2.7rem;
      }
    }

    /* ============================================================
       Print / PDF
       ============================================================ */
    @media print {
      body {
        padding: 0.5in !important;
        color: #0f172a !important;
        background: #ffffff !important;
        font-size: 12pt !important;
      }

      .bg-orbs,
      .print-btn,
      .back-to-top {
        display: none !important;
      }

      .glass-card,
      .footer {
        break-inside: avoid;
        page-break-inside: avoid;
        border: 1px solid #cbd5e1 !important;
        background: #ffffff !important;
        box-shadow: none !important;
        backdrop-filter: none !important;
      }

      .glass-card::before {
        display: none !important;
      }

      .hero-title,
      .footer .brand {
        color: #0f172a !important;
        background: none !important;
        -webkit-text-fill-color: #0f172a !important;
        animation: none !important;
      }

      .hero-meta,
      .glass-card p,
      .content-paragraph,
      .html-content-wrapper,
      .html-content-wrapper p,
      .footer p {
        color: #1e293b !important;
      }

      .content-heading,
      .html-content-wrapper h1,
      .html-content-wrapper h2,
      .html-content-wrapper h3,
      .html-content-wrapper h4,
      .html-content-wrapper h5,
      .html-content-wrapper h6 {
        color: #0f172a !important;
        background: #f8fafc !important;
        box-shadow: none !important;
      }

      .styled-list li,
      .html-content-wrapper blockquote {
        color: #1e293b !important;
        background: #f8fafc !important;
      }

      .html-content-wrapper pre,
      .html-content-wrapper code {
        color: #0f172a !important;
        background: #f1f5f9 !important;
      }

      .scroll-reveal,
      .js-enabled.reveal-ready .scroll-reveal,
      .js-enabled.reveal-ready .scroll-reveal:not(.is-visible) {
        opacity: 1 !important;
        transform: none !important;
        transition: none !important;
      }

      .card-header h3 {
        background: #e2e8f0 !important;
        color: #0f172a !important;
        text-shadow: none !important;
        box-shadow: none !important;
      }
    }
  </style>
</head>

<body>
  <div class="bg-orbs" aria-hidden="true">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
  </div>

  <main class="container">

    <header class="hero scroll-reveal" data-delay="0">
      <h1 class="hero-title">${title}</h1>

      <div class="hero-meta">
        <span class="meta-item">
          <i class="fas fa-book-open" aria-hidden="true"></i>
          سرفصل:
          <strong>${topicTitle}</strong>
        </span>

        ${
          topicId
            ? `
          <span class="meta-item">
            <i class="fas fa-hashtag" aria-hidden="true"></i>
            شناسه:
            <strong>${escapeHtml(topicId)}</strong>
          </span>
        `
            : ""
        }

        ${
          topic?.session_minute
            ? `
          <span class="meta-item">
            <i class="fas fa-clock" aria-hidden="true"></i>
            مدت جلسه:
            <strong>${escapeHtml(topic.session_minute)} دقیقه</strong>
          </span>
        `
            : ""
        }
      </div>
    </header>

    <section class="glass-card scroll-reveal" data-delay="100" aria-labelledby="intro-title">
      <div class="card-header">
        <span class="card-icon" aria-hidden="true">📘</span>
        <h3 id="intro-title" class="header-intro">معرفی سرفصل</h3>
      </div>

      <p>${description}</p>
    </section>

    ${
      summary
        ? `
      <section class="glass-card summary-card scroll-reveal" data-delay="180" aria-labelledby="summary-title">
        <div class="card-header">
          <span class="card-icon icon-summary" aria-hidden="true">📌</span>
          <h3 id="summary-title" class="header-summary">خلاصه محتوا</h3>
        </div>

        <p>${summary}</p>
      </section>
    `
        : ""
    }

    ${objectivesHtml}

    <section
      class="glass-card scroll-reveal is-visible always-visible"
      data-delay="0"
      aria-labelledby="content-title"
    >
      <div class="card-header">
        <span class="card-icon" aria-hidden="true">📖</span>
        <h3 id="content-title" class="header-content">محتوای آموزشی</h3>
      </div>

      <div class="content-area">
        ${bodyHtml}
      </div>
    </section>

    <footer class="footer scroll-reveal" data-delay="320">
      <a href="#" class="brand" aria-label="سامانه هوشمند آموزش و آزمون">
        <i class="fas fa-graduation-cap" aria-hidden="true"></i>
        سامانه هوشمند آموزش و آزمون
      </a>

      <p>
        تولید شده توسط
        <span>آموزش‌یار</span>
      </p>
    </footer>
  </main>

  <button class="print-btn" id="printBtn" aria-label="چاپ یا ذخیره PDF">
    <i class="fas fa-print" aria-hidden="true"></i>
    <span>چاپ / PDF</span>
  </button>

  <button class="back-to-top" id="backToTop" aria-label="بازگشت به بالا">
    <i class="fas fa-chevron-up" aria-hidden="true"></i>
  </button>

  <script>
    (function () {
      "use strict";

      var root = document.documentElement;

      var reducedMotion =
        window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      function showAllContent() {
        root.classList.remove("reveal-ready");

        document.querySelectorAll(".scroll-reveal").forEach(function (element) {
          element.classList.add("is-visible");
          element.style.opacity = "1";
          element.style.transform = "none";
        });
      }

      function prepareContentElements() {
        var selector = [
          ".html-content-wrapper > h1",
          ".html-content-wrapper > h2",
          ".html-content-wrapper > h3",
          ".html-content-wrapper > h4",
          ".html-content-wrapper > h5",
          ".html-content-wrapper > h6",
          ".html-content-wrapper > p",
          ".html-content-wrapper > ul",
          ".html-content-wrapper > ol",
          ".html-content-wrapper > blockquote",
          ".html-content-wrapper > img",
          ".html-content-wrapper > table",
          ".html-content-wrapper > pre",
          ".html-content-wrapper > iframe",
          ".html-content-wrapper > .ql-video"
        ].join(",");

        document.querySelectorAll(selector).forEach(function (element) {
          element.classList.add("scroll-reveal");
          // برای عناصر داخلی تاخیر بر اساس اندیس
          if (!element.dataset.delay) {
            var index = Array.prototype.indexOf.call(
              document.querySelectorAll(selector),
              element
            );
            element.dataset.delay = Math.min((index % 6) * 40, 200);
          }
        });
      }

      function revealElements() {
        var elements = Array.prototype.slice.call(
          document.querySelectorAll(".scroll-reveal")
        );

        if (!elements.length) {
          return;
        }

        if (reducedMotion) {
          showAllContent();
          return;
        }

        if (!("IntersectionObserver" in window)) {
          showAllContent();
          return;
        }

        try {
          root.classList.add("reveal-ready");

          var observer = new IntersectionObserver(
            function (entries) {
              entries.forEach(function (entry) {
                if (!entry.isIntersecting) {
                  return;
                }

                var element = entry.target;
                var delay = Number(element.dataset.delay || 0);

                window.setTimeout(function () {
                  element.classList.add("is-visible");
                  element.style.opacity = "";
                  element.style.transform = "";
                }, delay);

                observer.unobserve(element);
              });
            },
            {
              threshold: 0.08,
              rootMargin: "0px 0px -20px 0px",
            }
          );

          elements.forEach(function (element) {
            if (element.classList.contains("always-visible")) {
              element.classList.add("is-visible");
              return;
            }

            if (!element.dataset.delay) {
              var index = Array.prototype.indexOf.call(elements, element);
              element.dataset.delay = Math.min((index % 6) * 55, 220);
            }

            observer.observe(element);
          });

          window.setTimeout(function () {
            document.querySelectorAll(".scroll-reveal:not(.is-visible)")
              .forEach(function (element) {
                element.classList.add("is-visible");
                element.style.opacity = "";
                element.style.transform = "";
              });
          }, 2000);
        } catch (error) {
          console.warn("Scroll reveal failed; showing all content.", error);
          showAllContent();
        }
      }

      function initBackToTop() {
        var button = document.getElementById("backToTop");

        if (!button) {
          return;
        }

        function toggleButton() {
          if (window.scrollY > 420) {
            button.classList.add("visible");
          } else {
            button.classList.remove("visible");
          }
        }

        window.addEventListener("scroll", toggleButton, {
          passive: true,
        });

        toggleButton();

        button.addEventListener("click", function () {
          window.scrollTo({
            top: 0,
            behavior: reducedMotion ? "auto" : "smooth",
          });
        });
      }

      function initPrintButton() {
        var button = document.getElementById("printBtn");

        if (!button) {
          return;
        }

        button.addEventListener("click", function () {
          showAllContent();
          window.print();
        });
      }

      try {
        prepareContentElements();
        revealElements();
        initBackToTop();
        initPrintButton();
      } catch (error) {
        console.warn("Export page JavaScript failed; showing all content.", error);
        showAllContent();
      }
    })();
  </script>
</body>
</html>`;
}