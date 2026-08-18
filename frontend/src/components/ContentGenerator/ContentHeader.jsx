import React from "react";

const ContentHeader = ({ quizOnly = false }) => {
  return (
    <header className="content-generator-header">
      <div>
        <span className="section-kicker">دستیار هوشمند آموزشی</span>
        <h2>
          {quizOnly ? "تولید آزمون هوشمند" : "تولید و مدیریت محتوای درسی"}
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
  );
};

export default ContentHeader;