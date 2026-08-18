import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import api, { getApiError } from "../api";

import {
  exportPowerPointFile,
  getContentBody,
  getExportHtml,
  getBodyLines,
  isBullet,
  isHeading,
  isNumbered,
  cleanHeading,
  getBulletText,
  getNumber,
  getNumberedText,
  downloadFile,
  safeFileName,
} from "./ContentExporter.js";

import "./ContentGenerator.css";

const DEFAULT_PROVIDER = "openai_compatible";
const DEFAULT_MODEL = "gpt-5.6";
const DEFAULT_LANGUAGE = "fa";

const MIN_QUESTION_COUNT = 1;
const MAX_QUESTION_COUNT = 100;

const toPositiveInteger = (value) => {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const number = Number(value);

  if (!Number.isInteger(number) || number <= 0) {
    return null;
  }

  return number;
};

/*
 * تبدیل سطح نمایشی Frontend به مقدار مورد انتظار Backend
 *
 * Frontend:
 * beginner
 * intermediate
 * advanced
 *
 * Backend:
 * easy
 * medium
 * hard
 */
const normalizeQuizDifficulty = (value) => {
  const difficultyMap = {
    beginner: "easy",
    intermediate: "medium",
    advanced: "hard",

    // اگر قبلاً مستقیماً یکی از مقادیر Backend ارسال شده باشد
    easy: "easy",
    medium: "medium",
    hard: "hard",
  };

  return difficultyMap[value] || "medium";
};

/**
 * شناسه واقعی سرفصل همان topic.id است.
 *
 * توجه:
 * courseId نباید به جای topic_id استفاده شود.
 * شناسه‌هایی مانند 1038016 نباید به 16 تبدیل شوند.
 */
const getSafeTopicId = (topic) => {
  if (!topic || typeof topic !== "object") {
    return null;
  }

  const possibleIds = [
    topic.id,
    topic.topic_id,
    topic.topicId,
    topic.real_topic_id,
  ];

  for (const value of possibleIds) {
    const validId = toPositiveInteger(value);

    if (validId) {
      return validId;
    }
  }

  return null;
};

const getContentId = (content) => {
  if (!content || typeof content !== "object") {
    return null;
  }

  return toPositiveInteger(
    content.id ?? content.content_id
  );
};

const getErrorMessage = (error) => {
  const status = error?.response?.status;
  const responseData = error?.response?.data;
  const detail = responseData?.detail;

  // ۱. خطاهای اعتبارسنجی (۴۲۲)
  if (status === 422) {
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) => {
          const location = Array.isArray(item.loc)
            ? item.loc.join(" → ")
            : "";

          let message =
            item.msg || "مقدار ارسال‌شده معتبر نیست.";

          // تبدیل پیام‌های انگلیسی Validation به پیام فارسی
          if (
            item.loc?.includes("difficulty") &&
            item.type === "literal_error"
          ) {
            message =
              "سطح آزمون باید یکی از مقادیر easy، medium یا hard باشد.";
          }

          return location
            ? `${location}: ${message}`
            : message;
        })
        .join(" | ");
    }

    if (typeof detail === "string") {
      return detail;
    }

    return (
      "اطلاعات ارسالی با ساختار مورد انتظار Backend مطابقت ندارد."
    );
  }

  // ۲. خطاهای کلاینت (۴۰۰)
  if (status === 400) {
    return typeof detail === "string"
      ? detail
      : "اطلاعات درخواست معتبر نیست.";
  }

  // ۳. خطای پیدا نشدن (۴۰۴)
  if (status === 404) {
    return (
      "سرفصل، محتوای آموزشی یا مسیر API پیدا نشد."
    );
  }

  // ۴. محدودیت نرخ درخواست (۴۲۹)
  if (status === 429) {
    return (
      "محدودیت درخواست سرویس هوش مصنوعی اعمال شده است. " +
      "لطفاً چند دقیقه بعد دوباره تلاش کنید."
    );
  }

  // ۵. خطای دروازه (۵۰۲)
  if (status === 502) {
    return (
      "ارتباط با سرویس هوش مصنوعی ناموفق بود. " +
      "تنظیمات API، مدل و اعتبار حساب را بررسی کنید."
    );
  }

  // ۶. سرویس در دسترس نیست (۵۰۳)
  if (status === 503) {
    return (
      "سرویس هوش مصنوعی موقتاً در دسترس نیست. " +
      "لطفاً بعداً دوباره تلاش کنید."
    );
  }

  // ۷. خطای داخلی سرور (۵۰۰) – جزئیات کامل را نشان بده
  if (status === 500) {
    let errorMessage = "خطای داخلی سرور (۵۰۰) رخ داده است.";

    if (typeof detail === "string" && detail.trim()) {
      errorMessage = `خطای سرور: ${detail}`;
    } else if (responseData && typeof responseData === "object") {
      try {
        // تلاش برای نمایش کامل پاسخ به صورت JSON
        const jsonString = JSON.stringify(responseData, null, 2);
        errorMessage = `خطای داخلی سرور (۵۰۰) – پاسخ کامل:\n${jsonString}`;
      } catch {
        // در صورت عدم موفقیت، از پیام پیش‌فرض استفاده می‌کنیم
      }
    }
    return errorMessage;
  }

  // ۸. سایر خطاها – تلاش برای استخراج پیام
  try {
    return String(getApiError(error));
  } catch {
    return (
      error?.message ||
      "خطایی در ارتباط با سرور رخ داد."
    );
  }
};

