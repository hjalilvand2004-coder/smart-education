import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Diagnostic, MasteryEntry } from '../api'
import { AIEstimateBadge, hypothesisLabel } from '../components/StatusBadge'
import StatusBadge from '../components/StatusBadge'

const ACTION_LABELS: Record<string, string> = {
  REVIEW: 'مرور محتوا',
  PRACTICE: 'تمرین',
  DIAGNOSTIC_QUIZ: 'آزمون تشخیصی',
  ASK_TEACHER: 'پرسش از استاد',
}

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}٪`
}

/** تسلط من + تشخیص‌های AI — «UNKNOWN» یعنی شواهد کافی نیست، نه ضعف قطعی. */
export default function Mastery({ courseId }: { courseId: string }) {
  const [entries, setEntries] = useState<MasteryEntry[] | null>(null)
  const [diagnostics, setDiagnostics] = useState<Diagnostic[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    Promise.all([
      api.get<MasteryEntry[]>(`/me/courses/${courseId}/mastery`),
      api.get<Diagnostic[]>(`/me/courses/${courseId}/diagnostics`),
    ])
      .then(([m, d]) => {
        if (!alive) return
        setEntries(m || [])
        setDiagnostics(d || [])
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'خطا در دریافت وضعیت تسلط')
      })
    return () => {
      alive = false
    }
  }, [courseId])

  if (error) return <div className="error-box">{error}</div>
  if (entries === null || diagnostics === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال تحلیل وضعیت یادگیری…
      </div>
    )
  }

  const unknownCount = entries.filter((e) => e.status === 'UNKNOWN').length

  return (
    <>
      <div className="card">
        <div className="card-title">
          <h2>تسلط من بر مفاهیم</h2>
          <AIEstimateBadge />
        </div>
        <div className="inline-alert">
          مقادیر تسلط «تخمین AI» از شواهد یادگیری شما هستند؛ وضعیت «نامشخص» یعنی شواهد کافی نیست و لزوماً ضعف نیست.
          {unknownCount > 0 ? ` (${unknownCount} مفهوم در وضعیت نامشخص است.)` : ''}
        </div>
        {entries.length === 0 ? (
          <div className="empty-box">
            <strong>هنوز شواهدی ثبت نشده است</strong>
            با مطالعه محتوا و شرکت در آزمون‌ها، مدل یادگیری از شما شواهد جمع می‌کند.
          </div>
        ) : (
          entries.map((e) => (
            <div key={e.concept_id} className="mastery-row">
              <span className="mastery-name">{e.concept_name}</span>
              <StatusBadge status={e.status} />
              <div className="progress" style={{ maxWidth: 220 }}>
                <div
                  className={`progress-fill ${e.status === 'KNOWN' ? 'success' : e.status === 'PARTIAL' ? 'warn' : e.status === 'WEAK' ? 'danger' : ''}`}
                  style={{ width: `${e.estimated_mastery != null ? Math.round(e.estimated_mastery * 100) : 0}%` }}
                />
              </div>
              <span className="progress-value">{pct(e.estimated_mastery)}</span>
              <div className="mastery-meta">
                شواهد: {e.evidence_count} — اطمینان: {pct(e.confidence)}
                {e.prerequisites && e.prerequisites.length > 0 && (
                  <>
                    {' — پیش‌نیازها: '}
                    {e.prerequisites.map((p) => (
                      <span key={p.concept_id} className="prereq-chip">
                        {p.concept_name || 'مفهوم'}
                        <StatusBadge status={p.status} />
                      </span>
                    ))}
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="card">
        <div className="card-title">
          <h2>تشخیص‌های یادگیری (هیپوتزهای AI)</h2>
          <AIEstimateBadge label="تحلیل AI" />
        </div>
        {diagnostics.length === 0 ? (
          <div className="empty-box">
            <strong>تشخیص فعالی وجود ندارد</strong>
            پس از آزمون‌های بیشتر، تحلیل‌های تشخیصی اینجا نمایش داده می‌شود.
          </div>
        ) : (
          diagnostics.map((d) => (
            <div key={d.id} className="diag-card">
              <div className="card-title" style={{ marginBottom: 6 }}>
                <h3>
                  {d.concept_name || 'مفهوم'} — {hypothesisLabel(d.hypothesis_type)}
                </h3>
                <span className="badge badge-neutral">اطمینان: {pct(d.confidence)}</span>
              </div>
              <p className="muted">{d.rationale}</p>
              <div className="diag-actions">
                {d.recommended_actions.map((a, i) => {
                  const to =
                    a.type === 'REVIEW'
                      ? `/course/${courseId}?tab=content`
                      : a.type === 'ASK_TEACHER'
                        ? `/course/${courseId}?tab=tutor`
                        : `/course/${courseId}?tab=quizzes`
                  return (
                    <Link key={i} to={to} className="btn btn-sm" title={a.reason || undefined}>
                      {a.title || ACTION_LABELS[a.type] || a.type}
                    </Link>
                  )
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </>
  )
}
