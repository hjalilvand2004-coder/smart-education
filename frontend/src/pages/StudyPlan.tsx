import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { ReviewItem, StudyActivity, StudyPlan } from '../api'
import StatusBadge, { kindLabel } from '../components/StatusBadge'
import { fmtJalali } from '../utils/jalali'

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  try {
    return fmtJalali(iso, { withTime: true })
  } catch {
    return iso
  }
}

/** برنامه مطالعه شخصی + مرورهای فاصله‌دار پیشنهادی. */
export default function StudyPlan({ courseId }: { courseId: string }) {
  const [plan, setPlan] = useState<StudyPlan | null | undefined>(undefined) // undefined = در حال بارگذاری
  const [reviews, setReviews] = useState<ReviewItem[] | null>(null)
  const [weeklyHours, setWeeklyHours] = useState('5')
  const [examDate, setExamDate] = useState('')
  const [goals, setGoals] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const p = await api.get<StudyPlan | null>(`/me/study-plans?course_id=${encodeURIComponent(courseId)}`)
      setPlan(p)
      const r = await api.get<ReviewItem[]>(`/me/review-schedule?course_id=${encodeURIComponent(courseId)}`)
      setReviews(r || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت برنامه مطالعه')
    }
  }, [courseId])

  useEffect(() => {
    load()
  }, [load])

  const createPlan = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const created = await api.post<StudyPlan>('/study-plans', {
        course_id: courseId,
        weekly_hours: Number(weeklyHours) || 5,
        exam_date: examDate || null,
        goals: goals || null,
      })
      setPlan(created)
      setNotice('برنامه مطالعه شخصی شما ساخته شد.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ساخت برنامه مطالعه ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  const regenerate = async () => {
    setBusy(true)
    setError(null)
    try {
      const created = await api.post<StudyPlan>('/study-plans', {
        course_id: courseId,
        weekly_hours: Number(weeklyHours) || plan?.weekly_hours || 5,
        exam_date: examDate || plan?.exam_date || null,
        goals: goals || null,
        regenerate: true,
      })
      setPlan(created)
      setNotice('برنامه جدید بر اساس آخرین وضعیت شما بازتولید شد.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'بازتولید برنامه ناموفق بود')
    } finally {
      setBusy(false)
    }
  }

  const setActivityStatus = async (activityId: string, status: string) => {
    setError(null)
    try {
      await api.patch(`/study-activities/${activityId}`, { status })
      setPlan((prev) =>
        prev
          ? { ...prev, activities: prev.activities.map((a) => (a.id === activityId ? { ...a, status } : a)) }
          : prev,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'به‌روزرسانی فعالیت ناموفق بود')
    }
  }

  if (plan === undefined || reviews === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت برنامه مطالعه…
      </div>
    )
  }

  if (plan === null) {
    return (
      <div className="card">
        <h2>ساخت برنامه مطالعه شخصی</h2>
        <p className="muted">
          هنوز برنامه‌ای برای این درس ندارید. با اعلام ساعات مطالعه هفتگی و تاریخ آزمون، برنامه روزانه بر اساس
          وضعیت تسلط و مرورهای سررسید برای شما ساخته می‌شود.
        </p>
        <form onSubmit={createPlan}>
          <div className="form-grid">
            <div className="form-item">
              <label className="label" htmlFor="weekly-hours">ساعات مطالعه در هفته</label>
              <input
                id="weekly-hours"
                className="input"
                type="number"
                min="1"
                max="60"
                value={weeklyHours}
                onChange={(e) => setWeeklyHours(e.target.value)}
                required
              />
            </div>
            <div className="form-item">
              <label className="label" htmlFor="exam-date">تاریخ آزمون (اختیاری)</label>
              <input id="exam-date" className="input" type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
            </div>
            <div className="form-item form-item-full">
              <label className="label" htmlFor="goals">اهداف شما از این درس (اختیاری)</label>
              <textarea id="goals" className="textarea" value={goals} onChange={(e) => setGoals(e.target.value)} placeholder="مثلاً: تسلط کامل بر فصل‌های ۱ تا ۴ برای میان‌ترم" />
            </div>
          </div>
          {error && <div className="error-box">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={busy} style={{ marginTop: 10 }}>
            {busy ? 'در حال ساخت…' : 'ساخت برنامه مطالعه'}
          </button>
        </form>
      </div>
    )
  }

  // گروه‌بندی فعالیت‌ها بر اساس روز
  const byDay = new Map<number, StudyActivity[]>()
  for (const a of plan.activities) {
    const list = byDay.get(a.day_offset) || []
    list.push(a)
    byDay.set(a.day_offset, list)
  }
  const dayKeys = [...byDay.keys()].sort((x, y) => x - y)

  return (
    <>
      <div className="page-header">
        <div>
          <h1>برنامه مطالعه شخصی</h1>
          <div className="subtitle">
            {plan.weekly_hours} ساعت در هفته — آزمون: {fmtDate(plan.exam_date)}
          </div>
        </div>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={regenerate}>
          بازتولید برنامه
        </button>
      </div>

      {notice && <div className="success-box">{notice}</div>}
      {error && <div className="error-box">{error}</div>}

      {plan.rationale_summary ? (
        <div className="card">
          <h3>منطق پیشنهادها</h3>
          <p className="muted">{plan.rationale_summary}</p>
        </div>
      ) : null}

      <div className="card">
        <h2>فعالیت‌های روزانه</h2>
        {dayKeys.length === 0 ? (
          <div className="empty-box">فعالیتی در برنامه ثبت نشده است.</div>
        ) : (
          dayKeys.map((day) => (
            <div key={day} className="day-group">
              <div className="day-title">روز {day + 1}</div>
              {byDay.get(day)!.map((a) => (
                <div key={a.id} className={`activity-row${a.status === 'DONE' ? ' done' : a.status === 'DISMISSED' ? ' dismissed' : ''}`}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <strong>{a.title}</strong>
                    <div className="muted">
                      نوع: {kindLabel(a.type)}
                      {a.concept_name ? ` — مفهوم: ${a.concept_name}` : ''} — {a.estimated_minutes} دقیقه
                    </div>
                    {a.rationale ? <div className="hint">{a.rationale}</div> : null}
                  </div>
                  <div className="btn-row">
                    <StatusBadge status={a.status} />
                    {a.status === 'PROPOSED' && (
                      <button type="button" className="btn btn-success btn-sm" onClick={() => setActivityStatus(a.id, 'ACCEPTED')}>
                        پذیرش
                      </button>
                    )}
                    {a.status !== 'DONE' && a.status !== 'DISMISSED' && (
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => setActivityStatus(a.id, 'DONE')}>
                        انجام شد
                      </button>
                    )}
                    {a.status === 'PROPOSED' && (
                      <button type="button" className="btn btn-sm" onClick={() => setActivityStatus(a.id, 'DISMISSED')}>
                        رد پیشنهاد
                      </button>
                    )}
                    {a.status === 'DISMISSED' && (
                      <button type="button" className="btn btn-sm" onClick={() => setActivityStatus(a.id, 'PROPOSED')}>
                        بازگرداندن به پیشنهادها
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      <div className="card">
        <div className="card-title">
          <h2>مرورهای پیشنهادی (مرور فاصله‌دار)</h2>
          <span className="badge badge-ai">زمان‌بندی AI</span>
        </div>
        {reviews.length === 0 ? (
          <div className="empty-box">
            <strong>مروری در افق ۱۴ روز آینده ندارید</strong>
            پس از پاسخ به سؤال‌های درس، زمان‌بندی مرور اینجا نمایش داده می‌شود.
          </div>
        ) : (
          reviews.map((r) => (
            <div key={r.concept_id} className={`review-row${r.overdue ? ' overdue' : ''}`}>
              <strong>{r.concept_name}</strong>
              <span className="muted">سررسید: {fmtDate(r.due_at)}</span>
              <span className="muted">فاصله: {r.interval_days} روز — تکرار: {r.repetitions}</span>
              {r.overdue ? <span className="badge badge-danger">عقب‌افتاده — همین امروز مرور کنید</span> : <span className="badge badge-success">در زمان مقرر</span>}
            </div>
          ))
        )}
      </div>
    </>
  )
}
