import React from "react";
import {
  getBodyLines,
  isHeading,
  isBullet,
  isNumbered,
  cleanHeading,
  getBulletText,
  getNumber,
  getNumberedText,
} from "../ContentExporter";

const formatDate = (value) => {
  if (!value) return "امروز";
  const date = new Date(value);
  if (isNaN(date.getTime())) return "امروز";
  return date.toLocaleDateString("fa-IR");
};

// تابع تشخیص اینکه آیا محتوا شامل تگ‌های HTML است یا خیر
const isHtmlContent = (body) => {
  if (!body || typeof body !== "string") return false;
  // بررسی وجود تگ‌های HTML
  return /<[a-z][\s\S]*>/i.test(body);
};

const GeneratedContentDisplay = ({ content, onCopy, onPrint }) => {
  const bodyLines = getBodyLines(content);

  // =========================================================
  // رندر برای محتوای غیر HTML (متن ساده - هوش مصنوعی)
  // =========================================================
  const renderPlainBody = () => {
    if (!bodyLines.length) {
      return (
        <div className="content-empty">
          <span className="empty-icon">📄</span>
          <strong>محتوایی برای نمایش وجود ندارد</strong>
          <small>ابتدا محتوای آموزشی تولید کنید.</small>
        </div>
      );
    }

    return bodyLines.map((line, index) => {
      if (isHeading(line)) {
        return (
          <h3 className="generated-heading" key={`heading-${index}`}>
            <span className="heading-mark" />
            {cleanHeading(line)}
          </h3>
        );
      }
      if (isBullet(line)) {
        return (
          <div className="generated-list-item" key={`bullet-${index}`}>
            <span className="list-marker">•</span>
            <p>{getBulletText(line)}</p>
          </div>
        );
      }
      if (isNumbered(line)) {
        return (
          <div className="generated-list-item numbered" key={`number-${index}`}>
            <span className="list-marker">{getNumber(line)}</span>
            <p>{getNumberedText(line)}</p>
          </div>
        );
      }
      return (
        <p className="generated-paragraph" key={`paragraph-${index}`}>
          {line}
        </p>
      );
    });
  };

  // =========================================================
  // رندر برای محتوای HTML (دستی از ویرایشگر)
  // =========================================================
  const renderHtmlBody = () => {
    if (!content.body || typeof content.body !== "string" || !content.body.trim()) {
      return (
        <div className="content-empty">
          <span className="empty-icon">📄</span>
          <strong>محتوایی برای نمایش وجود ندارد</strong>
          <small>ابتدا محتوای آموزشی تولید کنید.</small>
        </div>
      );
    }

    return (
      <div
        className="html-content-body"
        dangerouslySetInnerHTML={{ __html: content.body }}
        dir="rtl"
      />
    );
  };

  // تشخیص نوع محتوا (HTML یا متن ساده)
  const isHtml = isHtmlContent(content.body);

  return (
    <>
      <header className="generated-content-header">
        <div>
          <span className="content-label">محتوای انتخاب‌شده</span>
          <h2>{content.title || "محتوای آموزشی تولیدشده"}</h2>
          <div className="content-details">
            <span>🗓 {formatDate(content.created_at)}</span>
            <span>📌 {content.source || "هوش مصنوعی"}</span>
          </div>
        </div>
        <div className="content-actions">
          <button type="button" className="icon-action" onClick={onCopy} title="کپی محتوا">
            📋
          </button>
          <button type="button" className="icon-action" onClick={onPrint} title="چاپ محتوا">
            🖨
          </button>
        </div>
      </header>

      {content.summary && (
        <div className="content-summary-box">
          <strong>خلاصه محتوا</strong>
          <p>{content.summary}</p>
        </div>
      )}

      {Array.isArray(content.learning_objectives) && content.learning_objectives.length > 0 && (
        <div className="content-objectives-box">
          <strong>اهداف یادگیری</strong>
          <ul>
            {content.learning_objectives.map((objective, index) => (
              <li key={index}>{objective}</li>
            ))}
          </ul>
        </div>
      )}

      <article className="generated-content-body">
        {isHtml ? renderHtmlBody() : renderPlainBody()}
      </article>
    </>
  );
};

export default GeneratedContentDisplay;