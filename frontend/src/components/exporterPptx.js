import pptxgen from "pptxgenjs";
import {
  DEFAULT_TITLE,
  safeFileName,
  buildSections,
  getBodyLines,
} from "./exporterUtils";

// =========================================================
// پالت رنگ‌های شاد و زنده
// =========================================================
const COLOR_PALETTE = [
  "FF6B6B", // قرمز
  "4ECDC4", // فیروزه‌ای
  "FFE66D", // زرد
  "A8E6CF", // سبز ملایم
  "FF8A5C", // نارنجی
  "6C5CE7", // بنفش
  "74B9FF", // آبی روشن
  "FD79A8", // صورتی
  "00B894", // سبز زمردی
  "FDCB6E", // طلایی
];

// =========================================================
// استخراج URL تصاویر از HTML
// =========================================================
function extractImagesFromHtml(html) {
  if (!html || typeof html !== "string") return [];
  const imgRegex = /<img[^>]+src=["']([^"']+)["']/gi;
  const images = [];
  let match;
  while ((match = imgRegex.exec(html)) !== null) {
    const url = match[1];
    if (url && (url.startsWith('http') || url.startsWith('data:') || url.startsWith('/'))) {
      images.push(url);
    }
  }
  return images;
}

// =========================================================
// تبدیل URL مطلق به مسیر نسبی (برای پروکسی Vite)
// =========================================================
function normalizeImageUrl(url) {
  if (!url) return url;
  // حذف پروتکل و دامنه برای تبدیل به مسیر نسبی
  const relative = url.replace(/^https?:\/\/[^\/]+/, '');
  // اگر با اسلش شروع می‌شود، همان را برمی‌گردانیم
  if (relative.startsWith('/')) return relative;
  // اگر تصویر از نوع داده باشد، تغییری نمی‌دهیم
  if (url.startsWith('data:')) return url;
  // در غیر این صورت همان url را برمی‌گردانیم
  return url;
}

// =========================================================
// توابع کمکی پاورپوینت
// =========================================================
const addPptText = (slide, text, options = {}) => {
  slide.addText(String(text || ""), {
    fontFace: "Tahoma",
    rtlMode: true,
    margin: 0.06,
    fit: "shrink",
    valign: "mid",
    breakLine: false,
    ...options,
  });
};

/**
 * هدر اسلاید با پس‌زمینه رنگی
 */
const addPptHeader = (pptx, slide, title, page, sectionIndex = 0, totalSections = 1) => {
  slide.background = { color: "FFFFFF" };

  // نوار آبی بالایی
  slide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0,
    w: 13.333,
    h: 0.2,
    line: { transparency: 100 },
    fill: { color: "2563EB" },
  });

  const colorIndex = sectionIndex % COLOR_PALETTE.length;
  const headerColor = COLOR_PALETTE[colorIndex];

  // مستطیل رنگی برای تیتر
  slide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0.2,
    w: 13.333,
    h: 0.85,
    line: { transparency: 100 },
    fill: { color: headerColor },
    shadow: {
      type: "outer",
      color: "000000",
      blur: 2,
      offset: 1,
      angle: 45,
      opacity: 0.15,
    },
  });

  addPptText(slide, title, {
    x: 0.7,
    y: 0.3,
    w: 11.9,
    h: 0.65,
    color: "FFFFFF",
    fontSize: 26,
    bold: true,
    align: "right",
    shadow: {
      type: "outer",
      color: "000000",
      blur: 1,
      offset: 1,
      angle: 45,
      opacity: 0.2,
    },
  });

  addPptText(slide, `سامانه هوشمند آموزش و آزمون | صفحه ${page}`, {
    x: 0.7,
    y: 7.05,
    w: 11.9,
    h: 0.2,
    color: "94A3B8",
    fontSize: 9,
    align: "center",
  });
};

