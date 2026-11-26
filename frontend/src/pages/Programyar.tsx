import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { fmtJalali } from '../utils/jalali'
import { useAuth } from '../auth'

/** صفحهٔ «برنامهٔ ترم جاری» (v3.9.0) — تنها سرویس مصرفی از برنامه‌یار۳۶۰:
 *  برنامهٔ هفتگی ترم جاریِ متناسب با استاد. دروس یکتا و سرفصل‌ها از پایه‌یار۳۶۰ می‌آیند. */

interface PyStatus {
  base_url: string
  reachable: boolean
  auth_required: boolean
  credentials_configured: boolean
  scope: string
  message: string
}

interface ScheduleEntry {
  day: string
  start: string
  end: string
  course_title: string
  course_code: string
  group: string
  place: string
  professor_name: string
}

interface ProfessorOption {
  ext_id: string
  name: string
  department: string
}

interface ScheduleResp {
  ok: boolean
  source: 'live' | 'demo'
  term: string
  professor: { ext_id: string; name: string; department: string }
  matched_profile: boolean
  entries: ScheduleEntry[]
  days: string[]
  slots: { start: string; end: string }[]
  total_weekly_hours: number
  message: string
}

const SOURCE_LABEL = { live: 'زنده از برنامه‌یار۳۶۰', demo: 'نمونهٔ قطعی توسعه' }

