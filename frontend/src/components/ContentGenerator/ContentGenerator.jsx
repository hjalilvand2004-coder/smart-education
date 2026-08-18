import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";

// فایل‌های کمکی - مسیرهای اصلاح‌شده
import {
  getContentBody,
  getExportHtml,
  downloadFile,
  safeFileName,
  exportPowerPointFile,
} from "../ContentExporter"; // ← src/components/ContentExporter.js

import { useContentGeneration } from "../hooks/useContentGeneration"; // ← src/components/hooks/useContentGeneration.js

import api, { getApiError } from "../../api"; // ← src/api.js

// کامپوننت‌های هم‌پوشه (همگی در همین پوشه)
import ContentHeader from "./ContentHeader";
import ContentTabs from "./ContentTabs";
import ContentGenerationPanel from "./ContentGenerationPanel";
import ContentHistoryPanel from "./ContentHistoryPanel";
import QuizGenerationPanel from "./QuizGenerationPanel";
import GeneratedContentDisplay from "./GeneratedContentDisplay";
import ExportToolbar from "./ExportToolbar";

// استایل اصلی (در پوشه والد components قرار دارد)
import "../ContentGenerator.css";

// =========================================================
// توابع کمکی
// =========================================================
const toPositiveInteger = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  if (!Number.isInteger(number) || number <= 0) return null;
  return number;
};

const getSafeTopicId = (topic) => {
  if (!topic || typeof topic !== "object") return null;
  const possibleIds = [topic.id, topic.topic_id, topic.topicId, topic.real_topic_id];
  for (const value of possibleIds) {
    const validId = toPositiveInteger(value);
    if (validId) return validId;
  }
  return null;
};

const getContentId = (content) => {
  if (!content || typeof content !== "object") return null;
  return toPositiveInteger(content.id ?? content.content_id);
};

const normalizeQuizDifficulty = (value) => {
  const map = { beginner: "easy", intermediate: "medium", advanced: "hard", easy: "easy", medium: "medium", hard: "hard" };
  return map[value] || "medium";
};

const MIN_QUESTION_COUNT = 1;
const MAX_QUESTION_COUNT = 100;
const DEFAULT_LANGUAGE = "fa";

