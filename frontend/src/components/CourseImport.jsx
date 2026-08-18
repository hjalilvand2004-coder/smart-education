import {
  useRef,
  useState,
} from "react";

import api, { getApiError } from "../api";
import "./CourseImport.css";


const ACCEPTED_EXTENSIONS = [
  ".xlsx",
  ".csv",
  ".tsv",
  ".txt",
];

const MAX_FILE_SIZE = 10 * 1024 * 1024;


function CourseImport({
  courseId,
  onSuccess,
}) {
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] =
    useState(false);

  const [result, setResult] = useState(null);


  /*
    آماده‌سازی و اعتبارسنجی شناسه درس
  */
  const normalizedCourseId = String(
    courseId ?? ""
  ).trim();

  const numericCourseId = Number(
    normalizedCourseId
  );

  const hasValidCourseId =
    normalizedCourseId !== "" &&
    Number.isInteger(numericCourseId) &&
    numericCourseId > 0;


  const getFileExtension = (
    fileName = ""
  ) => {
    const lastDotIndex =
      fileName.lastIndexOf(".");

    if (lastDotIndex === -1) {
      return "";
    }

    return fileName
      .substring(lastDotIndex)
      .toLowerCase();
  };


  const formatFileSize = (bytes = 0) => {
    if (!bytes) {
      return "0 بایت";
    }

    const units = [
      "بایت",
      "کیلوبایت",
      "مگابایت",
      "گیگابایت",
    ];

    const unitIndex = Math.min(
      Math.floor(
        Math.log(bytes) / Math.log(1024)
      ),
      units.length - 1
    );

    const size =
      bytes / Math.pow(1024, unitIndex);

    return `${size.toFixed(
      unitIndex === 0 ? 0 : 2
    )} ${units[unitIndex]}`;
  };


  const validateFile = (selectedFile) => {
    if (!selectedFile) {
      return "فایلی انتخاب نشده است.";
    }

    const extension = getFileExtension(
      selectedFile.name
    );

    if (
      !ACCEPTED_EXTENSIONS.includes(extension)
    ) {
      return (
        "فرمت فایل قابل قبول نیست. فقط فایل‌های " +
        "XLSX، CSV، TSV و TXT قابل بارگذاری هستند."
      );
    }

    if (selectedFile.size === 0) {
      return "فایل انتخاب‌شده خالی است.";
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      return (
        "حجم فایل نباید بیشتر از ۱۰ مگابایت باشد."
      );
    }

    return "";
  };


  const clearMessages = () => {
    setMessage("");
    setError("");
  };


  const clearFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };


  const selectFile = (selectedFile) => {
    clearMessages();
    setResult(null);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    const validationError =
      validateFile(selectedFile);

    if (validationError) {
      setFile(null);
      setError(validationError);
      clearFileInput();
      return;
    }

    setFile(selectedFile);
  };


  const handleFileChange = (event) => {
    const selectedFile =
      event.target.files?.[0] || null;

    selectFile(selectedFile);
  };


  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!loading) {
      setIsDragging(true);
    }
  };


  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();

    setIsDragging(false);
  };


  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();

    setIsDragging(false);

    if (loading) {
      return;
    }

    const droppedFile =
      event.dataTransfer.files?.[0] || null;

    selectFile(droppedFile);
  };


  const openFilePicker = () => {
    if (loading) {
      return;
    }

    fileInputRef.current?.click();
  };


  const removeFile = (event) => {
    event?.stopPropagation();

    if (loading) {
      return;
    }

    setFile(null);
    setResult(null);
    clearMessages();
    clearFileInput();
  };


  const uploadFile = async () => {
    if (loading) {
      return;
    }

    if (!hasValidCourseId) {
      setError(
        "شناسه درس معتبر نیست. ابتدا شناسه عددی بزرگ‌تر از صفر وارد کنید."
      );
      return;
    }

    const validationError =
      validateFile(file);

    if (validationError) {
      setError(validationError);
      return;
    }

    if (!file) {
      setError("ابتدا یک فایل انتخاب کنید.");
      return;
    }

    const formData = new FormData();

    /*
      نام file باید با Backend هماهنگ باشد:

      async def import_topics(
          file: UploadFile = File(...),
          course_id: int = Form(...)
      )
    */
    formData.append("file", file);

    /*
      ارسال شناسه درس به‌صورت جداگانه.
      این مقدار فقط course_id است و هیچ ترکیبی
      با شناسه سرفصل ایجاد نمی‌کند.
    */
    formData.append(
      "course_id",
      String(numericCourseId)
    );

    try {
      setLoading(true);
      clearMessages();
      setResult(null);

      console.log(
        "Import topics request:",
        {
          url: "/courses/import-topics",
          course_id: numericCourseId,
          file_name: file.name,
        }
      );

      const response = await api.post(
        "/courses/import-topics",
        formData
      );

      const data = response?.data || {};

      const inserted = Number(
        data.inserted ??
          data.created ??
          data.imported ??
          data.created_count ??
          0
      );

      const skipped = Number(
        data.skipped ??
          data.duplicates ??
          data.duplicate_count ??
          data.skipped_count ??
          0
      );

      const failed = Number(
        data.failed ??
          data.errors_count ??
          data.invalid ??
          data.failed_count ??
          0
      );

      const calculatedTotal =
        inserted + skipped + failed;

      const total = Number(
        data.total ??
          data.total_rows ??
          data.rows_count ??
          calculatedTotal
      );

      const responseMessage =
        data.message ||
        "فایل با موفقیت پردازش شد.";

      const uploadResult = {
        message: responseMessage,
        inserted,
        skipped,
        failed,
        total,
      };

      setResult(uploadResult);
      setMessage(responseMessage);

      /*
        اطلاع به App.jsx برای تازه‌سازی فهرست سرفصل‌ها
      */
      if (typeof onSuccess === "function") {
        onSuccess(data);
      }

      /*
        پاک‌کردن فایل پس از موفقیت
      */
      setFile(null);
      clearFileInput();
    } catch (requestError) {
      console.error(
        "Import topics error:",
        requestError
      );

      setError(
        String(
          getApiError(requestError) ||
            "بارگذاری و ثبت سرفصل‌ها انجام نشد."
        )
      );
    } finally {
      setLoading(false);
    }
  };


  return (
    <section
      className="card course-import-card"
      dir="rtl"
    >
      <div className="course-import-header">
        <div className="course-import-icon">
          📥
        </div>

        <div>
          <span className="section-kicker">
            مدیریت آموزشی
          </span>

          <h2>بارگذاری سرفصل‌ها</h2>

          <p>
            فایل سرفصل‌های درس را برای ثبت در سامانه
            انتخاب کنید.
          </p>
        </div>
      </div>


      <div className="course-import-help">
        <strong>
          درس انتخاب‌شده:
        </strong>

        <span>
          {hasValidCourseId
            ? `شناسه درس ${numericCourseId}`
            : "شناسه درس معتبر نیست"}
        </span>

        <strong>
          ساختار پیشنهادی فایل:
        </strong>

        <span>
          id، course_id، title، description،
          session_minute، sort_order و is_active
        </span>

        <small>
          فرمت‌های مجاز: XLSX، CSV، TSV و TXT ـ حداکثر
          حجم: ۱۰ مگابایت
        </small>
      </div>


      <div
        className={`file-drop-zone ${
          isDragging ? "dragging" : ""
        } ${file ? "has-file" : ""} ${
          loading || !hasValidCourseId
            ? "disabled"
            : ""
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={openFilePicker}
        role="button"
        tabIndex={
          loading || !hasValidCourseId
            ? -1
            : 0
        }
        aria-label="انتخاب فایل سرفصل‌ها"
        onKeyDown={(event) => {
          if (
            !loading &&
            hasValidCourseId &&
            (event.key === "Enter" ||
              event.key === " ")
          ) {
            event.preventDefault();
            openFilePicker();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          hidden
          accept={ACCEPTED_EXTENSIONS.join(",")}
          onChange={handleFileChange}
          disabled={
            loading || !hasValidCourseId
          }
        />

        {!file ? (
          <>
            <div className="drop-zone-icon">
              📄
            </div>

            <strong>
              فایل را اینجا رها کنید
            </strong>

            <span>
              یا برای انتخاب فایل کلیک کنید
            </span>

            <small>
              XLSX، CSV، TSV، TXT
            </small>
          </>
        ) : (
          <div
            className="selected-file"
            onClick={(event) =>
              event.stopPropagation()
            }
          >
            <div className="selected-file-icon">
              {getFileExtension(
                file.name
              ) === ".xlsx"
                ? "📊"
                : "📄"}
            </div>

            <div className="selected-file-info">
              <strong>{file.name}</strong>

              <span>
                {formatFileSize(file.size)} ـ{" "}
                {getFileExtension(file.name)
                  .replace(".", "")
                  .toUpperCase()}
              </span>
            </div>

            <button
              type="button"
              className="remove-file-button"
              onClick={removeFile}
              disabled={loading}
              aria-label="حذف فایل"
              title="حذف فایل"
            >
              ×
            </button>
          </div>
        )}
      </div>


      {!hasValidCourseId && (
        <div
          className="import-alert import-error"
          role="alert"
        >
          <span className="alert-icon">
            !
          </span>

          <p>
            برای بارگذاری فایل، ابتدا یک شناسه درس معتبر وارد کنید.
          </p>
        </div>
      )}


      {error && (
        <div
          className="import-alert import-error"
          role="alert"
        >
          <span className="alert-icon">
            !
          </span>

          <p>{error}</p>

          <button
            type="button"
            onClick={() => setError("")}
            aria-label="بستن پیام خطا"
          >
            ×
          </button>
        </div>
      )}


      {message && !error && (
        <div
          className="import-alert import-success"
          role="status"
        >
          <span className="alert-icon">
            ✓
          </span>

          <p>{message}</p>
        </div>
      )}


      {result && (
        <div className="import-result">
          <div className="import-result-header">
            <strong>
              گزارش بارگذاری
            </strong>

            <span>✓</span>
          </div>

          <div className="import-stat-grid">
            <div className="import-stat total">
              <strong>{result.total}</strong>
              <span>کل ردیف‌ها</span>
            </div>

            <div className="import-stat inserted">
              <strong>
                {result.inserted}
              </strong>

              <span>ثبت‌شده</span>
            </div>

            <div className="import-stat skipped">
              <strong>
                {result.skipped}
              </strong>

              <span>تکراری</span>
            </div>

            <div className="import-stat failed">
              <strong>
                {result.failed}
              </strong>

              <span>نامعتبر</span>
            </div>
          </div>
        </div>
      )}


      <div className="course-import-actions">
        <button
          type="button"
          className="primary-button upload-button"
          onClick={uploadFile}
          disabled={
            !file ||
            loading ||
            !hasValidCourseId
          }
        >
          {loading ? (
            <>
              <span className="button-spinner"></span>
              در حال پردازش فایل...
            </>
          ) : (
            <>
              <span>⬆</span>
              بارگذاری و ثبت سرفصل‌ها
            </>
          )}
        </button>

        {file && !loading && (
          <button
            type="button"
            className="secondary-button"
            onClick={removeFile}
          >
            پاک کردن انتخاب
          </button>
        )}
      </div>


      {loading && (
        <div className="upload-progress-message">
          <span className="small-spinner"></span>
          فایل در حال ارسال و پردازش است؛ لطفاً صفحه را
          نبندید.
        </div>
      )}
    </section>
  );
}


export default CourseImport;