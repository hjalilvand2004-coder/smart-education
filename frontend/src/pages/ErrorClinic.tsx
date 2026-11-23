import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import type { ClinicData, Course } from '../api'

const STATUS_LABEL: Record<string, string> = {
  OPEN: 'باز',
  ATTRIBUTED: 'با توضیح شما',
  RESOLVED: 'رفع‌شده',
}

export default function ErrorClinic({ courseId }: { courseId: string }) {
  const [params, setParams] = useSearchParams()
  const [courses, setCourses] = useState<Course[]>([])
  const cid = courseId || params.get('course_id') || ''
  const [data, setData] = useState<ClinicData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [explaining, setExplaining] = useState<string | null>(null)
  const [explanation, setExplanation] = useState('')
  const [saved, setSaved] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'کلینیک خطا | دانشجو۳۶۰'
    let alive = true
    api
      .get<Course[]>('/courses')
      .then((rows) => alive && setCourses(rows || []))
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [])

  const load = useCallback((id: string) => {
    if (!id) return
    let alive = true
    setData(null)
    api
      .get<ClinicData>(`/me/courses/${id}/error-clinic`)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'خطا در دریافت کلینیک خطا'))
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    load(cid)
  }, [cid, load])

  const submitAttribution = async (e: FormEvent, entryId: string) => {
    e.preventDefault()
    try {
      await api.post(`/me/error-notes/${entryId}/attribution`, { explanation })
      setSaved(entryId)
      setExplaining(null)
      setExplanation('')
      load(cid)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ثبت توضیح ناموفق بود')
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>🩺 کلینیک خطا</h1>
        <div className="muted">دفتر خطای آموزشی شما — هر خطا یک فرضیه است؛ نه برچسب.</div>
      </div>

      {courses.length > 1 && (
        <select
          className="select"
          value={cid}
          onChange={(e) => setParams({ course_id: e.target.value })}
          aria-label="انتخاب درس"
          style={{ maxWidth: 320, marginBottom: 12 }}
        >
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title} ({c.code})
            </option>
          ))}
        </select>
      )}

      {error && <div className="error-box">{error}</div>}
      {!data && !error && (
        <div className="center-note">
          <div className="spinner" />
        </div>
      )}

      {data && (
        <>
          {data.entries.length === 0 && (
            <div className="empty-box">
              <strong>دفتر خطا خالی است</strong>
              پس از پاسخ به آزمون‌ها و تمرین‌ها، الگوی خطاهای شما اینجا تحلیل می‌شود.
            </div>
          )}
          {data.entries.map((entry) => (
            <div key={entry.id} className={`clinic-entry${entry.status === 'RESOLVED' ? ' resolved' : ''}`}>
              <div className="ce-title">{entry.title}</div>
              <div className="ce-meta">
                مفهوم: {entry.concept_name ?? '—'} · شواهد: {entry.evidence_count} پاسخ ·
                بازگشت خطا: {entry.recurrence_count} بار · وضعیت: {STATUS_LABEL[entry.status] ?? entry.status}
                {entry.last_seen_at && ` · آخرین باره: ${new Date(entry.last_seen_at).toLocaleDateString('fa-IR')}`}
              </div>
              <div className="ce-explain">{entry.question}</div>
              {entry.student_explanation && (
                <div className="ce-explain">
                  <strong>توضیح شما: </strong>
                  {entry.student_explanation}
                </div>
              )}
              {saved === entry.id && <div className="success-box" style={{ marginTop: 8 }}>توضیح شما ثبت شد.</div>}
              <div className="btn-row" style={{ marginTop: 10 }}>
                {entry.suggested_practice && (
                  <Link className="btn btn-sm btn-primary" to={entry.suggested_practice.url}>
                    {entry.suggested_practice.label}
                  </Link>
                )}
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => setExplaining(explaining === entry.id ? null : entry.id)}
                >
                  «این خطا عامل دیگری داشت»
                </button>
              </div>
              {explaining === entry.id && (
                <form onSubmit={(e) => void submitAttribution(e, entry.id)} style={{ marginTop: 8 }}>
                  <textarea
                    className="textarea"
                    required
                    minLength={3}
                    value={explanation}
                    onChange={(e) => setExplanation(e.target.value)}
                    placeholder="مثلاً: در آن لحظه اینترنت قطع بود / خسته بودم / سؤال را اشتباه خواندم…"
                    aria-label="توضیح شما درباره عامل خطا"
                  />
                  <div className="btn-row" style={{ marginTop: 6 }}>
                    <button type="submit" className="btn btn-primary btn-sm">
                      ثبت توضیح
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => setExplaining(null)}>
                      انصراف
                    </button>
                  </div>
                </form>
              )}
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
