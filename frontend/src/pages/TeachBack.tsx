import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { ConceptMapData, TeachBackResult } from '../api'

/** «به من یاد بده» — دانشجو در نقش مدرس؛ بازخورد روبرکی، نه نمره رسمی. */
export default function TeachBack({ courseId }: { courseId: string }) {
  const [map, setMap] = useState<ConceptMapData | null>(null)
  const [conceptId, setConceptId] = useState('')
  const [content, setContent] = useState('')
  const [result, setResult] = useState<TeachBackResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    document.title = 'به من یاد بده | دانشجو۳۶۰'
    let alive = true
    api
      .get<ConceptMapData>(`/me/courses/${courseId}/concept-map?mode=full`)
      .then((m) => {
        if (!alive) return
        setMap(m)
        if (m.stages?.length && m.stages[0][0]) setConceptId(m.stages[0][0].concept_id)
      })
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'خطا در دریافت مفاهیم'))
    return () => {
      alive = false
    }
  }, [courseId])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await api.post<TeachBackResult>(`/me/courses/${courseId}/teach-backs`, {
        concept_id: conceptId,
        modality: 'TEXT',
        content,
      })
      setResult(res)
      setContent('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ارسال توضیح ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="teach-panel">
      <div className="page-header">
        <h1>🎙 به من یاد بده</h1>
        <div className="muted">
          یک مفهوم را با کلام خودتان توضیح دهید — قوی‌ترین شکل تثبیت یادگیری. سامانه با روبرک
          (دقت تعریف، پوشش روابط، کیفیت مثال) بازخورد می‌دهد؛ خروجی نمره رسمی نیست.
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <form className="card" onSubmit={submit}>
        <label className="label" htmlFor="tb-concept">
          مفهوم
        </label>
        <select
          id="tb-concept"
          className="select"
          value={conceptId}
          onChange={(e) => setConceptId(e.target.value)}
          required
        >
          {(map?.stages ?? []).flat().map((n) => (
            <option key={n.concept_id} value={n.concept_id}>
              {n.concept_name}
            </option>
          ))}
        </select>

        <label className="label" htmlFor="tb-content" style={{ marginTop: 10 }}>
          توضیح شما (حداقل یک جمله کامل؛ اتصال به پیش‌نیازها و یک مثال را فراموش نکنید)
        </label>
        <textarea
          id="tb-content"
          className="textarea"
          rows={7}
          required
          minLength={10}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="مثلاً: این مفهوم یعنی… و ارتباطش با مفهوم قبلی این است که… مثلاً وقتی…"
        />
        <div className="btn-row" style={{ marginTop: 10 }}>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'در حال بررسی…' : 'بررسی توضیح من'}
          </button>
        </div>
        <p className="muted" style={{ fontSize: '0.78rem', marginTop: 8 }}>
          ورودی صوتی در نسخه بعد فعال می‌شود؛ فعلاً متن بنویسید.
        </p>
      </form>

      {result && (
        <div className="card" style={{ marginTop: 14 }}>
          <h2 className="card-title">بازخورد روبرکی — {result.concept_name}</h2>
          {(result.rubric_scores ?? []).map((s) => (
            <div key={s.criterion} className="rubric-row">
              <span className="rr-score">
                {s.score}/{s.max_score}
              </span>
              <div>
                <strong>{s.criterion}</strong>
                <div className="muted" style={{ fontSize: '0.78rem' }}>
                  {s.evidence}
                </div>
              </div>
            </div>
          ))}
          {result.gaps.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <strong style={{ fontSize: '0.88rem' }}>نقاط ناقص:</strong>
              <ul className="list">
                {result.gaps.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </div>
          )}
          {result.follow_up_question && (
            <div className="followup-card">🤔 {result.follow_up_question}</div>
          )}
          <p className="muted" style={{ fontSize: '0.8rem', marginTop: 10 }}>
            {result.encouragement} — {result.note}
          </p>
        </div>
      )}
    </div>
  )
}
