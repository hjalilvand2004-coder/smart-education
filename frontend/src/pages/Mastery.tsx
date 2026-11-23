import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Diagnostic, MasteryEntry } from '../api'
import { AIEstimateBadge, hypothesisLabel } from '../components/StatusBadge'

interface Narrative {
  state_label: string
  evidence_line: string
  uncertainty_spread: number | null
  evidence_diverse: boolean
  why: string
  next_step: { label: string; url: string; ref?: string } | null
}

type MasteryRow = MasteryEntry & { narrative?: Narrative }

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}٪`
}

const STATE_FALLBACK: Record<string, string> = {
  KNOWN: 'تثبیت‌شده',
  PARTIAL: 'در حال تثبیت',
  WEAK: 'نیازمند تمرین',
  UNKNOWN: 'هنوز ارزیابی نشده',
}

/** تسلط من — روایت‌محور (نسخه ۳.۱): وضعیت/شواهد/چرا/قدم بعدی.
 * «UNKNOWN» خنثی نمایش داده می‌شود — نامشخص یعنی شواهد کافی نیست، نه ضعف قطعی. */
export default function Mastery({ courseId }: { courseId: string }) {
  const [entries, setEntries] = useState<MasteryRow[] | null>(null)
  const [diagnostics, setDiagnostics] = useState<Diagnostic[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'تسلط من | دانشجو۳۶۰'
    let alive = true
    Promise.all([
      api.get<MasteryRow[]>(`/me/courses/${courseId}/mastery`),
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

  const order: Record<string, number> = { WEAK: 0, UNKNOWN: 1, PARTIAL: 2, KNOWN: 3 }
  const sorted = [...entries].sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9))
  const unknownCount = entries.filter((e) => e.status === 'UNKNOWN').length

  return (
    <>
      <div className="card">
        <div className="card-title">
          <h2>تسلط من — روایت یادگیری</h2>
          <AIEstimateBadge />
        </div>
        <div className="inline-alert">
          برای هر مفهوم: وضعیت، شواهد، «چرا این نتیجه؟» و قدم بعدی پیشنهادی.
          {unknownCount > 0
            ? ` ${unknownCount} مفهوم «هنوز ارزیابی نشده» است — این وضعیت خنثی است، نه نشانه ضعف.`
            : ''}
        </div>
        {entries.length === 0 ? (
          <div className="empty-box">
            <strong>هنوز شواهدی ثبت نشده است</strong>
            با مطالعه محتوا و شرکت در آزمون‌ها، مدل یادگیری از شما شواهد جمع می‌کند.
          </div>
        ) : (
          sorted.map((e) => {
            const nar = e.narrative
            return (
              <div key={e.concept_id} className="narrative-card">
                <div className="n-state">
                  <span className="mastery-name">{e.concept_name}</span>
                  <span className={`n-chip${e.status === 'UNKNOWN' ? ' unknown' : ''}`}>
                    {nar?.state_label ?? STATE_FALLBACK[e.status] ?? e.status}
                  </span>
                </div>
                {nar ? (
                  <>
                    <div className="n-evidence">
                      {nar.evidence_line}
                      {nar.uncertainty_spread != null &&
                        ` · عدم‌قطعیت: ±${Math.round(nar.uncertainty_spread * 100)} واحد`}
                      {nar.evidence_diverse ? ' · شواهد متنوع از چند سؤال' : ''}
                      {' — اطمینان: '}
                      {pct(e.confidence)}
                    </div>
                    <div className="n-why">
                      <strong>چرا این نتیجه؟ </strong>
                      {nar.why}
                    </div>
                    {e.prerequisites && e.prerequisites.length > 0 && (
                      <div className="chip-list" style={{ marginTop: 8 }}>
                        {e.prerequisites.map((p) => (
                          <span key={p.concept_id} className="chip">
                            ↩ {p.concept_name || 'مفهوم'}:{' '}
                            {STATE_FALLBACK[p.status] ?? p.status}
                          </span>
                        ))}
                      </div>
                    )}
                    {nar.next_step && (
                      <div className="n-next">
                        <strong>قدم بعدی: </strong>
                        <Link className="btn btn-sm btn-primary" to={nar.next_step.url}>
                          {nar.next_step.label}
                        </Link>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="mastery-meta" style={{ marginTop: 6 }}>
                    شواهد: {e.evidence_count} — اطمینان: {pct(e.confidence)}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      <div className="card">
        <div className="card-title">
          <h2>فرضیه‌های تشخیصی (قابل آزمون، نه قطعی)</h2>
          <AIEstimateBadge label="تحلیل AI" />
        </div>
        {diagnostics.length === 0 ? (
          <div className="empty-box">
            <strong>فرضیه فعالی وجود ندارد</strong>
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
                      ? `/course/${courseId}/learn`
                      : a.type === 'ASK_TEACHER'
                        ? `/course/${courseId}/tutor`
                        : `/course/${courseId}/smart`
                  return (
                    <Link key={i} to={to} className="btn btn-sm" title={a.reason || undefined}>
                      {a.title}
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
