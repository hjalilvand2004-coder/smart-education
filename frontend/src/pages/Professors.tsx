import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { fmtJalali } from '../utils/jalali'

/** صفحهٔ «اساتید» (v3.7.0) — واکشی اساتید از پایه‌یار۳۶۰ و مطلوبیات درسی/زمانی
 *  از درس‌یار۳۶۰ (darsyar360.ir) + درس‌های متناسب برای تولید محتوا در استودیو. */

interface MdOverview {
  domains: Record<string, { count: number; last_synced_at: string | null }>
}

interface Professor {
  ext_id: string
  name: string
  department: string
  code: string
  email: string
  degree: string
  last_synced_at: string | null
}

interface SubjectPref {
  title: string
  course_code: string
  weekly_hours: number
  level: string
}

interface TimeSlot {
  day: string
  start: string
  end: string
  preference: 'preferred' | 'acceptable' | 'avoided'
  preference_label: string
}

interface PreferencesResp {
  ok: boolean
  source: 'live' | 'demo'
  cached: boolean
  fetched_at: string | null
  message?: string
  subjects: SubjectPref[]
  time_slots: TimeSlot[]
  constraints: string[]
}

interface MatchingCourse {
  course_id: string | null
  title: string
  code: string
  matched_subjects: string[]
  weekly_hours: number | null
  level: string | null
  syllabus_topics: number
  studio_url: string | null
  has_course: boolean
}

const DAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه']
const SLOT_RANGES = ['۸:۰۰–۱۰:۰۰', '۱۰:۰۰–۱۲:۰۰', '۱۳:۰۰–۱۵:۰۰', '۱۵:۰۰–۱۷:۰۰']

function faTime(v: string | null | undefined): string {
  if (!v) return '—'
  return fmtJalali(v, { withTime: true })
}

