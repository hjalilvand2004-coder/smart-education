import { useEffect, useState } from "react";
import api from "../api";

function AIStats() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        setError("");
        const response = await api.get("/ai-stats/summary?days=30");
        setStats(response.data);
      } catch (err) {
        setError("دریافت آمار استفاده از سرویس AI انجام نشد.");
        console.error("Error loading AI stats:", err);
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, []);

  if (loading) {
    return (
      <div className="ai-stats-card loading">
        <div className="ai-stats-spinner"></div>
        <span>در حال دریافت آمار...</span>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="ai-stats-card error">
        <span>⚠️</span>
        <span>{error || "آماری در دسترس نیست"}</span>
      </div>
    );
  }

  const { total, by_provider, by_model } = stats;

  return (
    <div className="ai-stats-card">
      <div className="ai-stats-header">
        <span className="ai-stats-icon">🤖</span>
        <div>
          <strong>آمار استفاده از AI</strong>
          <small>۳۰ روز اخیر</small>
        </div>
      </div>

      <div className="ai-stats-grid">
        <div className="ai-stat-item">
          <span className="ai-stat-value">{total.total_requests || 0}</span>
          <span className="ai-stat-label">تعداد درخواست‌ها</span>
        </div>
        <div className="ai-stat-item">
          <span className="ai-stat-value">{total.total_tokens || 0}</span>
          <span className="ai-stat-label">تعداد توکن‌ها</span>
        </div>
        <div className="ai-stat-item">
          <span className="ai-stat-value">{total.total_questions_generated || 0}</span>
          <span className="ai-stat-label">سوالات تولیدشده</span>
        </div>
        <div className="ai-stat-item">
          <span className="ai-stat-value">{total.avg_duration_ms || 0}ms</span>
          <span className="ai-stat-label">میانگین زمان</span>
        </div>
      </div>

      {by_provider && by_provider.length > 0 && (
        <div className="ai-stats-providers">
          <strong>ارائه‌دهندگان:</strong>
          <div className="ai-stats-provider-list">
            {by_provider.map((p) => (
              <span key={p.provider} className="ai-provider-tag">
                {p.provider}: {p.total_requests} درخواست
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default AIStats;