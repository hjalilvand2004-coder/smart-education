import React, { useState, useRef, useCallback, useMemo, useEffect } from "react";
import ReactQuill from "react-quill";
import "react-quill/dist/quill.snow.css";
import api from "../../api";
import { getApiError } from "../../api";

// =========================================================
// ۱. ثبت Blot سفارشی برای تصویر با پشتیبانی از width (فقط یک بار)
// =========================================================
let blotRegistered = false;

const registerResizableImageBlot = () => {
  if (blotRegistered) return;

  try {
    const Quill = ReactQuill.Quill;
    const BaseImage = Quill.import("formats/image");

    class ResizableImage extends BaseImage {
      static formats(domNode) {
        const formats = super.formats(domNode);
        const width = domNode.style.width || domNode.getAttribute("width");
        if (width) {
          formats.width = width;
        }
        return formats;
      }

      format(name, value) {
        if (name === "width") {
          if (value) {
            this.domNode.style.width = value;
            this.domNode.style.height = "auto";
          } else {
            this.domNode.style.removeProperty("width");
            this.domNode.style.removeProperty("height");
          }
          return;
        }
        super.format(name, value);
      }
    }

    ResizableImage.blotName = "image";
    ResizableImage.tagName = "IMG";
    Quill.register(ResizableImage, true);
    blotRegistered = true;
    console.log("✅ Blot سفارشی ResizableImage ثبت شد.");
  } catch (error) {
    console.warn("⚠️ خطا در ثبت Blot سفارشی:", error);
  }
};

