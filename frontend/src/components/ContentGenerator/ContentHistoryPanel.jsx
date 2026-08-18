import React, { useState, useRef, useCallback } from "react";
import ReactQuill from "react-quill";
import "react-quill/dist/quill.snow.css";
import api from "../../api"; // مسیر صحیح به api.js
import { getApiError } from "../../api"; // یا از فایل api خودتان

// استایل‌های سفارشی برای هماهنگی با تم نئونی
import "./ContentGenerationPanel.css"; // (اختیاری)

const ContentGenerationPanel = ({
  generationMode,
  setGenerationMode,
  provider,
  setProvider,
  model,
  setModel,
  level,
  setLevel,
  contentType,
  setContentType,
  customText,
  setCustomText,
  manualContent,
  setManualContent,
  generating,
  generateContent,
  loadingContents,
  safeTopicId,
}) => {
  const [uploadingImage, setUploadingImage] = useState(false);
  const quillRef = useRef(null);

  // =========================================================
  // ۱. هندلر آپلود عکس (ارسال به سرور و درج در ویرایشگر)
  // =========================================================
  const handleImageUpload = useCallback(async () => {
    const input = document.createElement("input");
    input.setAttribute("type", "file");
    input.setAttribute("accept", "image/*");
    input.click();

    input.onchange = async () => {
      const file = input.files[0];
      if (!file) return;

      // بررسی حجم (حداکثر ۵ مگابایت)
      if (file.size > 5 * 1024 * 1024) {
        alert("حجم عکس نباید بیشتر از ۵ مگابایت باشد.");
        return;
      }

      const formData = new FormData();
      formData.append("image", file);

      try {
        setUploadingImage(true);
        const response = await api.post("/upload/image", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const imageUrl = response.data?.url || response.data?.imageUrl;
        if (!imageUrl) throw new Error("آدرس عکس دریافت نشد.");

        // درج عکس در ویرایشگر
        const quill = quillRef.current?.getEditor();
        if (quill) {
          const range = quill.getSelection(true);
          quill.insertEmbed(range.index, "image", imageUrl);
          quill.setSelection(range.index + 1);
        }
      } catch (error) {
        alert("خطا در آپلود عکس: " + getApiError(error));
      } finally {
        setUploadingImage(false);
      }
    };
  }, []);

  // =========================================================
  // ۲. ماژول‌های تولبار (با دکمه آپلود سفارشی)
  // =========================================================
  const modules = useMemo(
    () => ({
      toolbar: {
        container: [
          [{ header: [1, 2, 3, false] }],
          ["bold", "italic", "underline", "strike"],
          [{ list: "ordered" }, { list: "bullet" }],
          [{ align: [] }],
          ["link", "image", "video"],
          ["blockquote", "code-block"],
          ["clean"],
        ],
        handlers: {
          image: handleImageUpload, // جایگزین handler پیش‌فرض
        },
      },
    }),
    [handleImageUpload]
  );

  // =========================================================
  // ۳. تغییر محتوای ویرایشگر
  // =========================================================
  const handleEditorChange = (value) => {
    setManualContent(value); // ذخیره HTML در state والد
  };

  // =========================================================
  // ۴. رندر
  // =========================================================
  return (
    <section className="content-generation-panel">
      {/* بخش انتخاب‌های تولید (همانند قبل) */}
      <div className="generation-controls">
        {/* ... کدهای قبلی برای انتخاب provider, model, level, contentType و ... */}
        {/* برای اختصار حذف شده، اما می‌توانید همان‌ها را از کامپوننت قبلی کپی کنید */}
      </div>

      {/* ویرایشگر متن غنی */}
      <div className="manual-editor-wrapper">
        <label className="editor-label">
          <span className="label-icon">✏️</span>
          محتوای دستی (می‌توانید متن، عکس، جدول و ... وارد کنید)
        </label>
        <ReactQuill
          ref={quillRef}
          value={manualContent || ""}
          onChange={handleEditorChange}
          modules={modules}
          theme="snow"
          placeholder="متن، عکس، جدول یا هر محتوای دیگری را اینجا وارد کنید..."
          className="custom-quill-editor"
          style={{ minHeight: "300px", marginBottom: "50px" }}
        />
        {uploadingImage && (
          <div className="upload-status">در حال آپلود عکس...</div>
        )}
      </div>

      {/* دکمه تولید محتوا (همانند قبل) */}
      <button
        className="btn-generate"
        onClick={generateContent}
        disabled={generating || loadingContents}
      >
        {generating ? "در حال تولید..." : "🚀 تولید محتوای هوشمند"}
      </button>
    </section>
  );
};

export default ContentGenerationPanel;