function ContentGenerator({
  topic,
  courseId,
  onQuizCreated,
  quizOnly = false,
}) {
  const [contents, setContents] = useState([]);
  const [selectedContent, setSelectedContent] =
    useState(null);

  const [customText, setCustomText] = useState("");
  const [questionCount, setQuestionCount] = useState(5);

  const [questionType, setQuestionType] = useState(
    "multiple_choice"
  );

  const [provider, setProvider] = useState(
    DEFAULT_PROVIDER
  );

  const [model, setModel] = useState(DEFAULT_MODEL);
  const [level, setLevel] = useState("intermediate");
  const [contentType, setContentType] =
    useState("lesson");

  const [loadingContents, setLoadingContents] =
    useState(false);

  const [generatingContent, setGeneratingContent] =
    useState(false);

  const [quizLoading, setQuizLoading] =
    useState(false);

  const [copyLoading, setCopyLoading] =
    useState(false);

  const [pptLoading, setPptLoading] =
    useState(false);

  const [message, setMessage] = useState("");
  const [messageType, setMessageType] =
    useState("info");

  const [activeTab, setActiveTab] = useState(
    quizOnly ? "quiz" : "content"
  );

  const generationLockRef = useRef(false);
  const quizLockRef = useRef(false);
  const loadRequestIdRef = useRef(0);

  const safeTopicId = useMemo(() => {
    return getSafeTopicId(topic);
  }, [
    topic?.id,
    topic?.topic_id,
    topic?.topicId,
    topic?.real_topic_id,
  ]);

  const safeCourseId = useMemo(() => {
    return toPositiveInteger(courseId);
  }, [courseId]);

  const showMessage = useCallback(
    (text, type = "info") => {
      setMessage(text || "");
      setMessageType(type);
    },
    []
  );

  const bodyLines = useMemo(() => {
    return getBodyLines(selectedContent);
  }, [selectedContent]);

  const loadContents = useCallback(async () => {
    if (!safeTopicId) {
      setContents([]);
      setSelectedContent(null);
      setLoadingContents(false);
      return;
    }

    const requestId = ++loadRequestIdRef.current;

    try {
      setLoadingContents(true);
      setMessage("");

      console.log(
        "GET content with real topic id:",
        safeTopicId
      );

      const response = await api.get(
        `/content/topic/${safeTopicId}`
      );

      if (
        requestId !== loadRequestIdRef.current
      ) {
        return;
      }

      const responseData = response.data;

      const items = Array.isArray(responseData)
        ? responseData
        : Array.isArray(responseData?.items)
          ? responseData.items
          : Array.isArray(responseData?.contents)
            ? responseData.contents
            : [];

      setContents(items);

      setSelectedContent((previous) => {
        if (!items.length) {
          return null;
        }

        const previousId =
          getContentId(previous);

        if (previousId) {
          const sameContent = items.find(
            (item) =>
              String(getContentId(item)) ===
              String(previousId)
          );

          if (sameContent) {
            return sameContent;
          }
        }

        return items[0];
      });
    } catch (error) {
      if (
        requestId !== loadRequestIdRef.current
      ) {
        return;
      }

      console.error(
        "Load contents error:",
        error
      );

      setContents([]);
      setSelectedContent(null);

      showMessage(
        getErrorMessage(error),
        "error"
      );
    } finally {
      if (
        requestId === loadRequestIdRef.current
      ) {
        setLoadingContents(false);
      }
    }
  }, [safeTopicId, showMessage]);

  useEffect(() => {
    setContents([]);
    setSelectedContent(null);
    setCustomText("");
    setQuestionCount(5);
    setQuestionType("multiple_choice");
    setMessage("");
    setActiveTab(quizOnly ? "quiz" : "content");

    loadContents();
  }, [loadContents, quizOnly]);

  const createContent = useCallback(async () => {
    if (generationLockRef.current) {
      return;
    }

    if (!safeTopicId) {
      showMessage(
        "ابتدا یک سرفصل معتبر انتخاب کنید.",
        "error"
      );
      return;
    }

    const normalizedModel = String(
      model || ""
    ).trim();

    if (!normalizedModel) {
      showMessage(
        "نام مدل هوش مصنوعی را وارد کنید.",
        "error"
      );
      return;
    }

    generationLockRef.current = true;

    try {
      setGeneratingContent(true);
      setMessage("");

      const payload = {
        topic_id: safeTopicId,
        custom_text:
          String(customText || "").trim() || null,
        provider,
        model: normalizedModel,
        language: DEFAULT_LANGUAGE,
        level,
        content_type: contentType,
      };

      console.log(
        "POST content generation:",
        `/content/generate/${safeTopicId}`,
        payload
      );

      const response = await api.post(
        `/content/generate/${safeTopicId}`,
        payload
      );

      const generatedContent =
        response.data?.content ||
        response.data?.data ||
        response.data;

      if (
        !generatedContent ||
        typeof generatedContent !== "object"
      ) {
        throw new Error(
          "محتوای معتبر از Backend دریافت نشد."
        );
      }

      const generatedBody =
        getContentBody(generatedContent);

      if (
        !generatedBody ||
        !String(generatedBody).trim()
      ) {
        throw new Error(
          "متن محتوای تولیدشده خالی است."
        );
      }

      setSelectedContent(generatedContent);

      setContents((previous) => {
        const generatedId =
          getContentId(generatedContent);

        const filtered = generatedId
          ? previous.filter(
              (item) =>
                String(getContentId(item)) !==
                String(generatedId)
            )
          : previous;

        return [
          generatedContent,
          ...filtered,
        ];
      });

      setActiveTab("content");

      showMessage(
        "محتوای آموزشی با موفقیت تولید شد.",
        "success"
      );
    } catch (error) {
      console.error(
        "Content generation error:",
        error
      );

      showMessage(
        getErrorMessage(error),
        "error"
      );
    } finally {
      generationLockRef.current = false;
      setGeneratingContent(false);
    }
  }, [
    safeTopicId,
    model,
    customText,
    provider,
    level,
    contentType,
    showMessage,
  ]);

  const createQuiz = useCallback(async () => {
    if (quizLockRef.current) {
      return;
    }

    if (!safeTopicId) {
      showMessage(
        "سرفصل معتبر انتخاب نشده است.",
        "error"
      );
      return;
    }

    const contentId =
      getContentId(selectedContent);

    if (!contentId) {
      showMessage(
        "ابتدا یک محتوای آموزشی تولید یا انتخاب کنید.",
        "error"
      );
      return;
    }

    const count = Number(questionCount);

    if (
      !Number.isInteger(count) ||
      count < MIN_QUESTION_COUNT ||
      count > MAX_QUESTION_COUNT
    ) {
      showMessage(
        `تعداد سؤالات باید بین ${MIN_QUESTION_COUNT} تا ${MAX_QUESTION_COUNT} باشد.`,
        "error"
      );
      return;
    }

    const normalizedQuestionType =
      questionType === "essay"
        ? "essay"
        : "multiple_choice";

    /*
     * نکته مهم:
     * level برای بخش محتوا از مقادیر beginner/intermediate/advanced
     * استفاده می‌کند، اما Backend آزمون مقادیر
     * easy/medium/hard را انتظار دارد.
     */
    const normalizedDifficulty =
      normalizeQuizDifficulty(level);

    quizLockRef.current = true;

    try {
      setQuizLoading(true);
      setMessage("");

      /*
       * ساختن payload – course_id را فقط در صورت وجود ارسال می‌کنیم
       * (نه null) تا از هرگونه ابهام در Backend جلوگیری شود.
       */
      const payload = {
        topic_id: safeTopicId,
        content_id: contentId,
        number_of_questions: count,
        question_type: normalizedQuestionType,
        difficulty: normalizedDifficulty,
        language: DEFAULT_LANGUAGE,
      };

      // فقط در صورت وجود course_id معتبر، آن را به payload اضافه کن
      if (safeCourseId) {
        payload.course_id = safeCourseId;
      }

      console.log(
        "POST quiz generation:",
        "/quizzes/generate"
      );

      console.log(
        "Quiz payload (JSON):",
        JSON.stringify(payload, null, 2)
      );

      const response = await api.post(
        "/quizzes/generate",
        payload
      );

      const responseData = response.data;

      const quiz =
        responseData?.quiz ||
        responseData?.data ||
        responseData;

      const quizId = toPositiveInteger(
        quiz?.id ??
          quiz?.quiz_id ??
          responseData?.quiz_id
      );

      if (!quizId) {
        throw new Error(
          "شناسه آزمون از Backend دریافت نشد."
        );
      }

      showMessage(
        "آزمون با موفقیت ساخته شد.",
        "success"
      );

      if (typeof onQuizCreated === "function") {
        onQuizCreated(quizId);
      }
    } catch (error) {
      console.error(
        "Quiz generation error:",
        error
      );

      // نمایش کامل پاسخ سرور برای خطاهای ۵۰۰ (و سایر خطاها)
      if (error?.response) {
        console.error(
          "Server response status:",
          error.response.status
        );
        console.error(
          "Server response data (full):",
          JSON.stringify(error.response.data, null, 2)
        );
      }

      console.error(
        "Validation details (if any):",
        JSON.stringify(
          error?.response?.data?.detail,
          null,
          2
        )
      );

      // نمایش پیام خطای به‌دست‌آمده
      showMessage(
        getErrorMessage(error),
        "error"
      );
    } finally {
      quizLockRef.current = false;
      setQuizLoading(false);
    }
  }, [
    safeTopicId,
    safeCourseId,
    selectedContent,
    questionCount,
    questionType,
    level,
    onQuizCreated,
    showMessage,
  ]);

  const renderContentBody = useCallback(() => {
    if (!bodyLines.length) {
      return (
        <div className="content-empty">
          <span className="empty-icon">
            📄
          </span>

          <strong>
            محتوایی برای نمایش وجود ندارد
          </strong>

          <small>
            ابتدا محتوای آموزشی تولید کنید.
          </small>
        </div>
      );
    }

    return bodyLines.map((line, index) => {
      if (isHeading(line)) {
        return (
          <h3
            className="generated-heading"
            key={`heading-${index}`}
          >
            <span className="heading-mark" />
            {cleanHeading(line)}
          </h3>
        );
      }

      if (isBullet(line)) {
        return (
          <div
            className="generated-list-item"
            key={`bullet-${index}`}
          >
            <span className="list-marker">
              •
            </span>

            <p>{getBulletText(line)}</p>
          </div>
        );
      }

      if (isNumbered(line)) {
        return (
          <div
            className="generated-list-item numbered"
            key={`number-${index}`}
          >
            <span className="list-marker">
              {getNumber(line)}
            </span>

            <p>{getNumberedText(line)}</p>
          </div>
        );
      }

      return (
        <p
          className="generated-paragraph"
          key={`paragraph-${index}`}
        >
          {line}
        </p>
      );
    });
  }, [bodyLines]);

  const exportHtml = useCallback(() => {
    if (!selectedContent) {
      showMessage(
        "ابتدا یک محتوا را انتخاب کنید.",
        "error"
      );
      return;
    }

    const html = getExportHtml({
      topic,
      content: selectedContent,
      topicId: safeTopicId,
    });

    downloadFile(
      html,
      `${safeFileName(
        selectedContent.title ||
          "educational-content"
      )}.html`,
      "text/html;charset=utf-8"
    );

    showMessage(
      "فایل HTML با موفقیت دریافت شد.",
      "success"
    );
  }, [
    selectedContent,
    topic,
    safeTopicId,
    showMessage,
  ]);

  const exportWord = useCallback(() => {
    if (!selectedContent) {
      showMessage(
        "ابتدا یک محتوا را انتخاب کنید.",
        "error"
      );
      return;
    }

    const html = getExportHtml({
      topic,
      content: selectedContent,
      topicId: safeTopicId,
    });

    downloadFile(
      html,
      `${safeFileName(
        selectedContent.title ||
          "educational-content"
      )}.doc`,
      "application/msword;charset=utf-8"
    );

    showMessage(
      "فایل Word با موفقیت ایجاد شد.",
      "success"
    );
  }, [
    selectedContent,
    topic,
    safeTopicId,
    showMessage,
  ]);

  const exportPowerPoint = useCallback(async () => {
    if (!selectedContent) {
      showMessage(
        "ابتدا یک محتوا را انتخاب کنید.",
        "error"
      );
      return;
    }

    if (pptLoading) {
      return;
    }

    try {
      setPptLoading(true);
      setMessage("");

      await exportPowerPointFile({
        topic,
        content: selectedContent,
        topicId: safeTopicId,
      });

      showMessage(
        "فایل PowerPoint با موفقیت ایجاد شد.",
        "success"
      );
    } catch (error) {
      console.error(
        "PowerPoint export error:",
        error
      );

      showMessage(
        "ساخت فایل PowerPoint انجام نشد. نصب بودن pptxgenjs و ساختار ContentExporter را بررسی کنید.",
        "error"
      );
    } finally {
      setPptLoading(false);
    }
  }, [
    selectedContent,
    topic,
    safeTopicId,
    pptLoading,
    showMessage,
  ]);

  const copyContent = useCallback(async () => {
    if (!selectedContent) {
      showMessage(
        "محتوایی برای کپی‌کردن وجود ندارد.",
        "error"
      );
      return;
    }

    if (copyLoading) {
      return;
    }

    try {
      setCopyLoading(true);

      const text = String(
        getContentBody(selectedContent) || ""
      );

      if (
        navigator.clipboard &&
        typeof navigator.clipboard.writeText ===
          "function"
      ) {
        await navigator.clipboard.writeText(text);
      } else {
        const area =
          document.createElement("textarea");

        area.value = text;
        area.style.position = "fixed";
        area.style.left = "-9999px";
        area.style.top = "0";
        area.style.opacity = "0";

        document.body.appendChild(area);
        area.focus();
        area.select();

        const copied =
          document.execCommand("copy");

        document.body.removeChild(area);

        if (!copied) {
          throw new Error("Copy failed");
        }
      }

      showMessage(
        "متن محتوا کپی شد.",
        "success"
      );
    } catch (error) {
      console.error(
        "Copy content error:",
        error
      );

      showMessage(
        "کپی محتوا توسط مرورگر انجام نشد.",
        "error"
      );
    } finally {
      setCopyLoading(false);
    }
  }, [
    selectedContent,
    copyLoading,
    showMessage,
  ]);

  const printContent = useCallback(() => {
    if (!selectedContent) {
      showMessage(
        "ابتدا یک محتوا را انتخاب کنید.",
        "error"
      );
      return;
    }

    const printWindow = window.open(
      "",
      "_blank",
      "width=1100,height=850"
    );

    if (!printWindow) {
      showMessage(
        "مرورگر اجازه بازشدن پنجره چاپ را نداد.",
        "error"
      );
      return;
    }

    const html = getExportHtml({
      topic,
      content: selectedContent,
      topicId: safeTopicId,
    });

    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();

    printWindow.onload = () => {
      printWindow.focus();
      printWindow.print();
    };
  }, [
    selectedContent,
    topic,
    safeTopicId,
    showMessage,
  ]);

  const formatDate = useCallback((value) => {
    if (!value) {
      return "امروز";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return "امروز";
    }

    return date.toLocaleDateString("fa-IR");
  }, []);

  if (!topic) {
    return (
      <section className="card content-generator-card">
        <div className="content-empty">
          <span className="empty-icon">
            📚
          </span>

          <strong>
            سرفصلی انتخاب نشده است
          </strong>

          <small>
            برای ادامه ابتدا یک سرفصل انتخاب کنید.
          </small>
        </div>
      </section>
    );
  }

  return (
    <section
      className="card content-generator-card"
      dir="rtl"
    >
      <header className="content-generator-header">
        <div>
          <span className="section-kicker">
            دستیار هوشمند آموزشی
          </span>

          <h2>
            {quizOnly
              ? "تولید آزمون هوشمند"
              : "تولید و مدیریت محتوای درسی"}
          </h2>

          <p>
            {quizOnly
              ? "بر اساس محتوای آموزشی انتخاب‌شده آزمون بسازید."
              : "محتوای آموزشی ساختاریافته تولید و دریافت کنید."}
          </p>
        </div>

        <div className="ai-status">
          <span className="ai-status-dot" />
          آماده استفاده
        </div>
      </header>

      <div className="content-topic-banner">
        <div className="topic-banner-icon">
          📖
        </div>

        <div className="topic-banner-text">
          <span>سرفصل انتخاب‌شده</span>

          <h3>
            {topic.title || "سرفصل بدون عنوان"}
          </h3>

          <p>
            {topic.description ||
              "برای این سرفصل توضیحی ثبت نشده است."}
          </p>
        </div>

        <div className="topic-meta">
          <div>
            <span>
              شناسه ارسالی به Backend
            </span>

            <strong>
              {safeTopicId || "-"}
            </strong>
          </div>

          <div>
            <span>زمان جلسه</span>

            <strong>
              {topic.session_minute || 0} دقیقه
            </strong>
          </div>
        </div>
      </div>

      {!quizOnly && (
        <nav className="content-tabs">
          <button
            type="button"
            className={
              activeTab === "content"
                ? "content-tab active"
                : "content-tab"
            }
            onClick={() =>
              setActiveTab("content")
            }
          >
            ✨ تولید محتوا
          </button>

          <button
            type="button"
            className={
              activeTab === "history"
                ? "content-tab active"
                : "content-tab"
            }
            onClick={() =>
              setActiveTab("history")
            }
          >
            🗂 محتواهای قبلی
            <b>{contents.length}</b>
          </button>

          <button
            type="button"
            className={
              activeTab === "quiz"
                ? "content-tab active"
                : "content-tab"
            }
            onClick={() =>
              setActiveTab("quiz")
            }
          >
            🧠 ساخت آزمون
          </button>
        </nav>
      )}

      {!quizOnly && activeTab === "content" && (
        <div className="generation-panel">
          <div className="generation-panel-header">
            <div>
              <h3>
                تولید محتوای جدید
              </h3>

              <p>
                تنظیمات تولید محتوا را مشخص کنید.
              </p>
            </div>

            <div className="generation-icon">
              ⚡
            </div>
          </div>

          <div className="ai-options-grid">
            <div>
              <label htmlFor="ai-provider">
                سرویس هوش مصنوعی
              </label>

              <select
                id="ai-provider"
                className="content-input"
                value={provider}
                onChange={(event) =>
                  setProvider(event.target.value)
                }
                disabled={generatingContent}
              >
                <option value="openai_compatible">
                  OpenAI Compatible
                </option>

                <option value="openai">
                  OpenAI
                </option>

                <option value="ollama">
                  Ollama محلی
                </option>
              </select>
            </div>

            <div>
              <label htmlFor="ai-model">
                مدل هوش مصنوعی
              </label>

              <input
                id="ai-model"
                className="content-input"
                value={model}
                onChange={(event) =>
                  setModel(event.target.value)
                }
                placeholder="مدل تنظیم‌شده در Backend"
                disabled={generatingContent}
              />
            </div>

            <div>
              <label htmlFor="content-level">
                سطح محتوا
              </label>

              <select
                id="content-level"
                className="content-input"
                value={level}
                onChange={(event) =>
                  setLevel(event.target.value)
                }
                disabled={generatingContent}
              >
                <option value="beginner">
                  مقدماتی
                </option>

                <option value="intermediate">
                  متوسط
                </option>

                <option value="advanced">
                  پیشرفته
                </option>
              </select>
            </div>

            <div>
              <label htmlFor="content-type">
                نوع محتوا
              </label>

              <select
                id="content-type"
                className="content-input"
                value={contentType}
                onChange={(event) =>
                  setContentType(event.target.value)
                }
                disabled={generatingContent}
              >
                <option value="lesson">
                  درس آموزشی
                </option>

                <option value="summary">
                  خلاصه آموزشی
                </option>

                <option value="article">
                  مقاله آموزشی
                </option>

                <option value="handout">
                  جزوه دانشگاهی
                </option>

                <option value="presentation">
                  محتوای ارائه
                </option>
              </select>
            </div>
          </div>

          <label htmlFor="custom-content">
            توضیحات اختصاصی استاد
          </label>

          <textarea
            id="custom-content"
            className="content-input"
            value={customText}
            onChange={(event) =>
              setCustomText(event.target.value)
            }
            placeholder="مثلاً محتوا شامل تعریف، مثال، کاربرد، نکات مهم و جمع‌بندی باشد."
            disabled={generatingContent}
          />

          <div className="generation-actions">
            <button
              type="button"
              className="primary-action"
              onClick={createContent}
              disabled={
                generatingContent ||
                loadingContents ||
                !safeTopicId
              }
            >
              {generatingContent
                ? "در حال تولید محتوا..."
                : "✨ تولید محتوای آموزشی"}
            </button>

            {customText &&
              !generatingContent && (
                <button
                  type="button"
                  className="light-action"
                  onClick={() =>
                    setCustomText("")
                  }
                >
                  پاک‌کردن متن
                </button>
              )}
          </div>
        </div>
      )}

      {!quizOnly && activeTab === "history" && (
        <div className="history-panel">
          <h3>محتواهای قبلی</h3>

          {loadingContents &&
          !contents.length ? (
            <div className="content-empty">
              در حال دریافت محتواها...
            </div>
          ) : !contents.length ? (
            <div className="content-empty">
              هنوز محتوایی تولید نشده است.
            </div>
          ) : (
            <div className="content-history-list">
              {contents.map((item, index) => {
                const itemId =
                  getContentId(item);

                const selectedId =
                  getContentId(selectedContent);

                return (
                  <button
                    type="button"
                    key={itemId || index}
                    className={
                      String(selectedId) ===
                      String(itemId)
                        ? "history-item selected"
                        : "history-item"
                    }
                    onClick={() => {
                      setSelectedContent(item);
                      setActiveTab("content");
                    }}
                  >
                    <span className="history-number">
                      {index + 1}
                    </span>

                    <span className="history-item-info">
                      <strong>
                        {item.title ||
                          "محتوای بدون عنوان"}
                      </strong>

                      <small>
                        منبع:{" "}
                        {item.source ||
                          "هوش مصنوعی"}
                      </small>
                    </span>

                    <span>←</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {(quizOnly || activeTab === "quiz") && (
        <div className="quiz-generation-panel">
          <div className="quiz-intro">
            <div className="quiz-intro-icon">
              🧠
            </div>

            <div>
              <h3>
                ساخت آزمون هوشمند
              </h3>

              <p>
                آزمون بر اساس محتوای انتخاب‌شده تولید می‌شود.
              </p>
            </div>
          </div>

          {!selectedContent ? (
            <div className="content-empty">
              ابتدا یک محتوای آموزشی تولید یا انتخاب کنید.
            </div>
          ) : (
            <>
              <div className="selected-content-preview">
                <span>محتوای مبنا</span>

                <strong>
                  {selectedContent.title ||
                    "محتوای آموزشی انتخاب‌شده"}
                </strong>
              </div>

              <div className="quiz-options-grid">
                <div>
                  <label htmlFor="question-type">
                    نوع آزمون
                  </label>

                  <select
                    id="question-type"
                    className="content-input"
                    value={questionType}
                    onChange={(event) => {
                      setQuestionType(
                        event.target.value
                      );
                      setMessage("");
                    }}
                    disabled={quizLoading}
                  >
                    <option value="multiple_choice">
                      چهارگزینه‌ای
                    </option>

                    <option value="essay">
                      تشریحی
                    </option>
                  </select>
                </div>

                <div>
                  <label htmlFor="question-count">
                    تعداد سؤالات
                  </label>

                  <input
                    id="question-count"
                    className="content-input"
                    type="number"
                    min={MIN_QUESTION_COUNT}
                    max={MAX_QUESTION_COUNT}
                    value={questionCount}
                    onChange={(event) => {
                      setQuestionCount(
                        event.target.value
                      );
                      setMessage("");
                    }}
                    disabled={quizLoading}
                  />
                </div>

                <div>
                  <label htmlFor="quiz-level">
                    سطح آزمون
                  </label>

                  <select
                    id="quiz-level"
                    className="content-input"
                    value={level}
                    onChange={(event) => {
                      setLevel(event.target.value);
                      setMessage("");
                    }}
                    disabled={quizLoading}
                  >
                    <option value="beginner">
                      مقدماتی
                    </option>

                    <option value="intermediate">
                      متوسط
                    </option>

                    <option value="advanced">
                      پیشرفته
                    </option>
                  </select>
                </div>
              </div>

              <div className="quiz-type-description">
                {questionType === "essay" ? (
                  <p>
                    در آزمون تشریحی، پاسخ دانشجو به‌صورت متنی ثبت می‌شود.
                  </p>
                ) : (
                  <p>
                    در آزمون چهارگزینه‌ای، هر سؤال دارای چهار گزینه خواهد بود.
                  </p>
                )}
              </div>

              <button
                type="button"
                className="quiz-action"
                onClick={createQuiz}
                disabled={
                  quizLoading ||
                  !safeTopicId ||
                  !selectedContent
                }
              >
                {quizLoading
                  ? "در حال ساخت آزمون..."
                  : questionType === "essay"
                    ? "✍️ ساخت آزمون تشریحی"
                    : "🧠 ساخت آزمون چهارگزینه‌ای"}
              </button>
            </>
          )}
        </div>
      )}

      {selectedContent && (
        <section className="generated-content-section">
          <header className="generated-content-header">
            <div>
              <span className="content-label">
                محتوای انتخاب‌شده
              </span>

              <h2>
                {selectedContent.title ||
                  "محتوای آموزشی تولیدشده"}
              </h2>

              <div className="content-details">
                <span>
                  🗓{" "}
                  {formatDate(
                    selectedContent.created_at
                  )}
                </span>

                <span>
                  📌{" "}
                  {selectedContent.source ||
                    "هوش مصنوعی"}
                </span>
              </div>
            </div>

            <div className="content-actions">
              <button
                type="button"
                className="icon-action"
                onClick={copyContent}
                disabled={copyLoading}
                title="کپی محتوا"
              >
                {copyLoading ? "..." : "📋"}
              </button>

              <button
                type="button"
                className="icon-action"
                onClick={printContent}
                title="چاپ محتوا"
              >
                🖨
              </button>
            </div>
          </header>

          <div className="export-toolbar">
            <span>دریافت خروجی:</span>

            <button
              type="button"
              className="export-button html"
              onClick={exportHtml}
            >
              🌐 خروجی HTML
            </button>

            <button
              type="button"
              className="export-button word"
              onClick={exportWord}
            >
              📄 خروجی Word
            </button>

            <button
              type="button"
              className="export-button powerpoint"
              onClick={exportPowerPoint}
              disabled={pptLoading}
            >
              {pptLoading
                ? "در حال ساخت پاورپوینت..."
                : "📊 خروجی PowerPoint"}
            </button>
          </div>

          {selectedContent.summary && (
            <div className="content-summary-box">
              <strong>
                خلاصه محتوا
              </strong>

              <p>
                {selectedContent.summary}
              </p>
            </div>
          )}

          {Array.isArray(
            selectedContent.learning_objectives
          ) &&
            selectedContent.learning_objectives.length >
              0 && (
              <div className="content-objectives-box">
                <strong>
                  اهداف یادگیری
                </strong>

                <ul>
                  {selectedContent.learning_objectives.map(
                    (objective, index) => (
                      <li key={index}>
                        {objective}
                      </li>
                    )
                  )}
                </ul>
              </div>
            )}

          <article className="generated-content-body">
            {renderContentBody()}
          </article>
        </section>
      )}

      {message && (
        <div
          className={`content-message ${messageType}`}
          role="alert"
        >
          <span>
            {messageType === "success"
              ? "✓"
              : messageType === "error"
                ? "!"
                : "i"}
          </span>

          <p>{message}</p>

          <button
            type="button"
            className="message-close"
            onClick={() => setMessage("")}
            aria-label="بستن پیام"
          >
            ×
          </button>
        </div>
      )}
    </section>
  );
}

export default ContentGenerator;