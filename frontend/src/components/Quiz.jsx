import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import api, { getApiError } from "../api";
import "./Quiz.css";


const OPTION_KEYS = ["A", "B", "C", "D"];

const QUESTION_TYPES = {
  MULTIPLE_CHOICE: "multiple_choice",
  ESSAY: "essay",
};


function normalizeQuestionType(value) {
  const type = String(value || "")
    .trim()
    .toLowerCase();

  const aliases = {
    multiple_choice: QUESTION_TYPES.MULTIPLE_CHOICE,
    "multiple-choice": QUESTION_TYPES.MULTIPLE_CHOICE,
    mcq: QUESTION_TYPES.MULTIPLE_CHOICE,
    test: QUESTION_TYPES.MULTIPLE_CHOICE,
    four_choice: QUESTION_TYPES.MULTIPLE_CHOICE,
    "چهارگزینه‌ای": QUESTION_TYPES.MULTIPLE_CHOICE,
    "چهارگزینه ای": QUESTION_TYPES.MULTIPLE_CHOICE,

    essay: QUESTION_TYPES.ESSAY,
    descriptive: QUESTION_TYPES.ESSAY,
    written: QUESTION_TYPES.ESSAY,
    "تشریحی": QUESTION_TYPES.ESSAY,
  };

  return (
    aliases[type] ||
    QUESTION_TYPES.MULTIPLE_CHOICE
  );
}


