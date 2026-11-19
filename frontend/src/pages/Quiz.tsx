import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import type { FinishResult, QuestionForStudent, QuestionOption } from '../api'
import StatusBadge from '../components/StatusBadge'

const TRUE_FALSE_OPTIONS: QuestionOption[] = [
  { key: 'TRUE', text: 'درست' },
  { key: 'FALSE', text: 'نادرست' },
]

const QUESTION_TYPE_LABELS: Record<string, string> = {
  MCQ: 'چهارگزینه‌ای',
  MULTI_SELECT: 'چندپاسخی',
  TRUE_FALSE: 'درست/نادرست',
  SHORT_ANSWER: 'پاسخ کوتاه',
  ESSAY: 'تشریحی',
  NUMERIC: 'عددی',
  CASE: 'موردکاوی',
  CODE: 'کدنویسی',
  ORDERING: 'مرتب‌سازی',
  MATCHING: 'تطبیق',
}

/** صفحه آزمون: سؤال‌به‌سؤال با شمارش زمان پاسخ و بازخورد طبق سیاست. */
export default function Quiz() {
  const { assessmentId = '' } = useParams()
  const [attemptId, setAttemptId] = useState<string | null>(null)
  const [attemptStatus, setAttemptStatus] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [feedbackPolicy, setFeedbackPolicy] = useState<string>('IMMEDIATE')
  const [queue, setQueue] = useState<QuestionForStudent[]>([])
  const [index, setIndex] = useState(0)
  const [answer, setAnswer] = useState<{ selected?: string[]; value?: string; text?: string }>({})
  const [busy, setBusy] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{ correct: boolean | null; text?: string | null } | null>(null)
  const [answeredCount, setAnsweredCount] = useState(0)
  const [result, setResult] = useState<FinishResult | null>(null)
  const [courseId, setCourseId] = useState<string | null>(null)
  const [conceptNames, setConceptNames] = useState<Record<string, string>>({})
  const questionShownAt = useRef<number>(Date.now())

  useEffect(() => {
    document.title = 'آزمون | دانشجو۳۶۰'
    let alive = true
    api
      .post<{ id: string; status: string; assessment?: { title?: string; course_id?: string; policy?: { feedback?: string } }; questions: QuestionForStudent[] }>(
        `/assessments/${assessmentId}/attempts`,
      )
      .then((res) => {
        if (!alive) return
        setAttemptId(res.id)
        setAttemptStatus(res.status)
        setTitle(res.assessment?.title || 'آزمون')
        setCourseId(res.assessment?.course_id || null)
        setFeedbackPolicy(res.assessment?.policy?.feedback || 'IMMEDIATE')
        setQueue(res.questions || [])
        setIndex(0)
        questionShownAt.current = Date.now()
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'شروع آزمون ناموفق بود')
      })
    return () => {
      alive = false
    }
  }, [assessmentId])

  // نام مفاهیم برای نمایش نتیجه به تفکیک مفهوم
  useEffect(() => {
    if (!result || !courseId) return
    let alive = true
    api
      .get<{ nodes: { id: string; name: string }[] }>(`/courses/${courseId}/concept-graph`)
      .then((g) => {
        if (!alive) return
        const names: Record<string, string> = {}
        for (const n of g.nodes || []) names[n.id] = n.name
        setConceptNames(names)
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [result, courseId])

  const current = queue[index]

  const options = useMemo<QuestionOption[]>(() => {
    if (!current) return []
    if (current.type === 'TRUE_FALSE' && (!current.options || current.options.length === 0)) {
      return TRUE_FALSE_OPTIONS
    }
    return current.options || []
  }, [current])

  const submitAnswer = async () => {
    if (!attemptId || !current) return
    setError(null)
    setNotice(null)
    setBusy(true)
    const timeSpent = Date.now() - questionShownAt.current
    let payload: Record<string, unknown>
    if (current.type === 'NUMERIC') {
      payload = { value: Number(answer.value) }
    } else if (current.type === 'SHORT_ANSWER' || current.type === 'ESSAY' || current.type === 'CASE' || current.type === 'CODE') {
      payload = { text: answer.text || '' }
    } else {
      payload = { selected: answer.selected || [] }
    }
    try {
      const res = await api.post<{
        response_id: string
        auto_scored: boolean
        grading: string
        correctness?: number | null
        ai_feedback?: string | null
        next_question?: QuestionForStudent
      }>(`/attempts/${attemptId}/responses`, {
        question_version_id: current.question_version_id,
        answer: payload,
        time_spent_ms: timeSpent,
      })
      setAnsweredCount((n) => n + 1)
      // بازخورد فوری طبق سیاست آزمون
      if (feedbackPolicy === 'IMMEDIATE') {
        if (res.correctness === null || res.correctness === undefined) {
          setFeedback({ correct: null, text: 'پاسخ شما ثبت شد؛ نتیجه پس از تصحیح اعلام می‌شود.' })
        } else {
          setFeedback({
            correct: res.correctness >= 1,
            text: res.correctness >= 1 ? 'پاسخ شما درست بود.' : 'پاسخ شما نادرست بود.',
          })
        }
        if (res.ai_feedback) setFeedback((f) => ({ correct: f?.correct ?? null, text: `${f?.text || ''} بازخورد: ${res.ai_feedback}` }))
      } else {
        setFeedback(null)
        setNotice('پاسخ ثبت شد.')
      }
      // سؤال بعدی در حالت تطبیقی/پاسخ‌های پیوسته
      if (res.next_question) {
        setQueue((q) => [...q, res.next_question as QuestionForStudent])
      }
      setAnswer({})
      window.setTimeout(() => {
        setFeedback(null)
        setNotice(null)
        setIndex((i) => i + 1)
        questionShownAt.current = Date.now()
      }, feedbackPolicy === 'IMMEDIATE' ? 1400 : 300)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ثبت پاسخ ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  const finish = async () => {
    if (!attemptId) return
    setFinishing(true)
    setError(null)
    try {
      const res = await api.post<FinishResult>(`/attempts/${attemptId}/finish`)
      setResult(res)
      setAttemptStatus('GRADED')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'پایان آزمون ناموفق بود')
    } finally {
      setFinishing(false)
    }
  }

  // ---------- نتیجه ----------
  if (result) {
    const pct = result.max_score > 0 ? Math.round((result.score / result.max_score) * 100) : 0
    return (
      <>
        <div className="page-header">
          <div>
            <h1>نتیجه {title}</h1>
            <div className="subtitle">پایان آزمون — نمره شما در ادامه محاسبه شده است.</div>
          </div>
        </div>
        <div className="result-banner">
          <div className="score-big">
            {result.score} از {result.max_score}
          </div>
          <div>{pct}٪ پاسخ‌های درست</div>
          {result.pending_count ? (
            <div className="muted" style={{ marginTop: 6 }}>
              {result.pending_count} پاسخ در انتظار تصحیح نهایی (AI پیشنهادی/استاد) است؛ نمره نهایی ممکن است تغییر کند.
            </div>
          ) : null}
        </div>
        <div className="card">
          <h3>نتایج به تفکیک مفهوم</h3>
          {Object.keys(result.per_concept).length === 0 ? (
            <div className="muted">داده‌ای برای تفکیک مفهومی ثبت نشد.</div>
          ) : (
            Object.entries(result.per_concept).map(([cid, agg]) => {
              const p = agg.total > 0 ? Math.round((agg.correct / agg.total) * 100) : 0
              return (
                <div key={cid} className="per-concept-row">
                  <strong>{conceptNames[cid] || <span className="muted" style={{ direction: 'ltr' }}>{cid.slice(0, 8)}…</span>}</strong>
                  <span>
                    درست: {agg.correct} از {agg.total}
                  </span>
                  <div className="progress" style={{ maxWidth: 260 }}>
                    <div
                      className={`progress-fill ${p >= 70 ? 'success' : p >= 40 ? 'warn' : 'danger'}`}
                      style={{ width: `${p}%` }}
                    />
                  </div>
                  <span className="progress-value">{p}٪</span>
                </div>
              )
            })
          )}
        </div>
        <Link to="/courses" className="btn">بازگشت به درس‌ها</Link>
      </>
    )
  }

  // ---------- بارگذاری/خطا ----------
  if (error && !attemptId && !current) {
    return (
      <>
        <div className="error-box">{error}</div>
        <Link to="/courses" className="btn">بازگشت</Link>
      </>
    )
  }
  if (attemptId === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال آماده‌سازی آزمون…
      </div>
    )
  }
  if (!current) {
    return (
      <>
        <div className="card">
          <h2>{title}</h2>
          <p className="muted">
            به همه سؤال‌ها پاسخ داده شد ({answeredCount} پاسخ). برای محاسبه نمره، آزمون را پایان دهید.
          </p>
          {attemptStatus ? <StatusBadge status={attemptStatus} /> : null}
        </div>
        {error && <div className="error-box">{error}</div>}
        <button type="button" className="btn btn-primary" disabled={finishing} onClick={finish}>
          {finishing ? 'در حال محاسبه…' : 'پایان آزمون و مشاهده نمره'}
        </button>
      </>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>{title}</h1>
          <div className="subtitle">
            سؤال {index + 1} از {Math.max(queue.length, index + 1)} — پاسخ‌های ثبت‌شده: {answeredCount}
          </div>
        </div>
        <button type="button" className="btn btn-sm" disabled={finishing} onClick={finish}>
          پایان آزمون
        </button>
      </div>

      <div className="card quiz-question">
        <div className="card-title">
          <h3>
            <span className="quiz-number">{current.number}</span>
            {QUESTION_TYPE_LABELS[current.type] || current.type}
          </h3>
          {feedbackPolicy === 'IMMEDIATE' ? (
            <span className="badge badge-ai">بازخورد فوری</span>
          ) : (
            <span className="badge badge-neutral">بازخورد پس از پایان</span>
          )}
        </div>

        <p>{current.body}</p>
        {current.policy_help ? <div className="hint">{current.policy_help}</div> : null}

        {/* ورودی پاسخ بر اساس نوع سؤال */}
        {(current.type === 'MCQ' || current.type === 'TRUE_FALSE') && (
          <div style={{ marginTop: 10 }}>
            {options.map((o) => (
              <label key={o.key} className="radio-option">
                <input
                  type="radio"
                  name={`q-${current.question_version_id}`}
                  checked={answer.selected?.[0] === o.key}
                  onChange={() => setAnswer({ selected: [o.key] })}
                />
                <span>
                  <strong dir="ltr">{o.key}.</strong> {o.text}
                </span>
              </label>
            ))}
          </div>
        )}

        {current.type === 'MULTI_SELECT' && (
          <div style={{ marginTop: 10 }}>
            {options.map((o) => (
              <label key={o.key} className="radio-option">
                <input
                  type="checkbox"
                  checked={(answer.selected || []).includes(o.key)}
                  onChange={() => {
                    const prev = answer.selected || []
                    setAnswer({
                      selected: prev.includes(o.key) ? prev.filter((k) => k !== o.key) : [...prev, o.key],
                    })
                  }}
                />
                <span>
                  <strong dir="ltr">{o.key}.</strong> {o.text}
                </span>
              </label>
            ))}
            <div className="hint">می‌توانید چند گزینه را انتخاب کنید.</div>
          </div>
        )}

        {current.type === 'NUMERIC' && (
          <div style={{ marginTop: 10 }}>
            <label className="label" htmlFor="numeric-answer">پاسخ عددی</label>
            <input
              id="numeric-answer"
              className="input"
              type="number"
              step="any"
              dir="ltr"
              value={answer.value || ''}
              onChange={(e) => setAnswer({ ...answer, value: e.target.value })}
            />
          </div>
        )}

        {(current.type === 'SHORT_ANSWER' || current.type === 'ESSAY' || current.type === 'CASE' || current.type === 'CODE') && (
          <div style={{ marginTop: 10 }}>
            <label className="label" htmlFor="text-answer">پاسخ شما</label>
            <textarea
              id="text-answer"
              className="textarea"
              value={answer.text || ''}
              onChange={(e) => setAnswer({ ...answer, text: e.target.value })}
            />
          </div>
        )}

        {notice && <div className="success-box">{notice}</div>}
        {feedback && (
          <div className={feedback.correct === null ? 'inline-alert' : feedback.correct ? 'success-box' : 'error-box'}>
            {feedback.correct === false ? '✗ ' : feedback.correct === true ? '✓ ' : ''}
            {feedback.text}
          </div>
        )}
        {error && <div className="error-box">{error}</div>}

        <div className="btn-row" style={{ marginTop: 10 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || (current.type === 'NUMERIC' && !answer.value)}
            onClick={submitAnswer}
          >
            {busy ? 'در حال ثبت…' : 'ثبت پاسخ و ادامه'}
          </button>
        </div>
      </div>
    </>
  )
}
