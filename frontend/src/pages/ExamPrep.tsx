import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Course, ExamPrepPlan } from '../api'

/** آمادگی آزمون با اولویت‌بندی صادقانه — پوشش و عدم‌قطعیت؛ بدون وعده نمره. */
export default function ExamPrep({ courseId }: { courseId: string }) {
  const [courses, setCourses] = useState<Course[]>([])
  const [cid, setCid] = useState(courseId)
  const [examDate, setExamDate] = useState('')
  const [minutes, setMinutes] = useState<number | ''>('')
  const [plan, setPlan] = useState<ExamPrepPlan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    document.title = 'آمادگی آزمون | دانشجو۳۶۰'
    let alive = true
    api
      .get<Course[]>('/courses')
      .then((rows) => {
        if (!alive) return
        setCourses(rows || [])
        if (!courseId && rows?.length) setCid(rows[0].id)
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [courseId])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!cid) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.post<{ plan: ExamPrepPlan }>(`/me/courses/${cid}/exam-prep`, {
        exam_date: examDate || null,
        available_minutes: minutes === '' ? null : Number(minutes),
      })
      setPlan(res.plan)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ساخت برنامه ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  const tierIcon = (tier: number) => (tier === 1 ? '🔴' : tier === 2 ? '❔' : '🔁')
  const allocated = plan?.allocated_minutes

  return (
    <div>
      <div className="page-header">
        <h1>🎯 آمادگی آزمون — اولویت‌بندی صادقانه</h1>
        <div className="muted">
          تاریخ آزمون و زمان در دسترس را بگویید؛ سامانه می‌گوید ابتدا کدام مفاهیم، کدام
          پیش‌نیازها و چه چیزی مرور شود — و صادقانه می‌گوید کجا شواهد کافی نداریم.
        </div>
      </div>

      {courses.length > 1 && (
        <select className="select" value={cid} onChange={(e) => setCid(e.target.value)} aria-label="درس" style={{ maxWidth: 320, marginBottom: 12 }}>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title} ({c.code})
            </option>
          ))}
        </select>
      )}

      {error && <div className="error-box">{error}</div>}

      <form className="card" onSubmit={submit}>
        <div className="form-grid">
          <div className="form-item">
            <label className="label" htmlFor="ep-date">تاریخ آزمون (اختیاری)</label>
            <input id="ep-date" className="input" type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          </div>
          <div className="form-item">
            <label className="label" htmlFor="ep-mins">زمان در دسترس تا آزمون (دقیقه)</label>
            <input
              id="ep-mins"
              className="input"
              type="number"
              min={0}
              step={15}
              placeholder="مثلاً ۳۶۰"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value === '' ? '' : Number(e.target.value))}
            />
          </div>
        </div>
        <div className="btn-row" style={{ marginTop: 10 }}>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'در حال ساخت برنامه…' : 'ساخت برنامه صادقانه'}
          </button>
        </div>
      </form>

      {plan && (
        <>
          <div className="honesty-note">⚖️ {plan.honesty_note}</div>

          {plan.coverage && (
            <div className="card" style={{ marginBottom: 12 }}>
              <h2 className="card-title">پوشش یادگیری</h2>
              <div className="progress" style={{ maxWidth: 420 }}>
                <div
                  className="progress-fill"
                  style={{ width: `${Math.round((plan.coverage.coverage_ratio ?? 0) * 100)}%` }}
                  role="progressbar"
                  aria-valuenow={Math.round((plan.coverage.coverage_ratio ?? 0) * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
              </div>
              <p className="muted" style={{ fontSize: '0.82rem', marginTop: 6 }}>
                {plan.coverage.with_evidence} از {plan.coverage.total_concepts} مفهوم حداقل یک شواهد
                ارزیابی معتبر دارند — {plan.coverage.meaning}
              </p>
            </div>
          )}

          {plan.priority_order.map((tier) => (
            <div key={tier.tier} className="tier-block">
              <div className="tier-label">
                {tierIcon(tier.tier)} {tier.label}
              </div>
              {tier.concepts.length === 0 && <p className="muted">موردی نیست — این بخش پاک است.</p>}
              {tier.concepts.map((c) => (
                <div key={c.concept_id} className="activity-row">
                  <div>
                    <strong>{c.concept_name}</strong>
                    <div className="muted" style={{ fontSize: '0.8rem' }}>
                      {c.action} · ~{c.minutes_hint} دقیقه — {c.why}
                      {c.prereq_required && c.prereq_required.length > 0 && (
                        <> · پیش‌نیاز لازم: {c.prereq_required.join('، ')}</>
                      )}
                    </div>
                  </div>
                  <Link className="btn btn-sm" to={`/course/${cid}/learn?concept=${c.concept_id}`}>
                    یادگیری
                  </Link>
                </div>
              ))}
            </div>
          ))}

          {allocated && (
            <div className="honesty-note">
              ⏱ {allocated.message}
              {!allocated.fits && allocated.covered?.length
                ? ` پوشش‌داده‌شده‌ها: ${allocated.covered.join('، ')}.`
                : ''}
            </div>
          )}

          {plan.insufficient_evidence.length > 0 && (
            <div className="card">
              <h2 className="card-title">جاهایی که هنوز شواهد کافی نداریم</h2>
              <div className="chip-list">
                {plan.insufficient_evidence.map((x) => (
                  <span key={x.concept_id} className="chip">{x.concept_name} — نامشخص</span>
                ))}
              </div>
              <p className="muted" style={{ fontSize: '0.82rem' }}>{plan.uncertainty_note}</p>
            </div>
          )}

          <p className="muted" style={{ fontSize: '0.8rem' }}>🗓 {plan.programyar_note}</p>
        </>
      )}
    </div>
  )
}
