import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Assessment } from '../api'
import StatusBadge, { kindLabel } from '../components/StatusBadge'
import { fmtJalali } from '../utils/jalali'

function fmtDate(iso?: string): string {
  if (!iso) return '—'
  try {
    return fmtJalali(iso, { withTime: true })
  } catch {
    return iso
  }
}

/** فهرست آزمون‌ها و ارزیابی‌های درس با دکمه شروع. */
export default function Assessments({ courseId }: { courseId: string }) {
  const navigate = useNavigate()
  const [items, setItems] = useState<Assessment[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .get<Assessment[]>(`/assessments?course_id=${encodeURIComponent(courseId)}`)
      .then((rows) => alive && setItems(rows || []))
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت آزمون‌ها'))
    return () => {
      alive = false
    }
  }, [courseId])

  if (error) return <div className="error-box">{error}</div>
  if (items === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت آزمون‌ها…
      </div>
    )
  }
  if (items.length === 0) {
    return (
      <div className="empty-box">
        <strong>آزمونی تعریف نشده است</strong>
        هنوز هیچ آزمون یا تمرینی برای این درس ساخته نشده است.
      </div>
    )
  }

  return (
    <div className="card">
      <h2>آزمون‌ها و تمرین‌های درس</h2>
      {items.map((a) => (
        <div key={a.id} className="activity-row">
          <div style={{ minWidth: 0 }}>
            <strong>{a.title}</strong>
            <div className="muted">
              نوع: {kindLabel(a.kind)} — حالت: {kindLabel(a.mode)}
              {a.duration_minutes ? ` — مدت: ${a.duration_minutes} دقیقه` : ''}
              {a.policy?.feedback ? ` — ${kindLabel(a.policy.feedback)}` : ''}
            </div>
            <div className="muted">ایجاد: {fmtDate(a.created_at)}</div>
          </div>
          <div className="badge-row" style={{ alignItems: 'center' }}>
            <span className={`badge badge-${a.mode === 'ADAPTIVE_PRACTICE' ? 'ai' : 'neutral'}`}>
              {kindLabel(a.mode)}
            </span>
            {a.status ? <StatusBadge status={a.status} /> : null}
            <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate(`/quiz/${a.id}`)}>
              شروع آزمون
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
