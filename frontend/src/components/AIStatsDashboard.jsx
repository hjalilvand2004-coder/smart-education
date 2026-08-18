import { useState, useEffect } from "react";
import api from "../api";
import "./AIStatsDashboard.css";

function AIStatsDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const response = await api.get("/ai-stats/summary?days=30");
        setStats(response.data);
        setError("");
      } catch (err) {
        console.error("Error loading AI stats:", err);
        setError("بارگیری آمار با خطا مواجه شد.");
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  // تابع کمکی برای نمایش تاریخ و ساعت
  const formatDateTime = (timestamp) => {
    if (!timestamp) return "-";
    const date = new Date(timestamp);
    const dateStr = date.toLocaleDateString("fa-IR");
    const timeStr = date.toLocaleTimeString("fa-IR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
    return `${dateStr} - ${timeStr}`;
  };

  if (loading) {
    return (
      <div className="ai-stats-loading">
        <span className="spinner"></span>
        <span>در حال دریافت آمار...</span>
      </div>
    );
  }

  if (error) {
    return <div className="ai-stats-error">{error}</div>;
  }

  if (!stats) {
    return <div className="ai-stats-empty">آماری برای نمایش وجود ندارد.</div>;
  }

  // محاسبه هزینه تقریبی (هر ۱۰۰۰ توکن = ۰.۰۰۲ دلار)
  const estimatedCost = ((stats.total.total_tokens || 0) / 1000) * 0.002;

  return (
    <div className="ai-stats-dashboard">
      <h2>📊 داشبورد هوش مصنوعی</h2>
      <p className="stats-period">۳۰ روز اخیر</p>

      {/* کارت‌های آماری */}
      <div className="stats-cards">
        <div className="stat-card">
          <div className="stat-icon">📨</div>
          <div className="stat-info">
            <span className="stat-label">تعداد کل درخواست‌ها</span>
            <strong className="stat-value">{stats.total.total_requests}</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🔢</div>
          <div className="stat-info">
            <span className="stat-label">تعداد توکن مصرفی</span>
            <strong className="stat-value">{stats.total.total_tokens.toLocaleString()}</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">❓</div>
          <div className="stat-info">
            <span className="stat-label">سوالات تولیدشده</span>
            <strong className="stat-value">{stats.total.total_questions_generated}</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">💰</div>
          <div className="stat-info">
            <span className="stat-label">هزینه تقریبی</span>
            <strong className="stat-value">${estimatedCost.toFixed(4)}</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">⏱️</div>
          <div className="stat-info">
            <span className="stat-label">میانگین زمان پاسخ</span>
            <strong className="stat-value">{stats.total.avg_duration_ms} ms</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📈</div>
          <div className="stat-info">
            <span className="stat-label">نرخ موفقیت</span>
            <strong className="stat-value">
              {stats.by_provider.length > 0
                ? Math.round(
                    (stats.by_provider[0].success_count / stats.by_provider[0].total_requests) * 100
                  )
                : 0}%
            </strong>
          </div>
        </div>
      </div>

      {/* جدول جزئیات درخواست‌ها */}
      <div className="stats-table-wrapper">
        <h3>📋 لیست درخواست‌های اخیر</h3>
        <div className="table-responsive">
          <table className="stats-table">
            <thead>
              <tr>
                <th>#</th>
                <th>نوع درخواست</th>
                <th>ارائه‌دهنده</th>
                <th>مدل</th>
                <th>تعداد توکن</th>
                <th>زمان پاسخ (ms)</th>
                <th>وضعیت</th>
                <th>تاریخ و زمان</th>  {/* ستون جدید با تاریخ و ساعت */}
              </tr>
            </thead>
            <tbody>
              {stats.recent_requests && stats.recent_requests.length > 0 ? (
                stats.recent_requests.map((req, index) => (
                  <tr key={req.id}>
                    <td>{index + 1}</td>
                    <td>
                      {req.request_type === "content_generation"
                        ? "تولید محتوا"
                        : req.request_type === "question_generation"
                        ? "تولید سوال"
                        : req.request_type}
                    </td>
                    <td>{req.provider}</td>
                    <td>{req.model}</td>
                    <td>{req.tokens_used.toLocaleString()}</td>
                    <td>{req.duration_ms}</td>
                    <td>
                      <span className={req.success ? "status-success" : "status-failed"}>
                        {req.success ? "✓ موفق" : "✗ ناموفق"}
                      </span>
                      {req.error_message && (
                        <span className="error-tooltip" title={req.error_message}>
                          ⚠️
                        </span>
                      )}
                    </td>
                    <td>{formatDateTime(req.timestamp)}</td>  {/* نمایش تاریخ و ساعت */}
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="empty-table">
                    هیچ درخواستی ثبت نشده است.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* خلاصه ارائه‌دهندگان */}
      <div className="stats-providers-summary">
        <h4>📊 خلاصه ارائه‌دهندگان</h4>
        <div className="provider-chips">
          {stats.by_provider.map((provider) => (
            <div key={provider.provider} className="provider-chip">
              <span className="chip-name">{provider.provider}</span>
              <span className="chip-requests">{provider.total_requests} درخواست</span>
              <span className="chip-success">✓ {provider.success_count}</span>
              <span className="chip-failed">✗ {provider.failure_count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default AIStatsDashboard;