function initials(name: string): string {
  const parts = name.replace('دکتر', '').trim().split(/\s+/)
  return (parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')
}

function slotCell(slots: TimeSlot[], day: string, range: string): TimeSlot | null {
  const [start, end] = range.split('–')
  return slots.find((s) => s.day === day && s.start === start && s.end === end) ?? null
}

export default function Professors() {
  const [overview, setOverview] = useState<MdOverview | null>(null)
  const [items, setItems] = useState<Professor[]>([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [msgOk, setMsgOk] = useState(true)
  const [open, setOpen] = useState<string | null>(null)
  const [prefs, setPrefs] = useState<Record<string, PreferencesResp | 'loading' | 'error'>>({})
  const [matching, setMatching] = useState<Record<string, MatchingCourse[]>>({})

  const load = useCallback(async (query: string) => {
    setLoading(true)
    try {
      const [ov, list] = await Promise.all([
        api.get<MdOverview>('/integration/payehyar/mdm/overview'),
        api.get<{ total: number; items: Professor[] }>(
          `/integration/professors?q=${encodeURIComponent(query)}`),
      ])
      setOverview(ov)
      setItems(list.items)
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'دریافت اساتید ناموفق بود')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load('') }, [load])

  const sync = async () => {
    setSyncing(true)
    setMsg(null)
    try {
      const r = await api.post<{ ok: boolean; message?: string; error?: { message: string; hint: string | null } }>(
        '/integration/professors/sync')
      setMsgOk(r.ok)
      setMsg(r.ok ? (r.message ?? 'همگام‌سازی اساتید انجام شد')
        : `${r.error?.message ?? 'همگام‌سازی ناموفق بود'}${r.error?.hint ? ` — ${r.error.hint}` : ''}`)
      await load(q)
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'همگام‌سازی ناموفق بود')
    } finally {
      setSyncing(false)
    }
  }

  const toggle = async (p: Professor) => {
    if (open === p.ext_id) { setOpen(null); return }
    setOpen(p.ext_id)
    if (!prefs[p.ext_id] || prefs[p.ext_id] === 'error') {
      setPrefs((prev) => ({ ...prev, [p.ext_id]: 'loading' }))
      try {
        const pr = await api.get<PreferencesResp>(`/integration/professors/${encodeURIComponent(p.ext_id)}/preferences`)
        setPrefs((prev) => ({ ...prev, [p.ext_id]: pr }))
        const mc = await api.get<{ items: MatchingCourse[] }>(
          `/integration/professors/${encodeURIComponent(p.ext_id)}/matching-courses`)
        setMatching((prev) => ({ ...prev, [p.ext_id]: mc.items }))
      } catch (e) {
        setMsgOk(false)
        setMsg(e instanceof Error ? `خطا در واکشی مطلوبیات: ${e.message}` : 'واکشی مطلوبیات ناموفق بود')
        setPrefs((prev) => ({ ...prev, [p.ext_id]: 'error' }))
      }
    }
  }

  const profCount = overview?.domains['professors']?.count

  return (
    <main className="page" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div className="page-header">
        <h1>اساتید</h1>
        <p className="subtitle">
          اساتید از سامانهٔ <b>پایه‌یار۳۶۰</b> واکشی می‌شود و مطلوبیات درسی و زمانی هر استاد از
          سامانهٔ <b>درس‌یار۳۶۰</b> (darsyar360.ir) دریافت و در همین‌جا نمایش داده می‌شود؛
          درس‌های متناسب با مطلوبیات، مستقیم به استودیوی تولید محتوا پیوند می‌خورند.
        </p>
      </div>

      {/* آمار */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        <div className="card prof-stat">
          <div style={{ fontSize: '1.6rem', fontWeight: 800 }}>{profCount ?? items.length}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>استاد همگام‌شده از پایه‌یار</div>
        </div>
        <div className="card prof-stat">
          <div style={{ fontSize: '1.6rem', fontWeight: 800 }}>{items.filter((p) => prefs[p.ext_id] && prefs[p.ext_id] !== 'error').length}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>مطلوبیات واکشی‌شده از درس‌یار</div>
        </div>
        <div className="card prof-stat">
          <div style={{ fontSize: '1.6rem', fontWeight: 800 }}>{Object.values(matching).reduce((a, l) => a + l.length, 0)}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>درس متناسب شناسایی‌شده</div>
        </div>
      </div>

      {/* همگام‌سازی و جستجو */}
      <div className="card">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button type="button" className="btn btn-primary" disabled={syncing} onClick={() => void sync()}>
            {syncing ? '⏳ در حال همگام‌سازی…' : '🔄 همگام‌سازی اساتید از پایه‌یار۳۶۰'}
          </button>
          <form onSubmit={(e) => { e.preventDefault(); void load(q) }} style={{ display: 'flex', gap: 8, flex: 1, minWidth: 240 }}>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جستجوی نام یا کد استاد…"
              style={{ flex: 1, padding: '8px 12px', borderRadius: 10, border: '1px solid var(--border, #ccc)', background: 'transparent', color: 'inherit' }}
            />
            <button type="submit" className="btn" disabled={loading}>{loading ? '…' : '🔍'}</button>
          </form>
        </div>
        {msg && (
          <div style={{ marginTop: 8, fontSize: '0.85rem', color: msgOk ? 'var(--success-text)' : 'var(--danger-text)' }}>
            {msgOk ? '✓ ' : '✗ '}{msg}
          </div>
        )}
      </div>

      {/* کارت اساتید */}
      {items.length === 0 && !loading && (
        <div className="card prof-empty">
          <div style={{ fontSize: '2.2rem', marginBottom: 8 }}>🧑‍🏫</div>
          استادی ثبت نشده — با «همگام‌سازی اساتید از پایه‌یار۳۶۰» فهرست را دریافت کنید.
        </div>
      )}
      <div className="prof-grid">
        {items.map((p) => {
          const pr = prefs[p.ext_id]
          const isOpen = open === p.ext_id
          return (
            <div key={p.ext_id} className={`card prof-card${isOpen ? ' prof-card-open' : ''}`}>
              <button type="button" className="prof-head" onClick={() => void toggle(p)}>
                <span className="prof-avatar">{initials(p.name)}</span>
                <span className="prof-meta">
                  <span className="prof-name">{p.name}</span>
                  <span className="prof-sub">
                    {[p.department, p.degree].filter(Boolean).join(' — ') || 'بدون گروه'}
                  </span>
                  {p.code && <span className="badge badge-info prof-code">کد {p.code}</span>}
                </span>
                <span className={`prof-chev${isOpen ? ' open' : ''}`}>▾</span>
              </button>

              {isOpen && (
                <div className="prof-detail">
                  {pr === 'loading' && <div className="prof-note">⏳ در حال واکشی مطلوبیات از درس‌یار۳۶۰…</div>}
                  {pr === 'error' && <div className="prof-note prof-note-err">واکشی مطلوبیات ناموفق بود — دوباره تلاش کنید</div>}
                  {pr && pr !== 'loading' && pr !== 'error' && (
                    <>
                      <div className="prof-source">
                        منبع: {pr.source === 'live' ? '🟢 زنده از درس‌یار۳۶۰' : '🟡 نمونهٔ توسعه (سرویس درس‌یار در دسترس نیست)'}
                        {' '}— آخرین واکشی: {faTime(pr.fetched_at)}
                      </div>
                      {pr.message && <div className="prof-note">{pr.message}</div>}

                      {/* مطلوبیات درسی */}
                      <h3 className="prof-section-title">📚 مطلوبیات درسی</h3>
                      <div className="prof-subjects">
                        {pr.subjects.map((s, i) => (
                          <div key={i} className="prof-subject">
                            <span className="prof-subject-title">{s.title}</span>
                            <span className="prof-subject-meta">
                              {s.weekly_hours} ساعت/هفته · سطح {s.level}
                              {s.course_code && ` · کد ${s.course_code}`}
                            </span>
                          </div>
                        ))}
                        {pr.subjects.length === 0 && <div className="prof-note">مطلوبیت درسی ثبت نشده</div>}
                      </div>

                      {/* مطلوبیات زمانی */}
                      <h3 className="prof-section-title">🕐 مطلوبیات زمانی</h3>
                      <div className="prof-timetable" role="table" aria-label="جدول مطلوبیات زمانی هفتگی">
                        <div className="prof-tt-row prof-tt-head">
                          <span />
                          {DAYS.map((d) => <span key={d}>{d}</span>)}
                        </div>
                        {SLOT_RANGES.map((range) => (
                          <div key={range} className="prof-tt-row">
                            <span className="prof-tt-range">{range}</span>
                            {DAYS.map((d) => {
                              const cell = slotCell(pr.time_slots, d, range)
                              const cls = cell ? `pref-${cell.preference}` : 'pref-none'
                              const label = cell ? cell.preference_label : '—'
                              return (
                                <span key={d} className={`prof-tt-cell ${cls}`} title={`${d} ${range}: ${label}`}>
                                  {label}
                                </span>
                              )
                            })}
                          </div>
                        ))}
                      </div>
                      <div className="prof-legend">
                        <span className="pref-chip pref-preferred">مطلوب</span>
                        <span className="pref-chip pref-acceptable">قابل‌قبول</span>
                        <span className="pref-chip pref-avoided">غیرمطلوب</span>
                      </div>

                      {/* محدودیت‌ها */}
                      {pr.constraints.length > 0 && (
                        <>
                          <h3 className="prof-section-title">⚠️ محدودیت‌ها</h3>
                          <ul className="prof-constraints">
                            {pr.constraints.map((c, i) => <li key={i}>{c}</li>)}
                          </ul>
                        </>
                      )}

                      {/* درس‌های متناسب */}
                      <h3 className="prof-section-title">🎯 درس‌های متناسب برای تولید محتوا</h3>
                      <div className="prof-matching">
                        {(matching[p.ext_id] ?? []).map((m, i) => (
                          <div key={i} className="prof-match-card">
                            <div className="prof-match-title">{m.title}{m.code && ` (${m.code})`}</div>
                            <div className="prof-match-meta">
                              تطبیق با: {m.matched_subjects.join('، ')}
                              {m.syllabus_topics > 0 && ` · ${m.syllabus_topics} سرفصل`}
                              {m.level && ` · سطح ${m.level}`}
                            </div>
                            {m.studio_url
                              ? <Link className="btn btn-primary prof-match-btn" to={m.studio_url}>🚀 ورود به استودیوی تولید محتوا</Link>
                              : <span className="prof-note">درسی با این عنوان در سامانه ساخته نشده — از «دروس یکتا» ایجاد/همگام کنید</span>}
                          </div>
                        ))}
                        {(matching[p.ext_id] ?? []).length === 0 && (
                          <div className="prof-note">درسی متناسب با مطلوبیات درسی یافت نشد</div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </main>
  )
}
