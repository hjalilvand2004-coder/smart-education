import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { ProfessorActionsData } from '../api'

const TONE: Record<string, 'warn' | 'info' | undefined> = {
  RETEACH: 'warn',
  AMBIGUOUS_QUESTION: 'warn',
  INSUFFICIENT_EVIDENCE: 'info',
  SMALL_GROUP_PRACTICE: 'info',
}

/** داشبورد اقدام‌محور استاد — هر گزارش به یک اقدام آموزشی منتهی می‌شود. */
export default function ProfessorActions({ courseId }: { courseId: string }) {
  const [data, setData] = useState<ProfessorActionsData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'اقدام‌های استاد | دانشجو۳۶۰'
    let alive = true
    api
      .get<ProfessorActionsData>(`/courses/${courseId}/professor-actions`)
      .then((d) => alive && setData(d))
      .catch((e) =>
        alive && setError(e instanceof Error ? e.message : 'خطا در دریافت اقدام‌های پیشنهادی'),
      )
    return () => {
      alive = false
    }
  }, [courseId])

  return (
    <div>
      <div className="page-header">
        <h1>🧭 اقدام‌های پیشنهادی آموزشی</h1>
        <div className="muted">
          به‌جای میانگین‌های صرف: کدام مفهوم نیاز به بازتوضیح دارد؟ کدام سؤال ابهام‌دار است؟
          چه گروهی به تمرین مشترک نیاز دارد؟
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {!data && !error && (
        <div className="center-note">
          <div className="spinner" />
        </div>
      )}

      {data && (
        <>
          {data.cards.length === 0 && (
            <div className="empty-box">
              <strong>همه‌چیز در مسیر درست است</strong>
              فعلاً اقدام فوری‌ای شناسایی نشده است؛ داشبورد دوره‌ای به‌روزرسانی می‌شود.
            </div>
          )}
          {data.cards.map((c, i) => (
            <div key={i} className="action-card" data-tone={TONE[c.type]}>
              <div className="ac-title">{c.title}</div>
              <div className="ac-detail">{c.detail}</div>
              <div className="btn-row" style={{ marginTop: 8 }}>
                <Link className="btn btn-sm btn-primary" to={c.action_url}>
                  {c.action_label}
                </Link>
              </div>
            </div>
          ))}
          <p className="muted" style={{ fontSize: '0.82rem' }}>
            {data.note}
          </p>
        </>
      )}
    </div>
  )
}
