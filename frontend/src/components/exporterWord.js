// exporterWord.js - بدون وابستگی اضافی
import { getExportHtml } from "./exporterHtml";
import { safeFileName } from "./exporterUtils";

// =========================================================
// تابع خروجی ورد (روش ساده و بدون وابستگی)
// =========================================================
export const exportWord = ({ topic, content, topicId }) => {
  const html = getExportHtml({ topic, content, topicId });
  const title = content?.title || topic?.title || "educational-content";

  // استخراج محتوای اصلی از HTML تولید شده
  const bodyContent = html
    .replace(/<!doctype html>.*?<body[^>]*>/is, "")
    .replace(/<\/body>.*$/is, "");

  // ساخت فایل Word با فرمت HTML (سازگار با Word)
  const fullHtml = `
    <html xmlns:o='urn:schemas-microsoft-com:office:office' 
          xmlns:w='urn:schemas-microsoft-com:office:word' 
          xmlns='http://www.w3.org/TR/REC-html40'>
    <head>
      <meta charset="UTF-8">
      <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
      <!--[if gte mso 9]>
      <xml>
        <w:WordDocument>
          <w:View>Print</w:View>
          <w:Zoom>100</w:Zoom>
        </w:WordDocument>
      </xml>
      <![endif]-->
      <style>
        body { 
          font-family: 'B Nazanin', 'Tahoma', sans-serif; 
          direction: rtl; 
          padding: 40px; 
          background: #ffffff;
          color: #1e293b;
        }
        h1 { font-size: 28pt; color: #1e3a8a; text-align: center; margin-bottom: 20px; }
        h2 { font-size: 22pt; color: #2563eb; margin-top: 25px; margin-bottom: 15px; border-right: 4px solid #2563eb; padding-right: 12px; }
        h3 { font-size: 18pt; color: #1e293b; margin-top: 20px; }
        h4 { font-size: 16pt; color: #334155; margin-top: 15px; }
        p { font-size: 14pt; line-height: 2; text-align: justify; margin-bottom: 12px; }
        ul, ol { padding-right: 30px; margin-bottom: 12px; }
        li { font-size: 14pt; line-height: 2; margin-bottom: 4px; }
        img { max-width: 100%; height: auto; margin: 10px 0; }
        strong { color: #0f172a; }
        .text-muted { color: #64748b; }
        .glass-card { 
          background: #f8fafc; 
          border: 1px solid #e2e8f0; 
          border-radius: 12px; 
          padding: 20px; 
          margin-bottom: 25px; 
        }
        .badge-container { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .badge { 
          background: #f1f5f9; 
          border: 1px solid #e2e8f0; 
          padding: 6px 14px; 
          border-radius: 20px; 
          font-size: 12pt; 
          color: #1e293b;
        }
      </style>
    </head>
    <body>
      ${bodyContent}
    </body>
    </html>
  `;

  // ایجاد Blob و دانلود
  const blob = new Blob([fullHtml], {
    type: "application/msword;charset=utf-8",
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeFileName(title)}.doc`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1500);
};

// خروجی پیش‌فرض برای سازگاری با بقیه کد
export const exportWordFile = exportWord;
export const exportWordSimple = exportWord;