// =========================================================
// کامپوننت اصلی
// =========================================================
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

  // ثبت Blot در اولین رندر
  useEffect(() => {
    registerResizableImageBlot();
  }, []);

  // =========================================================
  // ۲. هندلر آپلود عکس
  // =========================================================
  const handleImageUpload = useCallback(() => {
    const input = document.createElement("input");
    input.setAttribute("type", "file");
    input.setAttribute("accept", "image/*");
    input.click();

    input.onchange = async () => {
      const file = input.files[0];
      if (!file) return;

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

        let imageUrl = response.data?.url || response.data?.imageUrl;
        if (!imageUrl) throw new Error("آدرس عکس دریافت نشد.");

        const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
        const fullUrl = imageUrl.startsWith("http") ? imageUrl : `${baseUrl}${imageUrl}`;

        const quill = quillRef.current?.getEditor();
        if (quill) {
          const range = quill.getSelection(true);
          quill.insertEmbed(range.index, "image", fullUrl);
          quill.setSelection(range.index + 1);
        }
      } catch (error) {
        console.error("خطا در آپلود عکس:", error);
        alert("خطا در آپلود عکس: " + (getApiError(error) || "لطفاً مجدداً تلاش کنید."));
      } finally {
        setUploadingImage(false);
      }
    };
  }, []);

  // =========================================================
  // ۳. تغییر سایز تصویر با کلیک (اصلاح شده با وابستگی generationMode)
  // =========================================================
  useEffect(() => {
    // فقط در حالت‌های manual یا hybrid اجرا شود
    if (generationMode !== "manual" && generationMode !== "hybrid") {
      return;
    }

    const quill = quillRef.current?.getEditor();
    if (!quill) {
      console.warn("⚠️ Quill editor در دسترس نیست. ممکن است هنوز رندر نشده باشد.");
      return;
    }

    const editorContainer = quill.root;

    const handleImageClick = (e) => {
      const target = e.target;
      if (!(target instanceof HTMLImageElement)) return;
      if (!editorContainer.contains(target)) return;

      e.preventDefault();
      e.stopPropagation();

      // پیدا کردن Blot تصویر
      const Quill = ReactQuill.Quill;
      const blot = Quill.find(target);
      if (!blot) {
        console.warn("⚠️ Blot تصویر یافت نشد.");
        return;
      }

      // استخراج عرض فعلی
      const widthFromStyle = target.style.width;
      const widthFromAttribute = target.getAttribute("width");
      const currentWidth =
        widthFromStyle ||
        widthFromAttribute ||
        target.clientWidth ||
        target.naturalWidth ||
        300;

      const currentWidthNumber = parseInt(String(currentWidth), 10) || 300;

      // نمایش prompt برای دریافت عرض جدید
      const newWidth = window.prompt(
        "عرض تصویر را به پیکسل وارد کنید:",
        String(currentWidthNumber)
      );

      if (newWidth === null) return; // کاربر Cancel زده

      const numericWidth = Number(newWidth);
      if (!Number.isFinite(numericWidth) || numericWidth <= 0) {
        alert("لطفاً یک عرض معتبر و بزرگ‌تر از صفر وارد کنید.");
        return;
      }

      const widthValue = `${numericWidth}px`;

      // اعمال تغییر از طریق Blot (ثبت در Delta)
      const index = quill.getIndex(blot);
      quill.formatText(index, 1, "width", widthValue, "user");

      // اعمال تغییر در DOM برای نمایش فوری
      target.style.width = widthValue;
      target.style.height = "auto";
    };

    // اتصال listener به container ویرایشگر
    editorContainer.addEventListener("click", handleImageClick);
    console.log("✅ Listener تغییر سایز تصویر متصل شد.");

    // تابع کمکی برای تست در کنسول
    window.__testImage = () => {
      const img = editorContainer.querySelector("img");
      if (img) {
        const Quill = ReactQuill.Quill;
        const blot = Quill.find(img);
        console.log("✅ تصویر پیدا شد:", img);
        console.log("عرض فعلی (style):", img.style.width);
        console.log("عرض فعلی (blot):", blot?.formats()?.width);
        console.log("نکته: برای تغییر اندازه روی تصویر کلیک کنید.");
      } else {
        console.log("❌ هیچ تصویری در ویرایشگر پیدا نشد.");
      }
    };
    console.log("💡 برای تست، در کنسول تایپ کنید: __testImage()");

    return () => {
      editorContainer.removeEventListener("click", handleImageClick);
      delete window.__testImage;
      console.log("✅ Listener تغییر سایز تصویر جدا شد.");
    };
  }, [generationMode]); // ← این وابستگی کلیدی است

  // =========================================================
  // ۴. تنظیمات تولبار
  // =========================================================
  const modules = useMemo(() => {
    return {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, 4, 5, 6, false] }],
          [{ font: [] }],
          [{ size: ["small", false, "large", "huge"] }],
          ["bold", "italic", "underline", "strike"],
          [{ color: [] }, { background: [] }],
          [{ script: "sub" }, { script: "super" }],
          [{ list: "ordered" }, { list: "bullet" }],
          [{ indent: "-1" }, { indent: "+1" }],
          [{ align: [] }],
          ["link", "image", "video"],
          ["blockquote", "code-block"],
          ["clean"],
        ],
        handlers: {
          image: handleImageUpload,
        },
      },
      clipboard: {
        matchVisual: false,
      },
    };
  }, [handleImageUpload]);

  // =========================================================
  // ۵. تغییر محتوای ویرایشگر
  // =========================================================
  const handleEditorChange = (value) => {
    setManualContent(value);
  };

  // =========================================================
  // ۶. رندر
  // =========================================================
  return (
    <div className="generation-panel">
      <div className="generation-panel-header">
        <div>
          <h3>تولید محتوای جدید</h3>
          <p>روش تولید محتوا را انتخاب کنید.</p>
        </div>
        <div className="generation-icon">⚡</div>
      </div>

      <div className="generation-mode-selector">
        <button
          type="button"
          className={`mode-btn ${generationMode === "ai" ? "active" : ""}`}
          onClick={() => setGenerationMode("ai")}
        >
          🤖 هوش مصنوعی
        </button>
        <button
          type="button"
          className={`mode-btn ${generationMode === "manual" ? "active" : ""}`}
          onClick={() => setGenerationMode("manual")}
        >
          📝 بارگذاری دستی
        </button>
        <button
          type="button"
          className={`mode-btn ${generationMode === "hybrid" ? "active" : ""}`}
          onClick={() => setGenerationMode("hybrid")}
        >
          🔄 ترکیبی
        </button>
      </div>

      {(generationMode === "ai" || generationMode === "hybrid") && (
        <div className="ai-options-grid">
          <div>
            <label htmlFor="ai-provider">سرویس هوش مصنوعی</label>
            <select
              id="ai-provider"
              className="content-input"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={generating}
            >
              <option value="openai_compatible">OpenAI Compatible</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama محلی</option>
            </select>
          </div>
          <div>
            <label htmlFor="ai-model">مدل هوش مصنوعی</label>
            <input
              id="ai-model"
              className="content-input"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="مدل تنظیم‌شده در Backend"
              disabled={generating}
            />
          </div>
          <div>
            <label htmlFor="content-level">سطح محتوا</label>
            <select
              id="content-level"
              className="content-input"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              disabled={generating}
            >
              <option value="beginner">مقدماتی</option>
              <option value="intermediate">متوسط</option>
              <option value="advanced">پیشرفته</option>
            </select>
          </div>
          <div>
            <label htmlFor="content-type">نوع محتوا</label>
            <select
              id="content-type"
              className="content-input"
              value={contentType}
              onChange={(e) => setContentType(e.target.value)}
              disabled={generating}
            >
              <option value="lesson">درس آموزشی</option>
              <option value="summary">خلاصه آموزشی</option>
              <option value="article">مقاله آموزشی</option>
              <option value="handout">جزوه دانشگاهی</option>
              <option value="presentation">محتوای ارائه</option>
            </select>
          </div>
        </div>
      )}

      {(generationMode === "manual" || generationMode === "hybrid") && (
        <div className="manual-content-section">
          <label htmlFor="manual-content">
            {generationMode === "manual"
              ? "محتوای خود را وارد کنید (با قابلیت قالب‌بندی، عکس، رنگ و جدول)"
              : "محتوای اولیه خود را وارد کنید (توسط AI بهبود می‌یابد)"}
          </label>

          <div className="quill-wrapper">
            <ReactQuill
              ref={quillRef}
              value={manualContent || ""}
              onChange={handleEditorChange}
              modules={modules}
              theme="snow"
              placeholder="متن، عکس، جدول، رنگ‌بندی یا هر محتوای دیگری را اینجا وارد کنید..."
              className="custom-quill-editor"
              style={{ minHeight: "350px", marginBottom: "10px" }}
            />
            {uploadingImage && (
              <div className="upload-status">⏳ در حال آپلود عکس...</div>
            )}
          </div>

          <div className="editor-hint" style={{ marginTop: "10px", color: "#64748b", fontSize: "0.9rem" }}>
            <small>
              💡 برای تغییر اندازه تصویر، روی تصویر کلیک کنید و عرض جدید را وارد کنید.
            </small>
          </div>
        </div>
      )}

      {generationMode === "ai" && (
        <>
          <label htmlFor="custom-content">توضیحات اختصاصی استاد (اختیاری)</label>
          <textarea
            id="custom-content"
            className="content-input"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="مثلاً محتوا شامل تعریف، مثال، کاربرد، نکات مهم و جمع‌بندی باشد."
            disabled={generating}
          />
        </>
      )}

      <div className="generation-actions">
        <button
          type="button"
          className="primary-action"
          onClick={generateContent}
          disabled={generating || loadingContents || !safeTopicId}
        >
          {generating
            ? "در حال تولید محتوا..."
            : generationMode === "manual"
            ? "📤 ذخیره محتوای دستی"
            : generationMode === "hybrid"
            ? "🔄 بهبود محتوا با AI"
            : "✨ تولید محتوای آموزشی"}
        </button>

        {(customText || manualContent) && !generating && (
          <button
            type="button"
            className="light-action"
            onClick={() => {
              setCustomText("");
              setManualContent("");
            }}
          >
            پاک‌کردن متن
          </button>
        )}
      </div>
    </div>
  );
};

export default ContentGenerationPanel;