export default function Programyar() {
  const { user } = useAuth()
  const [status, setStatus] = useState<PyStatus | null>(null)
  const [professors, setProfessors] = useState<ProfessorOption[]>([])
  const [selected, setSelected] = useState('')
  const [schedule, setSchedule] = useState<ScheduleResp | null>(null)
  const [busy, setBusy] = useState<'status' | 'load' | null>(null)
  const [error, setError] = useState('')
  const [loadedAt, setLoadedAt] = useState<string | null>(null)

  const isStaffManager = user ? !['STUDENT'].includes(user.role) && user.role !== 'PROFESSOR' : false

  useEffect(() => {
    document.title = 'برنامهٔ ترم جاری | دانشجو۳۶۰'
  }, [])

  const checkStatus = async () => {
    setBusy('status'); setError('')
    try {
      setStatus(await api.get<PyStatus>('/integration/programyar/status'))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'خطای ارتباط با سرور')
    } finally {
      setBusy(null)
    }
  }

  /** بارگذاری برنامهٔ استاد — پیش‌فرض خودِ کاربر؛ مدیر می‌تواند استاد دلخواه را برگزیند */
  const loadSchedule = async (extId?: string) => {
    setBusy('load'); setError(''); setSchedule(null)
    try {
      const qs = extId ? `?professor_ext_id=${encodeURIComponent(extId)}&refresh=true` : '?refresh=true'
      const r = await api.get<ScheduleResp>(`/integration/programyar/schedule${qs}`)
      setSchedule(r)
      setSelected(r.professor?.ext_id || '')
      setLoadedAt(new Date().toISOString())
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'خطای ارتباط با سرور')
    } finally {
      setBusy(null)
    }
  }

  /** انتخاب استاد برای مدیران — فهرست اساتیدِ همگام‌شده از پایه‌یار */
  const loadProfessors = async () => {
    try {
      const r = await api.get<{ items: ProfessorOption[] }>('/integration/professors?limit=200')
      setProfessors(r.items || [])
    } catch {
      setProfessors([])
    }
  }

  useEffect(() => {
    void checkStatus()
    void loadSchedule()
    if (isStaffManager) void loadProfessors()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const cellFor = (day: string, slot: { start: string; end: string }): ScheduleEntry | undefined =>
    schedule?.entries.find((e) => e.day === day && e.start === slot.start)

  return (
    <>
      <div className="hero">
        <div className="hero-icon">🗓️</div>
        <div>
          <h2>برنامهٔ ترم جاری — برنامه‌یار۳۶۰</h2>
          <p>
            از سامانهٔ برنامه‌یار۳۶۰ فقط سرویسِ «برنامهٔ ترم جاری» واکشی می‌شود، آن هم
            متناسب با استاد: برنامهٔ هفتگی کلاس‌های استادِ انتخاب‌شده در نیم‌سال جاری.
            بقیهٔ اطلاعات (دروس یکتا، تفکیکی و سرفصل‌ها) از{' '}
            <Link to="/payehyar">پایه‌یار۳۶۰</Link> همگام‌سازی می‌شود و مطلوبیات اساتید
            از <Link to="/darsyar">درس‌یار۳۶۰</Link> می‌آید.
          </p>
        </div>
      </div>

      {/* وضعیت اتصال */}
      <div className="card">
        <div className="card-title">
          <h3>وضعیت اتصال</h3>
          <button type="button" className="btn btn-sm" disabled={busy !== null} onClick={checkStatus}>
            {busy === 'status' ? 'در حال بررسی…' : 'بررسی دوباره'}
          </button>
        </div>
        {status && (
          <div className={status.reachable ? 'success-box' : 'inline-alert'}>
            {status.reachable ? '✓ ' : '✕ '}
            {status.message}
            <div className="hint" style={{ marginTop: 4 }}>{status.scope}</div>
          </div>
        )}
        {error && <div className="error-box"><span>{error}</span></div>}
      </div>

      {/* انتخاب استاد + همگام‌سازی */}
      <div className="card">
        <div className="card-title">
          <h3>برنامهٔ هفتگی ترم جاری</h3>
          {schedule && (
            <span className="term-pill">📌 {schedule.term}</span>
          )}
        </div>

        {isStaffManager && professors.length > 0 && (
          <div className="form-item" style={{ maxWidth: 420 }}>
            <label className="label">انتخاب استاد</label>
            <select className="input" value={selected}
                    onChange={(e) => void loadSchedule(e.target.value)}>
              {professors.map((p) => (
                <option key={p.ext_id} value={p.ext_id}>
                  {p.name}{p.department ? ` — ${p.department}` : ''}
                </option>
              ))}
            </select>
            <div className="hint">برنامهٔ متناسب با استادِ انتخابی در ترم جاری نمایش داده می‌شود.</div>
          </div>
        )}

        <div className="btn-row section-gap">
          <button type="button" className="btn btn-primary" disabled={busy !== null}
                  onClick={() => void loadSchedule(selected || undefined)}>
            {busy === 'load' ? '⏳ در حال واکشی…' : '🔄 همگام‌سازی برنامهٔ ترم جاری'}
          </button>
          {schedule?.professor && (
            <span className="muted">
              استاد: <b>{schedule.professor.name}</b>
              {schedule.professor.department ? ` · ${schedule.professor.department}` : ''}
              {schedule.matched_profile ? '' : ' (تطبیق با رونوشت اساتید پایه‌یار انجام نشد)'}
            </span>
          )}
          {loadedAt && <span className="muted">آخرین واکشی: {fmtJalali(loadedAt, { withTime: true })}</span>}
        </div>

        {schedule && (
          <>
            <div className={schedule.source === 'live' ? 'success-box' : 'inline-alert'}
                 style={{ marginTop: 10 }}>
              {schedule.source === 'live' ? '✓ ' : 'ℹ '}
              {schedule.message}
            </div>
            {schedule.entries.length === 0 ? (
              <div className="empty-box">
                <strong>جلسه‌ای برای این استاد در ترم جاری ثبت نشده</strong>
                اگر سامانهٔ برنامه‌یار برنامهٔ این استاد را دارد، پس از تنظیم اتصال دوباره
                «همگام‌سازی» را بزنید.
              </div>
            ) : (
              <>
                <div className="muted" style={{ margin: '10px 0' }}>
                  جمع ساعت هفتگی: <b>{schedule.total_weekly_hours.toLocaleString('fa-IR')} ساعت</b> ·
                  {' '}تعداد جلسه: <b>{schedule.entries.length.toLocaleString('fa-IR')}</b>
                  {' '}· <span className={`badge ${schedule.source === 'live' ? 'badge-success' : 'badge-info'}`}>
                    {SOURCE_LABEL[schedule.source]}
                  </span>
                </div>
                <div className="table-wrap">
                  <table className="table schedule-grid">
                    <thead>
                      <tr>
                        <th>بازهٔ ساعت</th>
                        {schedule.days.map((d) => <th key={d}>{d}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {schedule.slots.map((slot) => (
                        <tr key={slot.start}>
                          <td className="slot-head">{slot.start}–{slot.end}</td>
                          {schedule.days.map((d) => {
                            const e = cellFor(d, slot)
                            return (
                              <td key={d}>
                                {e ? (
                                  <div className="sched-chip">
                                    <div className="sched-title">{e.course_title}</div>
                                    <div className="sched-meta">
                                      {e.course_code}{e.group && ` · ${e.group}`}{e.place && ` · ${e.place}`}
                                    </div>
                                  </div>
                                ) : ''}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </>
  )
}
