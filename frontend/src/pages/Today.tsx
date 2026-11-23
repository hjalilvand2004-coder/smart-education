import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Course, SessionPlan, TodayFocus } from '../api'

/** آسمان ستاره‌ای کشف — CSS خالص و سبک */
function StarSky({ count = 34 }: { count?: number }) {
  const stars = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        left: `${(i * 37 + 13) % 100}%`,
        top: `${(i * 53 + 7) % 92}%`,
        size: 2 + (i % 3),
      })),
    [count],
  )
  return (
    <div className="obs-stars" aria-hidden="true">
      {stars.map((s, i) => (
        <span key={i} style={{ left: s.left, top: s.top, width: s.size, height: s.size }} />
      ))}
    </div>
  )
}

const DURATIONS = [5, 15, 30]

export default function Today() {
  const [courses, setCourses] = useState<Course[]>([])
  const [courseId, setCourseId] = useState<string>('')
  const [data, setData] = useState<TodayFocus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [duration, setDuration] = useState<number>(15)
  const [session, setSession] = useState<SessionPlan | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    document.title = 'امروزِ من | دانشجو۳۶۰'
    let alive = true
    api
      .get<Course[]>('/courses')
      .then((rows) => {
        if (!alive) return
        setCourses(rows || [])
        if (rows?.length) setCourseId((prev) => prev || rows[0].id)
      })
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'خطا در دریافت درس‌ها'))
    return () => {
      alive = false
    }
  }, [])

  const loadToday = useCallback((cid: string) => {
    if (!cid) return
    let alive = true
    setData(null)
    api
      .get<TodayFocus>(`/me/courses/${cid}/today`)
      .then((d) => alive && setData(d))
      .then(() => api.get<SessionPlan | null>(`/me/courses/${cid}/learning-sessions/active`))
      .then((s) => alive && setSession(s && s.id ? s : null))
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'خطا در دریافت پیشنهاد امروز'))
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    loadToday(courseId)
  }, [courseId, loadToday])

  const startSession = async () => {
    if (!courseId) return
    setBusy(true)
    setError(null)
    try {
      const s = await api.post<SessionPlan>(
        `/me/courses/${courseId}/learning-sessions`,
        { minutes: duration },
        crypto.randomUUID(),
      )
      setSession(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطا در شروع جلسه')
    } finally {
      setBusy(false)
    }
  }

  const sessionAction = async (action: string, stepIndex?: number) => {
    if (!session) return
    setBusy(true)
    try {
      const s = await api.post<SessionPlan>(`/me/learning-sessions/${session.id}/actions`, {
        action,
        step_index: stepIndex,
      })
      setSession(s.state === 'DONE' ? null : s)
      if (action === 'done') loadToday(courseId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطا در عملیات جلسه')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <StarSky />
      {/* قهرمان کشف — «امروز از کجا شروع کنیم؟» */}
      <div className="observe-hero">
        <div className="oh-kicker">رصدخانه یادگیری — نسخه ۳.۱</div>
        <h1>{data?.greeting ?? 'سلام! امروز از کجا شروع کنیم؟'}</h1>
        <div className="oh-hint">
          یک قدم بعدی روشن، به‌جای انبوه داشبورد — انتخاب با شماست.
        </div>
        {courses.length > 1 && (
          <div style={{ marginTop: 12 }}>
            <select
              className="select"
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              aria-label="درس فعال"
              style={{ maxWidth: 320 }}
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title} ({c.code})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}
      {!data && !error && (
        <div className="center-note">
          <div className="spinner" />
        </div>
      )}

      {data && (
        <>
          {/* پیشنهاد اصلی امروز — یک دکمه اصلی */}
          <div className="suggestion-card">
            <span className="sug-badge">پیشنهاد امروز</span>
            <div className="sug-title">{data.today_suggestion.title}</div>
            <div className="sug-meta">
              <span>⏱ {data.today_suggestion.minutes} دقیقه</span>
              {data.today_suggestion.concept_id && (
                <Link to={`/course/${courseId}/map`}>مشاهده در نقشه مفاهیم</Link>
              )}
            </div>
            <div className="sug-reason">
              <strong>دلیل: </strong>
              {data.today_suggestion.reason}
            </div>
            <div>
              <Link className="btn btn-primary" to={data.today_suggestion.url}>
                {data.today_suggestion.primary_action}
              </Link>
            </div>
          </div>

          {/* سه انتخاب اصلی */}
          <div className="choice-grid" style={{ marginTop: 14 }}>
            {data.choices.map((c) => (
              <Link key={c.key} to={c.url} className="choice-card">
                <span className="c-title">{c.label}</span>
                {c.hint && <span className="c-hint">{c.hint}</span>}
              </Link>
            ))}
          </div>

          {/* جلسه یادگیری با زمان انتخابی */}
          <div className="card" style={{ marginBottom: 14 }}>
            <h2 className="card-title">جلسه یادگیری امروز</h2>
            {session ? (
              <>
                <p className="muted">
                  جلسه {session.minutes} دقیقه‌ای — وضعیت:{' '}
                  {session.state === 'PAUSED' ? 'متوقف‌شده' : 'در جریان'}
                </p>
                <div className="session-steps">
                  {(session.composition ?? []).map((step) => (
                    <div key={step.index} className={`session-step${step.done ? ' done' : ''}`}>
                      <input
                        type="checkbox"
                        checked={step.done}
                        onChange={() => sessionAction('advance', step.index)}
                        aria-label={`انجام گام ${step.title}`}
                      />
                      <div style={{ flex: 1 }}>
                        <strong style={{ fontSize: '0.9rem' }}>{step.title}</strong>
                        <div className="muted" style={{ fontSize: '0.78rem' }}>
                          {step.kind === 'REVIEW'
                            ? 'مرور فاصله‌دار'
                            : step.kind === 'MICRO_LESSON'
                              ? 'آموزش کوتاه'
                              : step.kind === 'PRACTICE'
                                ? 'تمرین هدفمند'
                                : 'کوییز هوشمند'}
                        </div>
                      </div>
                      <Link className="btn btn-sm" to={step.url}>
                        رفتن
                      </Link>
                      <span className="ss-min">{step.minutes} دقیقه</span>
                    </div>
                  ))}
                </div>
                <div className="btn-row" style={{ marginTop: 10 }}>
                  {session.state === 'PAUSED' ? (
                    <button className="btn btn-primary" disabled={busy} onClick={() => sessionAction('resume')}>
                      ادامه جلسه
                    </button>
                  ) : (
                    <button className="btn" disabled={busy} onClick={() => sessionAction('pause')}>
                      توقف جلسه
                    </button>
                  )}
                  <button className="btn btn-success" disabled={busy} onClick={() => sessionAction('done')}>
                    پایان و ثبت پیشرفت
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="muted">چقدر وقت داری؟ ترکیب مرور، مثال و تمرین متناسب با زمان پیشنهاد می‌شود.</p>
                <div className="duration-picker">
                  {DURATIONS.map((d) => (
                    <button
                      key={d}
                      type="button"
                      className={`duration-chip${duration === d ? ' on' : ''}`}
                      onClick={() => setDuration(d)}
                      aria-pressed={duration === d}
                    >
                      {d} دقیقه
                    </button>
                  ))}
                </div>
                <button className="btn btn-primary" disabled={busy} onClick={startSession}>
                  شروع جلسه یادگیری
                </button>
              </>
            )}
          </div>

          {/* پیشرفت من + مرورهای پیشنهادی */}
          <div className="grid-cards" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <div className="card">
              <h2 className="card-title">مسیر من</h2>
              <div className="kv-grid">
                <div className="kv">
                  <div className="n">{data.my_progress.known}</div>
                  <div className="l">تثبیت‌شده</div>
                </div>
                <div className="kv">
                  <div className="n">{data.my_progress.partial}</div>
                  <div className="l">در حال تثبیت</div>
                </div>
                <div className="kv">
                  <div className="n">{data.my_progress.weak}</div>
                  <div className="l">نیازمند تمرین</div>
                </div>
                <div className="kv">
                  <div className="n">{data.my_progress.unassessed}</div>
                  <div className="l">هنوز ارزیابی نشده</div>
                </div>
              </div>
              <Link className="link-btn" to={`/course/${courseId}/mastery`}>
                مشاهده روایت کامل تسلط ←
              </Link>
            </div>
            <div className="card">
              <h2 className="card-title">مرورهای پیشنهادی</h2>
              {data.reviews_suggested.length === 0 && (
                <p className="muted">فعلاً مرور فوری‌ای لازم نیست — عالی!</p>
              )}
              {data.reviews_suggested.map((r) => (
                <div key={r.concept_id} className="review-row" style={{ marginBottom: 8 }}>
                  <strong style={{ fontSize: '0.9rem' }}>{r.concept_name}</strong>
                  <div className="muted" style={{ fontSize: '0.78rem' }}>
                    {r.note}
                  </div>
                </div>
              ))}
              <Link className="link-btn" to={`/course/${courseId}/learn`}>
                شروع مرور در محیط یادگیری ←
              </Link>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 10, fontSize: '0.82rem' }}>
            {data.note}
          </p>
        </>
      )}
    </div>
  )
}