// =========================================================
// کامپوننت اصلی
// =========================================================
function ContentGenerator({ topic, courseId, onQuizCreated, quizOnly = false }) {
  // -------- stateهای محلی ----------
  const [contents, setContents] = useState([]);
  const [selectedContent, setSelectedContent] = useState(null);
  const [loadingContents, setLoadingContents] = useState(false);
  const [activeTab, setActiveTab] = useState(quizOnly ? "quiz" : "content");

  const [questionCount, setQuestionCount] = useState(5);
  const [questionType, setQuestionType] = useState("multiple_choice");
  const [quizLoading, setQuizLoading] = useState(false);

  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("info");

  const loadRequestIdRef = useRef(0);
  const quizLockRef = useRef(false);

  const safeTopicId = useMemo(() => getSafeTopicId(topic), [topic]);
  const safeCourseId = useMemo(() => toPositiveInteger(courseId), [courseId]);

  // -------- هوک تولید محتوا ----------
  const {
    generating: generatingContent,
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
    generationMode,
    setGenerationMode,
    generateContent,
  } = useContentGeneration({
    safeTopicId,
    onSuccess: (generated) => {
      setSelectedContent(generated);
      setContents((prev) => {
        const id = getContentId(generated);
        const filtered = id ? prev.filter((item) => String(getContentId(item)) !== String(id)) : prev;
        return [generated, ...filtered];
      });
      setActiveTab("content");
      showMessage("محتوای آموزشی با موفقیت تولید شد.", "success");
    },
    onError: (err) => showMessage(err, "error"),
  });

  // -------- تابع نمایش پیام ----------
  const showMessage = useCallback((text, type = "info") => {
    setMessage(text || "");
    setMessageType(type);
  }, []);

  // -------- بارگذاری محتواهای قبلی ----------
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
      const response = await api.get(`/content/topic/${safeTopicId}`);
      if (requestId !== loadRequestIdRef.current) return;
      const data = response.data;
      const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : Array.isArray(data?.contents) ? data.contents : [];
      setContents(items);
      setSelectedContent((prev) => {
        if (!items.length) return null;
        const prevId = getContentId(prev);
        if (prevId) {
          const found = items.find((item) => String(getContentId(item)) === String(prevId));
          if (found) return found;
        }
        return items[0];
      });
    } catch (error) {
      if (requestId !== loadRequestIdRef.current) return;
      showMessage(getApiError(error) || "خطا در دریافت محتواها", "error");
    } finally {
      if (requestId === loadRequestIdRef.current) setLoadingContents(false);
    }
  }, [safeTopicId, showMessage]);

  useEffect(() => {
    loadContents();
  }, [loadContents]);

  // -------- تولید آزمون ----------
  const createQuiz = useCallback(async () => {
    if (quizLockRef.current) return;
    if (!safeTopicId) { showMessage("سرفصل معتبر انتخاب نشده است.", "error"); return; }
    const contentId = getContentId(selectedContent);
    if (!contentId) { showMessage("ابتدا یک محتوای آموزشی تولید یا انتخاب کنید.", "error"); return; }
    const count = Number(questionCount);
    if (!Number.isInteger(count) || count < MIN_QUESTION_COUNT || count > MAX_QUESTION_COUNT) {
      showMessage(`تعداد سؤالات باید بین ${MIN_QUESTION_COUNT} تا ${MAX_QUESTION_COUNT} باشد.`, "error");
      return;
    }
    const normalizedQuestionType = questionType === "essay" ? "essay" : "multiple_choice";
    const normalizedDifficulty = normalizeQuizDifficulty(level);

    quizLockRef.current = true;
    setQuizLoading(true);
    try {
      const payload = {
        topic_id: safeTopicId,
        content_id: contentId,
        number_of_questions: count,
        question_type: normalizedQuestionType,
        difficulty: normalizedDifficulty,
        language: DEFAULT_LANGUAGE,
      };
      if (safeCourseId) payload.course_id = safeCourseId;

      const response = await api.post("/quizzes/generate", payload);
      const quiz = response.data?.quiz || response.data?.data || response.data;
      const quizId = toPositiveInteger(quiz?.id ?? quiz?.quiz_id ?? response.data?.quiz_id);
      if (!quizId) throw new Error("شناسه آزمون دریافت نشد.");
      showMessage("آزمون با موفقیت ساخته شد.", "success");
      if (typeof onQuizCreated === "function") onQuizCreated(quizId);
    } catch (error) {
      showMessage(getApiError(error), "error");
    } finally {
      quizLockRef.current = false;
      setQuizLoading(false);
    }
  }, [safeTopicId, selectedContent, questionCount, questionType, level, safeCourseId, onQuizCreated, showMessage]);

  // -------- توابع خروجی ----------
  const exportHtml = useCallback(() => {
    if (!selectedContent) { showMessage("ابتدا یک محتوا را انتخاب کنید.", "error"); return; }
    const html = getExportHtml({ topic, content: selectedContent, topicId: safeTopicId });
    downloadFile(html, `${safeFileName(selectedContent.title || "educational-content")}.html`, "text/html;charset=utf-8");
    showMessage("فایل HTML با موفقیت دریافت شد.", "success");
  }, [selectedContent, topic, safeTopicId, showMessage]);

  const exportWord = useCallback(() => {
    if (!selectedContent) { showMessage("ابتدا یک محتوا را انتخاب کنید.", "error"); return; }
    const html = getExportHtml({ topic, content: selectedContent, topicId: safeTopicId });
    downloadFile(html, `${safeFileName(selectedContent.title || "educational-content")}.doc`, "application/msword;charset=utf-8");
    showMessage("فایل Word با موفقیت ایجاد شد.", "success");
  }, [selectedContent, topic, safeTopicId, showMessage]);

  const [pptLoading, setPptLoading] = useState(false);
  const exportPowerPoint = useCallback(async () => {
    if (!selectedContent) { showMessage("ابتدا یک محتوا را انتخاب کنید.", "error"); return; }
    if (pptLoading) return;
    try {
      setPptLoading(true);
      await exportPowerPointFile({ topic, content: selectedContent, topicId: safeTopicId });
      showMessage("فایل PowerPoint با موفقیت ایجاد شد.", "success");
    } catch (error) {
      showMessage("ساخت فایل PowerPoint انجام نشد.", "error");
    } finally {
      setPptLoading(false);
    }
  }, [selectedContent, topic, safeTopicId, pptLoading, showMessage]);

  const copyContent = useCallback(async () => {
    if (!selectedContent) { showMessage("محتوایی برای کپی وجود ندارد.", "error"); return; }
    try {
      const text = String(getContentBody(selectedContent) || "");
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(text);
      } else {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.left = "-9999px";
        area.style.top = "0";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.focus();
        area.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(area);
        if (!copied) throw new Error("Copy failed");
      }
      showMessage("متن محتوا کپی شد.", "success");
    } catch (error) {
      showMessage("کپی محتوا انجام نشد.", "error");
    }
  }, [selectedContent, showMessage]);

  const printContent = useCallback(() => {
    if (!selectedContent) { showMessage("ابتدا یک محتوا را انتخاب کنید.", "error"); return; }
    const printWindow = window.open("", "_blank", "width=1100,height=850");
    if (!printWindow) { showMessage("مرورگر اجازه بازشدن پنجره چاپ را نداد.", "error"); return; }
    const html = getExportHtml({ topic, content: selectedContent, topicId: safeTopicId });
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.onload = () => { printWindow.focus(); printWindow.print(); };
  }, [selectedContent, topic, safeTopicId, showMessage]);

  // -------- رندر ----------
  if (!topic) {
    return (
      <section className="card content-generator-card">
        <div className="content-empty">
          <span className="empty-icon">📚</span>
          <strong>سرفصلی انتخاب نشده است</strong>
          <small>برای ادامه ابتدا یک سرفصل انتخاب کنید.</small>
        </div>
      </section>
    );
  }

  return (
    <section className="card content-generator-card" dir="rtl">
      <ContentHeader quizOnly={quizOnly} />

      <div className="content-topic-banner">
        <div className="topic-banner-icon">📖</div>
        <div className="topic-banner-text">
          <span>سرفصل انتخاب‌شده</span>
          <h3>{topic.title || "سرفصل بدون عنوان"}</h3>
          <p>{topic.description || "برای این سرفصل توضیحی ثبت نشده است."}</p>
        </div>
        <div className="topic-meta">
          <div>
            <span>شناسه ارسالی به Backend</span>
            <strong>{safeTopicId || "-"}</strong>
          </div>
          <div>
            <span>زمان جلسه</span>
            <strong>{topic.session_minute || 0} دقیقه</strong>
          </div>
        </div>
      </div>

      {!quizOnly && (
        <ContentTabs
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          contentsCount={contents.length}
        />
      )}

      {!quizOnly && activeTab === "content" && (
        <ContentGenerationPanel
          generationMode={generationMode}
          setGenerationMode={setGenerationMode}
          provider={provider}
          setProvider={setProvider}
          model={model}
          setModel={setModel}
          level={level}
          setLevel={setLevel}
          contentType={contentType}
          setContentType={setContentType}
          customText={customText}
          setCustomText={setCustomText}
          manualContent={manualContent}
          setManualContent={setManualContent}
          generating={generatingContent}
          generateContent={generateContent}
          loadingContents={loadingContents}
          safeTopicId={safeTopicId}
        />
      )}

      {!quizOnly && activeTab === "history" && (
        <ContentHistoryPanel
          contents={contents}
          selectedContent={selectedContent}
          loading={loadingContents}
          onSelectContent={(content) => {
            setSelectedContent(content);
            setActiveTab("content");
          }}
        />
      )}

      {(quizOnly || activeTab === "quiz") && (
        <QuizGenerationPanel
          selectedContent={selectedContent}
          questionCount={questionCount}
          setQuestionCount={setQuestionCount}
          questionType={questionType}
          setQuestionType={setQuestionType}
          level={level}
          setLevel={setLevel}
          quizLoading={quizLoading}
          createQuiz={createQuiz}
          safeTopicId={safeTopicId}
        />
      )}

      {selectedContent && (
        <section className="generated-content-section">
          <GeneratedContentDisplay
            content={selectedContent}
            onCopy={copyContent}
            onPrint={printContent}
          />
          <ExportToolbar
            onExportHtml={exportHtml}
            onExportWord={exportWord}
            onExportPowerPoint={exportPowerPoint}
            pptLoading={pptLoading}
          />
        </section>
      )}

      {message && (
        <div className={`content-message ${messageType}`} role="alert">
          <span>{messageType === "success" ? "✓" : messageType === "error" ? "!" : "i"}</span>
          <p>{message}</p>
          <button type="button" className="message-close" onClick={() => setMessage("")} aria-label="بستن پیام">×</button>
        </div>
      )}
    </section>
  );
}

export default ContentGenerator;