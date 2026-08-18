// =========================================================
// توابع پایه و مشترک برای تمام خروجی‌ها
// =========================================================

export const DEFAULT_TITLE = "محتوای آموزشی";

export const normalizeBody = (value) => {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    return value
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .trim();
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        if (
          item &&
          typeof item === "object" &&
          item.text !== undefined
        ) {
          return String(item.text);
        }

        return JSON.stringify(item);
      })
      .join("\n")
      .trim();
  }

  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => {
        if (
          typeof item === "string" ||
          typeof item === "number"
        ) {
          return `${key}: ${item}`;
        }

        return `${key}: ${JSON.stringify(item)}`;
      })
      .join("\n")
      .trim();
  }

  return String(value).trim();
};

export const getContentBody = (content) => {
  return normalizeBody(content?.body);
};

// تشخیص محتوای HTML
export const isHtmlContent = (body) => {
  if (!body || typeof body !== "string") return false;
  return /<[a-z][\s\S]*>/i.test(body);
};

// استخراج خطوط از HTML (برای پاورپوینت و موارد مشابه)
export const htmlToLines = (html) => {
  if (!html || typeof html !== "string") return [];

  // ایجاد یک عنصر موقت برای پردازش
  const wrapper = document.createElement("div");
  wrapper.innerHTML = html;

  const lines = [];

  // پردازش عناصر تیتر
  const headings = wrapper.querySelectorAll("h1, h2, h3, h4, h5, h6");
  headings.forEach((el) => {
    const text = el.textContent.trim();
    if (text) {
      lines.push(`# ${text}`);
    }
  });

  // پردازش پاراگراف‌ها و لیست‌ها
  const elements = wrapper.querySelectorAll("p, li, div:not(:has(*))");
  elements.forEach((el) => {
    if (!el.closest("h1, h2, h3, h4, h5, h6")) {
      const text = el.textContent.trim();
      if (text) {
        if (el.tagName === "LI") {
          const parent = el.closest("ul, ol");
          if (parent) {
            if (parent.tagName === "UL") {
              lines.push(`- ${text}`);
            } else if (parent.tagName === "OL") {
              const index = Array.from(parent.children).indexOf(el) + 1;
              lines.push(`${index}. ${text}`);
            }
          } else {
            lines.push(`- ${text}`);
          }
        } else {
          lines.push(text);
        }
      }
    }
  });

  if (lines.length === 0) {
    const text = wrapper.textContent.trim();
    if (text) {
      lines.push(text);
    }
  }

  return lines;
};

export const getBodyLines = (content) => {
  const body = getContentBody(content);

  if (isHtmlContent(body)) {
    return htmlToLines(body);
  }

  return body
    ? body
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
    : [];
};

// =========================================================
// توابع تشخیص و پردازش خطوط
// =========================================================
export const isHeading = (line) => {
  const value = String(line || "").trim();

  return (
    /^#{1,6}\s+/.test(value) ||
    /^(فصل|بخش|درس)\s+/i.test(value) ||
    /^(مقدمه|اهداف یادگیری|توضیح درس|مثال عملی|تمرین|نکات کلیدی|جمع‌بندی|جمع بندی|نتیجه‌گیری|نتیجه گیری)\s*:?\s*$/i.test(
      value
    ) ||
    /^.{1,30}[:：]\s*$/.test(value) ||
    /^\d+\.\s+\S+/.test(value)
  );
};

export const cleanHeading = (line) => {
  return String(line || "")
    .replace(/^#{1,6}\s+/, "")
    .replace(/^[-*•]\s+/, "")
    .replace(/[:：]\s*$/, "")
    .trim();
};

export const isBullet = (line) => {
  return /^[-*•]\s+/.test(String(line || ""));
};

export const isNumbered = (line) => {
  return /^\d+[\-.)]\s+/.test(String(line || ""));
};

export const getBulletText = (line) => {
  return String(line)
    .replace(/^[-*•]\s+/, "")
    .trim();
};

export const getNumberedText = (line) => {
  return String(line)
    .replace(/^\d+[\-.)]\s+/, "")
    .trim();
};

export const getNumber = (line) => {
  return String(line).match(/^\d+/)?.[0] || "";
};

export const escapeHtml = (value) => {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
};

export const safeFileName = (value) => {
  const result = String(value || DEFAULT_TITLE)
    .replace(/[\\/:*?"<>|]/g, "-")
    .replace(/\s+/g, " ")
    .trim();

  return result || DEFAULT_TITLE;
};

export const downloadFile = (content, fileName, mimeType) => {
  const blob = new Blob([content], {
    type: `${mimeType};charset=utf-8`,
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = fileName;
  link.rel = "noopener";
  link.style.display = "none";

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 1500);
};

// =========================================================
// ساختار بخش‌ها (برای پاورپوینت)
// =========================================================
export const buildSections = (content) => {
  const sections = [];
  let current = null;

  const ensureSection = () => {
    if (!current) {
      current = {
        title: "محتوای آموزشی",
        items: [],
      };
      sections.push(current);
    }
    return current;
  };

  const lines = getBodyLines(content);

  lines.forEach((line) => {
    if (isHeading(line)) {
      current = {
        title: cleanHeading(line),
        items: [],
      };
      sections.push(current);
      return;
    }

    const section = ensureSection();

    if (isBullet(line)) {
      section.items.push({
        text: getBulletText(line),
        type: "bullet",
      });
    } else if (isNumbered(line)) {
      section.items.push({
        text: getNumberedText(line),
        type: "number",
        number: getNumber(line),
      });
    } else {
      section.items.push({
        text: line,
        type: "paragraph",
      });
    }
  });

  return sections;
};