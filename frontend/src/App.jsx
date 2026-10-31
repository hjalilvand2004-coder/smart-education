import { useEffect, useMemo, useState } from "react";

import CourseImport from "./components/CourseImport";
import CourseList from "./components/CourseList";
import ContentGenerator from "./components/ContentGenerator";
import Quiz from "./components/Quiz";
import AIStatsDashboard from "./components/AIStatsDashboard"; // کامپوننت جدید داشبورد
import AuthScreen from "./components/AuthScreen";
import UserManagement from "./components/UserManagement";
import api, { getApiError, getToken, setToken } from "./api";


const DEFAULT_COURSE_ID = ""; // ← تغییر: مقدار پیش‌فرض خالی


const PAGE_INFO = {
  topics: {
    title: "ثبت و مدیریت سرفصل دروس",
    subtitle:
      "بارگذاری فایل و مشاهده سرفصل‌های ثبت‌شده",
  },

  content: {
    title: "تولید محتوای دروس",
    subtitle:
      "تولید محتوای آموزشی هوشمند برای سرفصل انتخاب‌شده",
  },

  "quiz-generator": {
    title: "تولید تست و کوییز هوشمند",
    subtitle:
      "ساخت آزمون چهارگزینه‌ای بر اساس محتوای آموزشی",
  },

  "student-quiz": {
    title: "شرکت در کوییز",
    subtitle:
      "پاسخ‌دادن به سؤالات و مشاهده نتیجه آزمون",
  },

  "ai-stats": {
    title: "داشبورد هوش مصنوعی",
    subtitle:
      "مشاهده آمار و هزینه‌های استفاده از سرویس‌های هوش مصنوعی",
  },

  "user-management": {
    title: "مدیریت کاربران و سطوح دسترسی",
    subtitle:
      "تایید ثبت‌نام، فعال/غیرفعال‌سازی، تغییر نقش و بازنشانی رمز کاربران",
  },
};


const ROLE_LABELS_FA = {
  admin: "مدیر سامانه",
  group_manager: "مدیرگروه",
  professor: "استاد",
  student: "دانشجو",
};


/*
  تبدیل مقدار به عدد صحیح مثبت.
*/
const toPositiveInteger = (value) => {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const numericValue = Number(value);

  if (
    !Number.isInteger(numericValue) ||
    numericValue <= 0
  ) {
    return null;
  }

  return numericValue;
};


/*
  نرمال‌سازی شناسه درس.
*/
const normalizeCourseIdValue = (value) => {
  const numericValue = toPositiveInteger(value);

  return numericValue
    ? String(numericValue)
    : null;
};


/*
  استخراج شناسه واقعی سرفصل.
*/
const getTopicId = (topic, courseId) => {
  if (!topic || typeof topic !== "object") {
    return null;
  }

  const explicitTopicId =
    topic.topic_id ??
    topic.topicId ??
    topic.real_topic_id;

  const validExplicitTopicId =
    toPositiveInteger(explicitTopicId);

  if (validExplicitTopicId) {
    return validExplicitTopicId;
  }

  const rawTopicId = toPositiveInteger(topic.id);

  if (!rawTopicId) {
    return null;
  }

  const normalizedCourseId =
    toPositiveInteger(courseId);

  if (!normalizedCourseId) {
    return rawTopicId;
  }

  const topicIdText = String(rawTopicId);
  const courseIdText = String(normalizedCourseId);

  if (
    topicIdText.startsWith(courseIdText) &&
    topicIdText.length > courseIdText.length
  ) {
    const extractedTopicId = toPositiveInteger(
      topicIdText.slice(courseIdText.length)
    );

    if (extractedTopicId) {
      return extractedTopicId;
    }
  }

  return rawTopicId;
};


const getTopicCourseId = (topic) => {
  if (!topic || typeof topic !== "object") {
    return null;
  }

  return toPositiveInteger(
    topic.course_id ??
      topic.courseId
  );
};