function Quiz({ quizId, onSubmitted }) {
  const [quiz, setQuiz] = useState(null);
  const [studentName, setStudentName] = useState("");
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);

  const questionRefs = useRef({});


  const normalizeQuiz = useCallback((data) => {
    if (!data || typeof data !== "object") {
      return null;
    }

    const rawQuestions = Array.isArray(data.questions)
      ? data.questions
      : Array.isArray(data.items)
        ? data.items
        : [];

    const normalizedQuestions = rawQuestions.map(
      (question, index) => {
        const questionType = normalizeQuestionType(
          question.question_type ||
          question.type ||
          question.questionType
        );

        return {
          ...question,

          id:
            question.id ??
            question.question_id ??
            question.questionId ??
            index + 1,

          question_type: questionType,

          question_text:
            question.question_text ||
            question.text ||
            question.question ||
            `سؤال ${index + 1}`,

          option_a:
            question.option_a ??
            question.options?.A ??
            question.options?.a ??
            question.choices?.A ??
            question.choices?.a ??
            "",

          option_b:
            question.option_b ??
            question.options?.B ??
            question.options?.b ??
            question.choices?.B ??
            question.choices?.b ??
            "",

          option_c:
            question.option_c ??
            question.options?.C ??
            question.options?.c ??
            question.choices?.C ??
            question.choices?.c ??
            "",

          option_d:
            question.option_d ??
            question.options?.D ??
            question.options?.d ??
            question.choices?.D ??
            question.choices?.d ??
            "",

          model_answer:
            question.model_answer ||
            question.sample_answer ||
            question.answer ||
            "",

          explanation:
            question.explanation ||
            question.feedback ||
            "",
        };
      }
    );

    return {
      ...data,

      id: data.id ?? data.quiz_id ?? quizId,

      title:
        data.title ||
        data.name ||
        "آزمون آنلاین",

      description:
        data.description ||
        data.instructions ||
        "",

      questions: normalizedQuestions,
    };
  }, [quizId]);


  const loadQuiz = useCallback(async () => {
    const numericQuizId = Number(quizId);

    if (!Number.isInteger(numericQuizId) || numericQuizId <= 0) {
      setQuiz(null);
      setError("شناسه آزمون معتبر نیست.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");
      setQuiz(null);
      setResult(null);
      setAnswers({});
      setShowConfirm(false);
      setStudentName("");
      questionRefs.current = {};

      const response = await api.get(
        `/quizzes/${numericQuizId}`
      );

      const normalized = normalizeQuiz(
        response.data?.quiz || response.data
      );

      if (!normalized) {
        throw new Error("اطلاعات آزمون دریافت نشد.");
      }

      setQuiz(normalized);
    } catch (requestError) {
      setError(String(getApiError(requestError)));
    } finally {
      setLoading(false);
    }
  }, [quizId, normalizeQuiz]);


  useEffect(() => {
    loadQuiz();
  }, [loadQuiz]);


  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setShowConfirm(false);
      }
    };

    window.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("keydown", handleEscape);
    };
  }, []);


  const questions = useMemo(() => {
    return Array.isArray(quiz?.questions)
      ? quiz.questions
      : [];
  }, [quiz]);


  const multipleChoiceQuestions = useMemo(() => {
    return questions.filter(
      (question) =>
        question.question_type ===
        QUESTION_TYPES.MULTIPLE_CHOICE
    );
  }, [questions]);


  const essayQuestions = useMemo(() => {
    return questions.filter(
      (question) =>
        question.question_type ===
        QUESTION_TYPES.ESSAY
    );
  }, [questions]);


  const answeredCount = useMemo(() => {
    return questions.filter((question) => {
      const answer = answers[question.id];

      return typeof answer === "string" && answer.trim();
    }).length;
  }, [answers, questions]);


  const unansweredQuestions = useMemo(() => {
    return questions.filter((question) => {
      const answer = answers[question.id];

      return !(
        typeof answer === "string" &&
        answer.trim()
      );
    });
  }, [answers, questions]);


  const progress = useMemo(() => {
    if (!questions.length) {
      return 0;
    }

    return Math.round(
      (answeredCount / questions.length) * 100
    );
  }, [answeredCount, questions.length]);


  const setAnswer = useCallback((
    questionId,
    value
  ) => {
    if (result || submitting) {
      return;
    }

    setAnswers((previous) => ({
      ...previous,
      [questionId]: value,
    }));

    setError("");
  }, [result, submitting]);


  const selectAnswer = useCallback((
    questionId,
    option
  ) => {
    setAnswer(questionId, option);
  }, [setAnswer]);


  const writeEssayAnswer = useCallback((
    questionId,
    value
  ) => {
    setAnswer(questionId, value);
  }, [setAnswer]);


  const getOptions = useCallback((question) => {
    return OPTION_KEYS.map((key) => ({
      key,
      text: String(
        question[`option_${key.toLowerCase()}`] || ""
      ).trim(),
    })).filter((option) => option.text);
  }, []);


  const focusQuestion = useCallback((questionId) => {
    const element = questionRefs.current[questionId];

    if (!element) {
      return;
    }

    element.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    const focusableElement = element.querySelector(
      'input:not([disabled]), textarea:not([disabled])'
    );

    if (focusableElement) {
      window.setTimeout(() => {
        focusableElement.focus();
      }, 500);
    }
  }, []);


  const validateForm = useCallback(() => {
    const normalizedName = studentName.trim();

    if (!normalizedName) {
      setError("نام و نام خانوادگی دانشجو را وارد کنید.");
      return false;
    }

    if (normalizedName.length < 2) {
      setError(
        "نام دانشجو باید حداقل دو حرف داشته باشد."
      );
      return false;
    }

    if (!questions.length) {
      setError(
        "این آزمون فاقد سؤال است و قابل ارسال نیست."
      );
      return false;
    }

    const invalidMultipleChoiceQuestion =
      multipleChoiceQuestions.find((question) => {
        return getOptions(question).length !== 4;
      });

    if (invalidMultipleChoiceQuestion) {
      setError(
        "یکی از سؤال‌های چهارگزینه‌ای آزمون دارای گزینه‌های ناقص است."
      );

      focusQuestion(invalidMultipleChoiceQuestion.id);
      return false;
    }

    if (unansweredQuestions.length > 0) {
      const firstUnansweredQuestion =
        unansweredQuestions[0];

      setError(
        `لطفاً به همه سؤالات پاسخ دهید. تعداد سؤالات بدون پاسخ: ${unansweredQuestions.length}`
      );

      focusQuestion(firstUnansweredQuestion.id);
      return false;
    }

    return true;
  }, [
    studentName,
    questions,
    multipleChoiceQuestions,
    unansweredQuestions,
    getOptions,
    focusQuestion,
  ]);


  const requestSubmit = useCallback(() => {
    if (!validateForm()) {
      return;
    }

    setShowConfirm(true);
  }, [validateForm]);


  const createAnswerPayload = useCallback(() => {
    return questions.map((question) => {
      const answerValue = String(
        answers[question.id] || ""
      ).trim();

      if (
        question.question_type ===
        QUESTION_TYPES.ESSAY
      ) {
        return {
          question_id: Number(question.id),
          selected_option: null,
          essay_answer: answerValue,
        };
      }

      return {
        question_id: Number(question.id),
        selected_option: answerValue.toUpperCase(),
        essay_answer: null,
      };
    });
  }, [answers, questions]);


  const submitQuiz = useCallback(async () => {
    if (!validateForm()) {
      setShowConfirm(false);
      return;
    }

    try {
      setSubmitting(true);
      setError("");
      setShowConfirm(false);

      const payload = {
        student_name: studentName.trim(),
        answers: createAnswerPayload(),
      };

      const response = await api.post(
        `/quizzes/${Number(quizId)}/submit`,
        payload
      );

      const submittedResult =
        response.data?.result ||
        response.data;

      setResult(submittedResult);

      if (typeof onSubmitted === "function") {
        onSubmitted(submittedResult);
      }

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    } catch (requestError) {
      setError(String(getApiError(requestError)));
    } finally {
      setSubmitting(false);
    }
  }, [
    validateForm,
    studentName,
    createAnswerPayload,
    quizId,
    onSubmitted,
  ]);


  const resetQuiz = useCallback(() => {
    setAnswers({});
    setResult(null);
    setError("");
    setShowConfirm(false);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }, []);


  const getResultValue = useCallback((
    keys,
    fallback = "-"
  ) => {
    if (!result) {
      return fallback;
    }

    for (const key of keys) {
      if (
        result[key] !== undefined &&
        result[key] !== null
      ) {
        return result[key];
      }
    }

    return fallback;
  }, [result]);


  const score = getResultValue(
    ["score", "final_score", "percentage"],
    0
  );

  const correctAnswers = getResultValue(
    ["correct_answers", "correct_count"],
    0
  );

  const totalQuestions = getResultValue(
    ["total_questions", "question_count"],
    questions.length
  );

  const multipleChoiceCount = getResultValue(
    ["multiple_choice_questions"],
    multipleChoiceQuestions.length
  );

  const essayCount = getResultValue(
    ["essay_questions"],
    essayQuestions.length
  );

  const incorrectAnswers = getResultValue(
    ["incorrect_answers", "wrong_answers"],
    Math.max(
      Number(multipleChoiceCount) -
        Number(correctAnswers),
      0
    )
  );

  const unansweredAnswers = getResultValue(
    ["unanswered", "unanswered_questions"],
    0
  );

  const resultStatus = String(
    getResultValue(["status"], "")
  ).toLowerCase();

  const hasPendingEssayReview =
    Number(essayCount) > 0 ||
    resultStatus === "pending_manual_review";


  if (loading) {
    return (
      <section className="card quiz-card quiz-loading-card">
        <div className="quiz-loading">
          <span className="quiz-spinner" />
          <strong>در حال دریافت آزمون...</strong>
          <small>لطفاً چند لحظه صبر کنید.</small>
        </div>
      </section>
    );
  }


  if (error && !quiz) {
    return (
      <section className="card quiz-card">
        <div className="quiz-state error-state">
          <span className="quiz-state-icon">⚠️</span>
          <h3>دریافت آزمون ناموفق بود</h3>
          <p>{error}</p>

          <button
            type="button"
            className="quiz-secondary-button"
            onClick={loadQuiz}
          >
            تلاش مجدد
          </button>
        </div>
      </section>
    );
  }


  if (!quiz) {
    return (
      <section className="card quiz-card">
        <div className="quiz-state">
          <span className="quiz-state-icon">📝</span>
          <h3>آزمونی برای نمایش وجود ندارد</h3>
        </div>
      </section>
    );
  }


  if (!questions.length) {
    return (
      <section className="card quiz-card">
        <div className="quiz-state">
          <span className="quiz-state-icon">📭</span>
          <h3>این آزمون هنوز سؤالی ندارد</h3>
          <p>ابتدا سؤال‌های آزمون را ایجاد یا ذخیره کنید.</p>
        </div>
      </section>
    );
  }


  return (
    <section
      className="card quiz-card"
      dir="rtl"
    >
      <header className="quiz-header">
        <div className="quiz-header-icon">🧠</div>

        <div className="quiz-header-content">
          <span className="quiz-kicker">
            {essayQuestions.length > 0 &&
            multipleChoiceQuestions.length > 0
              ? "آزمون ترکیبی"
              : essayQuestions.length > 0
                ? "آزمون تشریحی"
                : "آزمون چهارگزینه‌ای"}
          </span>

          <h2>{quiz.title || "آزمون آنلاین"}</h2>

          {quiz.description && (
            <p>{quiz.description}</p>
          )}
        </div>

        <div className="quiz-header-badge">
          <strong>{questions.length}</strong>
          <span>سؤال</span>
        </div>
      </header>


      {!result && (
        <div className="quiz-progress-section">
          <div className="quiz-progress-top">
            <span>میزان پیشرفت پاسخ‌گویی</span>

            <strong>
              {answeredCount} از {questions.length}
            </strong>
          </div>

          <div
            className="quiz-progress-bar"
            aria-label={`پیشرفت ${progress} درصد`}
          >
            <span
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="quiz-progress-footer">
            <span>
              {progress === 100
                ? "همه سؤالات پاسخ داده شده است."
                : "به همه سؤالات پاسخ دهید."}
            </span>

            <strong>{progress}%</strong>
          </div>
        </div>
      )}


      <div className="quiz-body">
        {!result && (
          <div className="student-info-box">
            <div className="student-info-icon">👤</div>

            <div className="student-info-content">
              <label htmlFor="student-name">
                نام و نام خانوادگی دانشجو
              </label>

              <input
                id="student-name"
                type="text"
                value={studentName}
                onChange={(event) => {
                  setStudentName(event.target.value);
                  setError("");
                }}
                placeholder="مثلاً: علی رضایی"
                autoComplete="name"
                maxLength={100}
                disabled={submitting}
              />

              <small>
                نام واردشده همراه نتیجه آزمون ثبت می‌شود.
              </small>
            </div>
          </div>
        )}


        {error && (
          <div
            className="quiz-alert error"
            role="alert"
          >
            <span>!</span>
            <p>{error}</p>

            <button
              type="button"
              onClick={() => setError("")}
              aria-label="بستن پیام"
            >
              ×
            </button>
          </div>
        )}


        {!result && (
          <div className="questions-list">
            {questions.map((question, index) => {
              const isEssay =
                question.question_type ===
                QUESTION_TYPES.ESSAY;

              const options = isEssay
                ? []
                : getOptions(question);

              const selectedAnswer =
                answers[question.id] || "";

              const isAnswered = Boolean(
                String(selectedAnswer).trim()
              );

              return (
                <article
                  ref={(element) => {
                    if (element) {
                      questionRefs.current[question.id] =
                        element;
                    }
                  }}
                  className={`question-card ${
                    isAnswered
                      ? "question-answered"
                      : ""
                  } ${
                    isEssay
                      ? "essay-question-card"
                      : "multiple-choice-question-card"
                  }`}
                  key={question.id}
                >
                  <div className="question-card-header">
                    <span className="question-number">
                      {index + 1}
                    </span>

                    <div className="question-title">
                      <div className="question-title-top">
                        <h3>{question.question_text}</h3>

                        <span
                          className={`question-type-badge ${
                            isEssay
                              ? "essay"
                              : "multiple-choice"
                          }`}
                        >
                          {isEssay
                            ? "تشریحی"
                            : "چهارگزینه‌ای"}
                        </span>
                      </div>

                      <span>
                        {isAnswered
                          ? "پاسخ ثبت شده"
                          : "بدون پاسخ"}
                      </span>
                    </div>
                  </div>

                  {isEssay ? (
                    <div className="essay-answer-section">
                      <label
                        htmlFor={`essay-answer-${question.id}`}
                      >
                        پاسخ تشریحی خود را بنویسید:
                      </label>

                      <textarea
                        id={`essay-answer-${question.id}`}
                        value={selectedAnswer}
                        onChange={(event) =>
                          writeEssayAnswer(
                            question.id,
                            event.target.value
                          )
                        }
                        placeholder="پاسخ خود را با توضیح کافی وارد کنید..."
                        rows={7}
                        maxLength={5000}
                        disabled={submitting}
                      />

                      <div className="essay-answer-footer">
                        <small>
                          پاسخ شما پس از ثبت آزمون برای بررسی
                          ذخیره می‌شود.
                        </small>

                        <small>
                          {selectedAnswer.length} / 5000
                        </small>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="options-list">
                        {options.map((option) => (
                          <label
                            className={`quiz-option ${
                              selectedAnswer === option.key
                                ? "selected"
                                : ""
                            }`}
                            key={option.key}
                          >
                            <input
                              type="radio"
                              name={`question-${question.id}`}
                              value={option.key}
                              checked={
                                selectedAnswer === option.key
                              }
                              onChange={() =>
                                selectAnswer(
                                  question.id,
                                  option.key
                                )
                              }
                              disabled={submitting}
                            />

                            <span className="option-letter">
                              {option.key}
                            </span>

                            <span className="option-text">
                              {option.text}
                            </span>

                            <span className="option-check">
                              ✓
                            </span>
                          </label>
                        ))}
                      </div>

                      {options.length !== 4 && (
                        <div className="question-warning">
                          گزینه‌های این سؤال کامل نیستند. لطفاً
                          با مدیر سامانه تماس بگیرید.
                        </div>
                      )}
                    </>
                  )}
                </article>
              );
            })}
          </div>
        )}


        {!result && (
          <div className="quiz-submit-section">
            <div className="submit-hint">
              <span>💡</span>

              <p>
                {essayQuestions.length > 0
                  ? "پاسخ‌های تشریحی پس از ثبت برای بررسی ذخیره می‌شوند. قبل از ثبت، پاسخ همه سؤالات را بررسی کنید."
                  : "قبل از ثبت آزمون، پاسخ همه سؤالات را بررسی کنید."}
              </p>
            </div>

            <button
              type="button"
              className="quiz-submit-button"
              onClick={requestSubmit}
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <span className="quiz-button-spinner" />
                  در حال ثبت پاسخ‌ها...
                </>
              ) : (
                <>
                  <span>✅</span>
                  ثبت نهایی آزمون
                </>
              )}
            </button>
          </div>
        )}


        {result && (
          <section className="quiz-result-section">
            <div className="result-success-icon">✓</div>

            <h2>آزمون با موفقیت ثبت شد</h2>

            <p className="result-student-name">
              دانشجو:{" "}
              <strong>
                {getResultValue(
                  ["student_name"],
                  studentName
                )}
              </strong>
            </p>

            {Number(multipleChoiceCount) > 0 && (
              <div className="score-card">
                <span>
                  {hasPendingEssayReview
                    ? "نمره موقت بخش چهارگزینه‌ای"
                    : "نمره نهایی"}
                </span>

                <strong>{score}</strong>
                <small>از ۱۰۰</small>
              </div>
            )}

            <div className="result-stat-grid">
              {Number(multipleChoiceCount) > 0 && (
                <>
                  <div className="result-stat correct">
                    <span>✓</span>
                    <strong>{correctAnswers}</strong>
                    <small>پاسخ صحیح</small>
                  </div>

                  <div className="result-stat incorrect">
                    <span>×</span>
                    <strong>{incorrectAnswers}</strong>
                    <small>پاسخ نادرست</small>
                  </div>
                </>
              )}

              <div className="result-stat unanswered">
                <span>−</span>
                <strong>{unansweredAnswers}</strong>
                <small>بدون پاسخ</small>
              </div>

              <div className="result-stat total">
                <span>#</span>
                <strong>{totalQuestions}</strong>
                <small>کل سؤالات</small>
              </div>

              {Number(essayCount) > 0 && (
                <div className="result-stat essay">
                  <span>✎</span>
                  <strong>{essayCount}</strong>
                  <small>سؤال تشریحی</small>
                </div>
              )}
            </div>

            {hasPendingEssayReview && (
              <div className="result-message result-pending-review">
                پاسخ‌های تشریحی ثبت شدند و برای بررسی دستی یا
                ارزیابی هوش مصنوعی در انتظار ارزیابی هستند.
              </div>
            )}

            {result.message && (
              <div className="result-message">
                {result.message}
              </div>
            )}

            <button
              type="button"
              className="quiz-secondary-button"
              onClick={resetQuiz}
            >
              شرکت مجدد در آزمون
            </button>
          </section>
        )}
      </div>


      {showConfirm && (
        <div
          className="quiz-modal-backdrop"
          role="presentation"
          onClick={() => {
            if (!submitting) {
              setShowConfirm(false);
            }
          }}
        >
          <div
            className="quiz-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="quiz-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="confirm-icon">⚠️</div>

            <h3 id="quiz-confirm-title">
              ثبت نهایی آزمون
            </h3>

            <p>
              پس از ثبت آزمون امکان تغییر پاسخ‌ها وجود ندارد.
              آیا از ثبت پاسخ‌ها مطمئن هستید؟
            </p>

            {essayQuestions.length > 0 && (
              <div className="confirm-essay-note">
                پاسخ‌های تشریحی برای بررسی و ارزیابی ذخیره خواهند
                شد.
              </div>
            )}

            <div className="confirm-actions">
              <button
                type="button"
                className="quiz-cancel-button"
                onClick={() => setShowConfirm(false)}
                disabled={submitting}
              >
                بازگشت
              </button>

              <button
                type="button"
                className="quiz-confirm-button"
                onClick={submitQuiz}
                disabled={submitting}
              >
                {submitting
                  ? "در حال ثبت..."
                  : "بله، ثبت نهایی"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}


export default Quiz;