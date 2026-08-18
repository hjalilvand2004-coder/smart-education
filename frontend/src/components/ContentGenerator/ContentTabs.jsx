import React from "react";

const ContentTabs = ({ activeTab, setActiveTab, contentsCount = 0 }) => {
  return (
    <nav className="content-tabs">
      <button
        type="button"
        className={activeTab === "content" ? "content-tab active" : "content-tab"}
        onClick={() => setActiveTab("content")}
      >
        ✨ تولید محتوا
      </button>
      <button
        type="button"
        className={activeTab === "history" ? "content-tab active" : "content-tab"}
        onClick={() => setActiveTab("history")}
      >
        🗂 محتواهای قبلی
        <b>{contentsCount}</b>
      </button>
      <button
        type="button"
        className={activeTab === "quiz" ? "content-tab active" : "content-tab"}
        onClick={() => setActiveTab("quiz")}
      >
        🧠 ساخت آزمون
      </button>
    </nav>
  );
};

export default ContentTabs;