// =========================================================
// تابع اصلی خروجی پاورپوینت
// =========================================================
export const exportPowerPointFile = async ({ topic, content, topicId }) => {
  const pptx = new pptxgen();

  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "سامانه هوشمند آموزش";
  pptx.company = "سامانه هوشمند آموزش";
  pptx.subject = topic?.title || DEFAULT_TITLE;
  pptx.title = content?.title || topic?.title || DEFAULT_TITLE;
  pptx.lang = "fa-IR";

  pptx.theme = {
    headFontFace: "Tahoma",
    bodyFontFace: "Tahoma",
    lang: "fa-IR",
  };

  const title = content?.title || topic?.title || DEFAULT_TITLE;
  const topicTitle = topic?.title || "بدون عنوان";
  const description =
    topic?.description || "محتوای آموزشی تولیدشده توسط سامانه هوشمند آموزش";

  let page = 1;

  // =========================================================
  // اسلاید عنوان (جلد)
  // =========================================================
  {
    const slide = pptx.addSlide();
    slide.background = { fill: "123B72" };

    slide.addShape(pptx.ShapeType.rect, {
      x: 0,
      y: 6.85,
      w: 13.333,
      h: 0.65,
      line: { transparency: 100 },
      fill: { color: "60A5FA" },
    });

    addPptText(slide, "✨ محتوای آموزشی هوشمند ✨", {
      x: 0.8,
      y: 1.1,
      w: 11.7,
      h: 0.5,
      color: "FFE66D",
      fontSize: 20,
      bold: true,
      align: "right",
    });

    addPptText(slide, title, {
      x: 0.8,
      y: 2.1,
      w: 11.7,
      h: 1.35,
      color: "FFFFFF",
      fontSize: 34,
      bold: true,
      align: "right",
      shadow: {
        type: "outer",
        color: "000000",
        blur: 2,
        offset: 2,
        angle: 45,
        opacity: 0.3,
      },
    });

    addPptText(slide, `📚 سرفصل: ${topicTitle}`, {
      x: 0.8,
      y: 3.8,
      w: 11.7,
      h: 0.55,
      color: "DBEAFE",
      fontSize: 18,
      align: "right",
    });

    addPptText(slide, "تولیدشده توسط سامانه هوشمند آموزش و آزمون", {
      x: 0.8,
      y: 6.98,
      w: 11.7,
      h: 0.25,
      color: "FFFFFF",
      fontSize: 10,
      align: "center",
    });

    slide.transition = { type: "fade", duration: 0.7 };
  }

  // =========================================================
  // اسلاید معرفی سرفصل
  // =========================================================
  {
    page += 1;
    const slide = pptx.addSlide();
    addPptHeader(pptx, slide, "معرفی سرفصل", page, 0, 1);

    slide.addShape(pptx.ShapeType.roundRect, {
      x: 0.85,
      y: 1.65,
      w: 11.65,
      h: 3.7,
      rectRadius: 0.08,
      line: { color: "DBEAFE", width: 1.2 },
      fill: { color: "F8FBFF" },
      shadow: {
        type: "outer",
        color: "000000",
        blur: 3,
        offset: 2,
        angle: 45,
        opacity: 0.1,
      },
    });

    addPptText(slide, topicTitle, {
      x: 1.2,
      y: 2.05,
      w: 10.9,
      h: 0.65,
      color: "1E3A8A",
      fontSize: 24,
      bold: true,
      align: "right",
    });

    addPptText(slide, description, {
      x: 1.2,
      y: 2.95,
      w: 10.9,
      h: 1.35,
      color: "475569",
      fontSize: 16,
      align: "right",
      valign: "top",
    });

    addPptText(
      slide,
      `شناسه سرفصل: ${topicId || "-"} | زمان جلسه: ${
        topic?.session_minute || 0
      } دقیقه`,
      {
        x: 1.2,
        y: 4.7,
        w: 10.9,
        h: 0.35,
        color: "64748B",
        fontSize: 11,
        align: "right",
      }
    );

    slide.transition = { type: "fade", duration: 0.7 };
  }

  // =========================================================
  // اهداف یادگیری (حداکثر ۸ عدد، هر کدام در یک خط)
  // =========================================================
  const objectives = Array.isArray(content?.learning_objectives)
    ? content.learning_objectives.filter(Boolean).slice(0, 8)
    : [];

  if (objectives.length > 0) {
    page += 1;
    const slide = pptx.addSlide();
    addPptHeader(pptx, slide, "اهداف یادگیری", page, 1, 2);

    // حداکثر ۶ هدف در هر اسلاید (اگر بیشتر بود، اسلاید بعدی)
    const chunkSizeObj = 6;
    for (let i = 0; i < objectives.length; i += chunkSizeObj) {
      const chunk = objectives.slice(i, i + chunkSizeObj);
      if (i > 0) {
        // اسلاید جدید برای ادامه اهداف
        page += 1;
        const slideExtra = pptx.addSlide();
        addPptHeader(pptx, slideExtra, "اهداف یادگیری (ادامه)", page, 1, 2);
        chunk.forEach((objective, idx) => {
          const y = 1.65 + idx * 0.62;
          const dotColor = COLOR_PALETTE[(i + idx) % COLOR_PALETTE.length];
          slideExtra.addShape(pptx.ShapeType.ellipse, {
            x: 0.85,
            y: y + 0.12,
            w: 0.18,
            h: 0.18,
            line: { transparency: 100 },
            fill: { color: dotColor },
          });
          addPptText(slideExtra, objective, {
            x: 1.2,
            y,
            w: 11,
            h: 0.45,
            color: "1E293B",
            fontSize: 15,
            align: "right",
          });
        });
        slideExtra.transition = { type: "fade", duration: 0.7 };
      } else {
        // اسلاید اول
        chunk.forEach((objective, idx) => {
          const y = 1.65 + idx * 0.62;
          const dotColor = COLOR_PALETTE[idx % COLOR_PALETTE.length];
          slide.addShape(pptx.ShapeType.ellipse, {
            x: 0.85,
            y: y + 0.12,
            w: 0.18,
            h: 0.18,
            line: { transparency: 100 },
            fill: { color: dotColor },
          });
          addPptText(slide, objective, {
            x: 1.2,
            y,
            w: 11,
            h: 0.45,
            color: "1E293B",
            fontSize: 15,
            align: "right",
          });
        });
        slide.transition = { type: "fade", duration: 0.7 };
      }
    }
  }

  // =========================================================
  // بدنه اصلی محتوا (متن) – با حداکثر ۴ آیتم در هر اسلاید
  // =========================================================
  const sections = buildSections(content);

  // فیلتر بخش‌هایی که آیتم معتبر دارند
  const nonEmptySections = sections.filter(
    (sec) => sec.items && sec.items.length > 0
  );

  nonEmptySections.forEach((section, sectionIdx) => {
    // حداکثر ۴ آیتم در هر اسلاید (برای جلوگیری از شلوغی)
    const chunkSize = 4;
    const chunks = [];
    for (let i = 0; i < section.items.length; i += chunkSize) {
      chunks.push(section.items.slice(i, i + chunkSize));
    }

    chunks.forEach((chunk, chunkIndex) => {
      page += 1;
      const slide = pptx.addSlide();

      const titleToShow =
        chunkIndex === 0 ? section.title : `${section.title} (ادامه)`;
      addPptHeader(
        pptx,
        slide,
        titleToShow,
        page,
        sectionIdx,
        nonEmptySections.length
      );

      const colorForSection = COLOR_PALETTE[sectionIdx % COLOR_PALETTE.length];

      // اگر ادامه است، یک خط توضیح اضافه کنیم
      if (chunkIndex > 0) {
        addPptText(slide, `ادامه مبحث ${section.title}`, {
          x: 0.7,
          y: 1.35,
          w: 11.9,
          h: 0.3,
          color: "64748B",
          fontSize: 11,
          italic: true,
          align: "right",
        });
      }

      // هر آیتم در یک ردیف با فاصله کافی
      chunk.forEach((item, index) => {
        const y = 1.65 + index * 0.82; // افزایش فاصله برای جلوگیری از تداخل

        // دایره‌های رنگی
        slide.addShape(pptx.ShapeType.ellipse, {
          x: 0.82,
          y: y + 0.1,
          w: 0.17,
          h: 0.17,
          line: { transparency: 100 },
          fill: { color: colorForSection },
          shadow: {
            type: "outer",
            color: "000000",
            blur: 1,
            offset: 1,
            angle: 45,
            opacity: 0.15,
          },
        });

        const text =
          item.type === "number" ? `${item.number}. ${item.text}` : item.text;

        // اگر متن خالی است، از این آیتم صرفنظر کنیم
        if (!text || text.trim() === "") return;

        addPptText(slide, text, {
          x: 1.15,
          y,
          w: 11.15,
          h: 0.6, // افزایش ارتفاع برای جلوگیری از برش
          color: "1E293B",
          fontSize: item.type === "paragraph" ? 14 : 15,
          align: "right",
          valign: "top",
          fit: "shrink", // کاهش اندازه در صورت نیاز
        });
      });

      slide.transition = { type: "fade", duration: 0.7 };
    });
  });

  // =========================================================
  // استخراج و افزودن تصاویر (با استفاده از پروکسی Vite)
  // =========================================================
  const htmlContent = content?.body || content?.html || "";
  let imageUrls = extractImagesFromHtml(htmlContent);

  // نرمال‌سازی URLها برای پروکسی
  imageUrls = imageUrls.map(normalizeImageUrl);
  // حذف تکراری‌ها
  imageUrls = [...new Set(imageUrls)];

  if (imageUrls.length > 0) {
    // اسلاید عنوان تصاویر
    page += 1;
    const slideTitle = pptx.addSlide();
    addPptHeader(pptx, slideTitle, "تصاویر مرتبط", page, 0, 1);
    addPptText(slideTitle, "تصاویر موجود در محتوای آموزشی", {
      x: 1.2,
      y: 2.0,
      w: 10.9,
      h: 1.0,
      color: "475569",
      fontSize: 20,
      align: "center",
      valign: "mid",
    });
    slideTitle.transition = { type: "fade", duration: 0.7 };

    // برای هر تصویر یک اسلاید
    for (let i = 0; i < imageUrls.length; i++) {
      const url = imageUrls[i];
      page += 1;
      const slide = pptx.addSlide();
      addPptHeader(pptx, slide, `تصویر ${i + 1}`, page, 0, 1);

      try {
        // تلاش برای بارگذاری تصویر (با مسیر پروکسی یا مستقیم)
        slide.addImage({
          path: url,
          x: 1.5,
          y: 1.5,
          w: 10.33,
          h: 5.0,
          sizing: { type: "contain", w: 10.33, h: 5.0 },
        });
      } catch (error) {
        console.warn(`خطا در بارگذاری تصویر ${url}:`, error);
        // در صورت خطا، یک پیام نمایش می‌دهیم
        addPptText(slide, "بارگذاری تصویر ممکن نیست", {
          x: 1.5,
          y: 3.0,
          w: 10.33,
          h: 1.0,
          color: "EF4444",
          fontSize: 18,
          align: "center",
          valign: "mid",
        });
      }

      slide.transition = { type: "fade", duration: 0.7 };
    }
  }

  // =========================================================
  // اسلاید جمع‌بندی
  // =========================================================
  {
    page += 1;
    const slide = pptx.addSlide();

    slide.background = { fill: "EFF6FF" };

    slide.addShape(pptx.ShapeType.rect, {
      x: 0,
      y: 0,
      w: 13.333,
      h: 0.35,
      line: { transparency: 100 },
      fill: { color: "2563EB" },
    });

    addPptText(slide, "📌 جمع‌بندی", {
      x: 0.8,
      y: 0.7,
      w: 11.7,
      h: 0.7,
      color: "1E3A8A",
      fontSize: 32,
      bold: true,
      align: "center",
    });

    addPptText(
      slide,
      content?.summary ||
        `این ارائه بر اساس محتوای آموزشی سرفصل «${topicTitle}» تهیه شده است.`,
      {
        x: 1.2,
        y: 2.0,
        w: 10.9,
        h: 1.8,
        color: "334155",
        fontSize: 20,
        align: "center",
        valign: "mid",
        shadow: {
          type: "outer",
          color: "000000",
          blur: 2,
          offset: 1,
          angle: 45,
          opacity: 0.05,
        },
      }
    );

    addPptText(slide, "📖 مطالعه محتوای کامل و شرکت در آزمون پیشنهاد می‌شود.", {
      x: 1.2,
      y: 4.2,
      w: 10.9,
      h: 0.6,
      color: "64748B",
      fontSize: 16,
      align: "center",
    });

    addPptText(slide, "سامانه هوشمند آموزش و آزمون", {
      x: 1,
      y: 6.75,
      w: 11.3,
      h: 0.3,
      color: "2563EB",
      fontSize: 12,
      align: "center",
    });

    slide.transition = { type: "fade", duration: 0.7 };
  }

  // =========================================================
  // ذخیره فایل
  // =========================================================
  await pptx.writeFile({
    fileName: `${safeFileName(title)}.pptx`,
  });
};