function App() {
  const [courseId, setCourseId] = useState(
    DEFAULT_COURSE_ID
  );

  const [selectedTopic, setSelectedTopic] =
    useState(null);

  const [quizId, setQuizId] = useState(null);

  const [refreshTopics, setRefreshTopics] =
    useState(0);

  const [activeSection, setActiveSection] =
    useState("topics");

  const [appMessage, setAppMessage] =
    useState("");

  // ---------------- احراز هویت ----------------
  const [authUser, setAuthUser] =
    useState(null);

  const [authChecking, setAuthChecking] =
    useState(true);

  useEffect(() => {
    let cancelled = false;

    const checkSession = async () => {
      if (!getToken()) {
        setAuthChecking(false);
        return;
      }
      try {
        const res = await api.get("/auth/me");
        if (!cancelled) {
          setAuthUser(res.data.user);
        }
      } catch (err) {
        setToken("");
        if (
          !cancelled &&
          typeof window !== "undefined" &&
          window.location.hash === "#auth-expired"
        ) {
          setAppMessage("");
        }
      } finally {
        if (!cancelled) {
          setAuthChecking(false);
        }
      }
    };

    checkSession();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleAuthSuccess = (user) => {
    setAuthUser(user);
    setAppMessage(
      `خوش آمدید ${user.full_name} — نقش: ${
        ROLE_LABELS_FA[user.role] || user.role
      }`
    );
  };

  const handleLogout = () => {
    setToken("");
    setAuthUser(null);
    setActiveSection("topics");
  };

  const canManageUsers =
    authUser &&
    (authUser.role === "admin" || authUser.role === "group_manager");


  const normalizedCourseId = useMemo(() => {
    return normalizeCourseIdValue(courseId);
  }, [courseId]);


  const hasValidCourseId =
    normalizedCourseId !== null;


  const numericCourseId = useMemo(() => {
    return toPositiveInteger(normalizedCourseId);
  }, [normalizedCourseId]);


  const pageTitle = useMemo(() => {
    return (
      PAGE_INFO[activeSection] || {
        title: "سامانه هوشمند آموزش و آزمون",
        subtitle:
          "تولید محتوا، ساخت آزمون و ارزیابی دانشجو",
      }
    );
  }, [activeSection]);


  // ---------------- صفحهٔ ورود (بعد از همهٔ Hook ها) ----------------
  if (authChecking) {
    return (
      <div className="auth-screen">
        <div className="auth-loading">در حال بررسی نشست…</div>
      </div>
    );
  }

  if (!authUser) {
    return <AuthScreen onAuthSuccess={handleAuthSuccess} />;
  }


  const isTopicForCurrentCourse = (topic) => {
    if (!topic || !hasValidCourseId) {
      return false;
    }

    const topicCourseId =
      getTopicCourseId(topic);

    if (!topicCourseId) {
      return (
        getTopicId(topic, numericCourseId) !== null
      );
    }

    return topicCourseId === numericCourseId;
  };


  const resetTopicAndQuiz = () => {
    setSelectedTopic(null);
    setQuizId(null);
  };


  const handleCourseIdChange = (event) => {
    const value = event.target.value;

    setCourseId(value);
    resetTopicAndQuiz();
    setRefreshTopics((current) => current + 1);
    setActiveSection("topics");
    setAppMessage("");
  };


  const handleImportSuccess = () => {
    resetTopicAndQuiz();

    setRefreshTopics((value) => value + 1);
    setActiveSection("topics");
    setAppMessage(
      "سرفصل‌ها با موفقیت ثبت شدند."
    );
  };


  const handleSelectTopic = (topic) => {
    if (!topic) {
      resetTopicAndQuiz();
      setAppMessage("");
      return;
    }

    const realTopicId = getTopicId(
      topic,
      numericCourseId
    );

    if (!realTopicId) {
      setSelectedTopic(null);
      setQuizId(null);
      setAppMessage(
        "شناسه واقعی سرفصل معتبر نیست."
      );
      return;
    }

    if (!isTopicForCurrentCourse(topic)) {
      setSelectedTopic(null);
      setQuizId(null);
      setAppMessage(
        "این سرفصل متعلق به درس انتخاب‌شده نیست."
      );
      return;
    }

    const topicCourseId =
      getTopicCourseId(topic);

    const normalizedTopic = {
      ...topic,

      id: realTopicId,
      topic_id: realTopicId,

      course_id:
        topicCourseId || numericCourseId,
    };

    console.log(
      "Selected topic with real id:",
      normalizedTopic
    );

    setSelectedTopic(normalizedTopic);
    setQuizId(null);
    setAppMessage("");
  };


  const handleTopicsSection = () => {
    setActiveSection("topics");
    setAppMessage("");
  };


  const handleContentSection = () => {
    if (!hasValidCourseId) {
      setActiveSection("topics");
      setAppMessage(
        "ابتدا یک شناسه درس معتبر وارد کنید."
      );
      return;
    }

    if (!selectedTopic) {
      setActiveSection("topics");
      setAppMessage(
        "برای تولید محتوا، ابتدا یک سرفصل انتخاب کنید."
      );
      return;
    }

    if (
      !getTopicId(
        selectedTopic,
        numericCourseId
      )
    ) {
      setActiveSection("topics");
      setAppMessage(
        "شناسه واقعی سرفصل انتخاب‌شده معتبر نیست."
      );
      return;
    }

    setAppMessage("");
    setActiveSection("content");
  };


  const handleQuizGeneratorSection = () => {
    if (!hasValidCourseId) {
      setActiveSection("topics");
      setAppMessage(
        "ابتدا یک شناسه درس معتبر وارد کنید."
      );
      return;
    }

    if (!selectedTopic) {
      setActiveSection("topics");
      setAppMessage(
        "برای ساخت آزمون، ابتدا یک سرفصل انتخاب کنید."
      );
      return;
    }

    if (
      !getTopicId(
        selectedTopic,
        numericCourseId
      )
    ) {
      setActiveSection("topics");
      setAppMessage(
        "شناسه واقعی سرفصل انتخاب‌شده معتبر نیست."
      );
      return;
    }

    setAppMessage("");
    setActiveSection("quiz-generator");
  };


  const handleStudentQuizSection = () => {
    if (!quizId) {
      setActiveSection("quiz-generator");
      setAppMessage(
        "ابتدا یک آزمون تولید کنید."
      );
      return;
    }

    setAppMessage("");
    setActiveSection("student-quiz");
  };


  const handleAIStatsSection = () => {
    setActiveSection("ai-stats");
    setAppMessage("");
  };


  const handleQuizCreated = (newQuizId) => {
    const numericQuizId =
      toPositiveInteger(newQuizId);

    if (!numericQuizId) {
      setAppMessage(
        "شناسه معتبر آزمون دریافت نشد."
      );
      return;
    }

    setQuizId(numericQuizId);
    setActiveSection("student-quiz");
    setAppMessage(
      "آزمون با موفقیت ساخته شد و آماده برگزاری است."
    );
  };


  const renderEmptyState = ({
    icon,
    title,
    description,
    buttonText,
    onClick,
  }) => {
    return (
      <section
        className="card empty-state"
        dir="rtl"
      >
        <div className="empty-state-icon">
          {icon}
        </div>

        <h2>{title}</h2>

        <p>{description}</p>

        <button
          type="button"
          className="primary-button"
          onClick={onClick}
        >
          {buttonText}
        </button>
      </section>
    );
  };


  const renderActivePage = () => {
    if (activeSection === "user-management") {
      return <UserManagement currentUser={authUser} />;
    }

    if (!hasValidCourseId) {
      return renderEmptyState({
        icon: "⚠️",
        title: "شناسه درس معتبر نیست",
        description:
          "لطفاً در نوار سمت راست یک شناسه عددی معتبر برای درس وارد کنید.",
        buttonText:
          "ورود شناسه درس",
        onClick: () => {
          // فوکوس روی فیلد شناسه درس
          document.getElementById("sidebar-course-id")?.focus();
        },
      });
    }


    if (activeSection === "topics") {
      return (
        <>
          <CourseImport
            courseId={normalizedCourseId}
            onSuccess={handleImportSuccess}
          />

          <CourseList
            courseId={normalizedCourseId}
            refreshKey={refreshTopics}
            selectedTopicId={
              selectedTopic?.topic_id ??
              selectedTopic?.id ??
              null
            }
            onSelectTopic={handleSelectTopic}
          />
        </>
      );
    }


    if (activeSection === "content") {
      if (!selectedTopic) {
        return renderEmptyState({
          icon: "📚",
          title:
            "ابتدا یک سرفصل انتخاب کنید",
          description:
            "برای تولید محتوای آموزشی، ابتدا از بخش ثبت سرفصل دروس یک سرفصل را انتخاب کنید.",
          buttonText:
            "مشاهده سرفصل‌ها",
          onClick: handleTopicsSection,
        });
      }

      return (
        <ContentGenerator
          topic={selectedTopic}
          courseId={normalizedCourseId}
          quizOnly={false}
          onQuizCreated={handleQuizCreated}
        />
      );
    }


    if (
      activeSection === "quiz-generator"
    ) {
      if (!selectedTopic) {
        return renderEmptyState({
          icon: "🧠",
          title:
            "ابتدا یک سرفصل انتخاب کنید",
          description:
            "برای ساخت آزمون هوشمند، ابتدا از جدول سرفصل‌ها یک سرفصل را انتخاب کنید.",
          buttonText:
            "انتخاب سرفصل",
          onClick: handleTopicsSection,
        });
      }

      return (
        <ContentGenerator
          topic={selectedTopic}
          courseId={normalizedCourseId}
          quizOnly={true}
          onQuizCreated={handleQuizCreated}
        />
      );
    }


    if (
      activeSection === "student-quiz"
    ) {
      if (!quizId) {
        return renderEmptyState({
          icon: "🎯",
          title:
            "هنوز آزمونی برای شرکت وجود ندارد",
          description:
            "ابتدا یک سرفصل را انتخاب کرده و آزمون چهارگزینه‌ای تولید کنید.",
          buttonText:
            "تولید آزمون",
          onClick:
            handleQuizGeneratorSection,
        });
      }

      return (
        <Quiz
          quizId={quizId}
          courseId={normalizedCourseId}
        />
      );
    }


    if (activeSection === "ai-stats") {
      return <AIStatsDashboard />;
    }

    return null;
  };


  return (
    <div
      className="app-shell"
      dir="rtl"
    >
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            آ
          </div>

          <div>
            <h2>آموزش‌یار</h2>

            <span>
              سامانه هوشمند آموزش
            </span>
          </div>
        </div>


        <div className="sidebar-course">
          <label htmlFor="sidebar-course-id">
            شناسه درس
          </label>

          <input
            id="sidebar-course-id"
            type="number"
            min="1"
            step="1"
            value={courseId}
            placeholder="مثلاً 1038"
            onChange={handleCourseIdChange}
          />

          {!hasValidCourseId && (
            <small className="input-error">
              شناسه درس باید عددی بزرگ‌تر از صفر باشد.
            </small>
          )}
        </div>


        <nav
          className="sidebar-menu"
          aria-label="منوی اصلی"
        >
          <button
            type="button"
            className={
              activeSection === "topics"
                ? "menu-item active"
                : "menu-item"
            }
            onClick={handleTopicsSection}
          >
            <span className="menu-icon">
              📚
            </span>

            <span>
              ثبت سرفصل دروس
            </span>
          </button>


          <button
            type="button"
            className={
              activeSection === "content"
                ? "menu-item active"
                : "menu-item"
            }
            onClick={handleContentSection}
          >
            <span className="menu-icon">
              📝
            </span>

            <span>
              تولید محتوای دروس
            </span>
          </button>


          <button
            type="button"
            className={
              activeSection ===
              "quiz-generator"
                ? "menu-item active"
                : "menu-item"
            }
            onClick={handleQuizGeneratorSection}
          >
            <span className="menu-icon">
              🧠
            </span>

            <span>
              تولید تست و کوییز هوشمند
            </span>
          </button>


          <button
            type="button"
            className={
              activeSection ===
              "student-quiz"
                ? "menu-item active"
                : "menu-item"
            }
            onClick={handleStudentQuizSection}
          >
            <span className="menu-icon">
              🎯
            </span>

            <span>
              شرکت در کوییز
            </span>
          </button>


          <button
            type="button"
            className={
              activeSection === "ai-stats"
                ? "menu-item active"
                : "menu-item"
            }
            onClick={handleAIStatsSection}
          >
            <span className="menu-icon">
              📊
            </span>

            <span>
              داشبورد هوش مصنوعی
            </span>
          </button>


          <a
            className="menu-item menu-item-link"
            href="/reports-page"
            title="تولید خروجی HTML، PowerPoint، PDF و Word"
          >
            <span className="menu-icon">
              📈
            </span>

            <span>
              استودیو گزارش‌ها (۴ فرمت)
            </span>
          </a>

          {canManageUsers && (
            <button
              type="button"
              className={
                activeSection === "user-management"
                  ? "menu-item active"
                  : "menu-item"
              }
              onClick={() => {
                setActiveSection("user-management");
                setAppMessage("");
              }}
            >
              <span className="menu-icon">
                🛡️
              </span>

              <span>
                مدیریت کاربران
              </span>
            </button>
          )}
        </nav>


        <div className="sidebar-footer">
          <div className="status-dot"></div>

          <span>
            سامانه فعال است
          </span>
        </div>
      </aside>


      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="breadcrumb">
              پنل مدیریت /{" "}
              {pageTitle.title}
            </p>

            <h1>{pageTitle.title}</h1>

            <p className="page-subtitle">
              {pageTitle.subtitle}
            </p>
          </div>


          <div className="user-box">
            <div className="user-avatar">
              {(authUser.full_name || "ا").trim().charAt(0)}
            </div>

            <div>
              <strong>
                {authUser.full_name}
              </strong>

              <span>
                {authUser.role_label || ROLE_LABELS_FA[authUser.role] || authUser.role}
              </span>
            </div>

            <button
              type="button"
              className="logout-button"
              onClick={handleLogout}
              title="خروج از حساب"
            >
              خروج
            </button>
          </div>
        </header>


        <section className="course-info-card">
          <div className="course-info-icon">
            🎓
          </div>

          <div className="course-info-details">
            <span>
              درس انتخاب‌شده
            </span>

            <strong>
              {hasValidCourseId
                ? `درس با شناسه ${normalizedCourseId}`
                : "شناسه درس وارد نشده است"}
            </strong>
          </div>


          {selectedTopic && (
            <div className="selected-topic-badge">
              <span>
                سرفصل انتخاب‌شده:
              </span>

              <strong>
                {selectedTopic.title ||
                  "بدون عنوان"}
              </strong>

              <small>
                شناسه واقعی:{" "}
                {selectedTopic.topic_id ??
                  selectedTopic.id ??
                  "-"}
              </small>
            </div>
          )}


          {quizId && (
            <div className="selected-quiz-badge">
              <span>
                شناسه آزمون:
              </span>

              <strong>{quizId}</strong>
            </div>
          )}
        </section>


        {appMessage && (
          <div
            className="app-message"
            role="status"
          >
            {appMessage}
          </div>
        )}


        <section className="page-content">
          {renderActivePage()}
        </section>
      </main>
    </div>
  );
}


export default App;