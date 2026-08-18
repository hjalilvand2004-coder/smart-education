import React from "react";

const MIN_QUESTION_COUNT = 1;
const MAX_QUESTION_COUNT = 100;

const QuizGenerationPanel = ({
  selectedContent,
  questionCount,
  setQuestionCount,
  questionType,
  setQuestionType,
  level,
  setLevel,
  quizLoading,
  createQuiz,
  safeTopicId,
}) => {
  return (
    <div className="quiz-generation-panel">
      <div className="quiz-intro">
        <div className="quiz-intro-icon">🧠</div>
        <div>
          <h3>ساخت آزمون هوشمند</h3>
          <p>آزمون بر اساس محتوای انتخاب‌شده تولید می‌شود.</p>
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
            <strong>{selectedContent.title || "محتوای آموزشی انتخاب‌شده"}</strong>
          </div>

          <div className="quiz-options-grid">
            <div>
              <label htmlFor="question-type">نوع آزمون</label>
              <select
                id="question-type"
                className="content-input"
                value={questionType}
                onChange={(e) => {
                  setQuestionType(e.target.value);
                }}
                disabled={quizLoading}
              >
                <option value="multiple_choice">چهارگزینه‌ای</option>
                <option value="essay">تشریحی</option>
              </select>
            </div>

            <div>
              <label htmlFor="question-count">تعداد سؤالات</label>
              <input
                id="question-count"
                className="content-input"
                type="number"
                min={MIN_QUESTION_COUNT}
                max={MAX_QUESTION_COUNT}
                value={questionCount}
                onChange={(e) => {
                  setQuestionCount(e.target.value);
                }}
                disabled={quizLoading}
              />
            </div>

            <div>
              <label htmlFor="quiz-level">سطح آزمون</label>
              <select
                id="quiz-level"
                className="content-input"
                value={level}
                onChange={(e) => {
                  setLevel(e.target.value);
                }}
                disabled={quizLoading}
              >
                <option value="beginner">مقدماتی</option>
                <option value="intermediate">متوسط</option>
                <option value="advanced">پیشرفته</option>
              </select>
            </div>
          </div>

          <div className="quiz-type-description">
            {questionType === "essay" ? (
              <p>در آزمون تشریحی، پاسخ دانشجو به‌صورت متنی ثبت می‌شود.</p>
            ) : (
              <p>در آزمون چهارگزینه‌ای، هر سؤال دارای چهار گزینه خواهد بود.</p>
            )}
          </div>

          <button
            type="button"
            className="quiz-action"
            onClick={createQuiz}
            disabled={quizLoading || !safeTopicId || !selectedContent}
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
  );
};

export default QuizGenerationPanel;