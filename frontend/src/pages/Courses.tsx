import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, qs } from '../api'
import type { Course } from '../api'
import { useAuth } from '../auth'
import { STAFF_COURSE_ROLES } from '../auth'
import StatusBadge, { roleLabel } from '../components/StatusBadge'

/** حالت‌های نمایش فهرست درس‌ها — انتخاب کاربر به‌خاطر سپرده می‌شود. */
type ViewMode = 'cards' | 'table' | 'infographic'
const VIEW_KEY = 's360:courses-view'
const ALLOWED_VIEWS: ViewMode[] = ['cards', 'table', 'infographic']

function loadView(): ViewMode {
  try {
    const stored = localStorage.getItem(VIEW_KEY) as ViewMode | null
    if (stored && ALLOWED_VIEWS.includes(stored)) return stored
  } catch {
    /* دسترسی به localStorage ممکن نیست — حالت پیش‌فرض */
  }
  return 'cards'
}

function ViewIcon({ mode }: { mode: ViewMode }) {
  const paths: Record<ViewMode, ReactNode> = {
    cards: (
      <>
        <rect x="3" y="3" width="8" height="8" rx="2" />
        <rect x="13" y="3" width="8" height="8" rx="2" />
        <rect x="3" y="13" width="8" height="8" rx="2" />
        <rect x="13" y="13" width="8" height="8" rx="2" />
      </>
    ),
    table: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 10h18M3 15h18M9 4v16" />
      </>
    ),
    infographic: (
      <>
        <path d="M5 20V14" />
        <path d="M12 20V8" />
        <path d="M19 20V4" />
        <path d="M3 20h18" />
      </>
    ),
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[mode]}
    </svg>
  )
}

const VIEW_LABELS: Record<ViewMode, string> = {
  cards: 'کارت زیبا',
  table: 'جدولی',
  infographic: 'اینفوگرافیک',
}

/* نشان مونوگرام درس — چهار ترکیب رنگی رویایی، چرخشی بر اساس ترتیب */
const EMBLEM_VARIANTS = ['v1', 'v2', 'v3', 'v4']

function emblemText(title: string): string {
  const word = (title || 'درس').trim().split(/\s+/)[0] || 'درس'
  return word.slice(0, 2)
}

/** نرمال‌سازی متن فارسی برای جستجو — ZWNJ، ی/ك عربی، ارقام و فاصله‌ها */
function faNorm(text: string): string {
  return (text || '')
    .replace(/\u200c/g, ' ')
    .replace(/[يى]/g, 'ی')
    .replace(/[ك]/g, 'ک')
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

export default function Courses() {
  const { user } = useAuth()
  const [courses, setCourses] = useState<Course[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<ViewMode>(loadView)
  const [query, setQuery] = useState('')

  useEffect(() => {
    document.title = 'درس‌های من | دانشجو۳۶۰'
  }, [])

  useEffect(() => {
    let alive = true
    api
      .get<Course[]>(`/courses${qs({})}`)
      .then((rows) => {
        if (alive) setCourses(rows || [])
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'خطا در دریافت درس‌ها')
      })
    return () => {
      alive = false
    }
  }, [])

  const changeView = (mode: ViewMode) => {
    setView(mode)
    try {
      localStorage.setItem(VIEW_KEY, mode)
    } catch {
      /* بدون localStorage هم حالت در همین نشست کار می‌کند */
    }
  }

  const summary = useMemo(() => {
    const rows = courses || []
    return {
      total: rows.length,
      enrolled: rows.filter((c) => c.enrolled).length,
      staff: rows.filter((c) => STAFF_COURSE_ROLES.includes(c.my_role)).length,
      credits: rows.reduce((acc, c) => acc + (c.credits || 0), 0),
    }
  }, [courses])

  const maxCredits = useMemo(
    () => Math.max(1, ...(courses || []).map((c) => c.credits || 0)),
    [courses],
  )

  /** جستجوی درس‌ها — بر اساس عنوان، کد، گروه/دانشکده و ترم (فارسی‌آگاه) */
  const filtered = useMemo(() => {
    const q = faNorm(query)
    if (!q) return courses || []
    return (courses || []).filter((c) =>
      [c.title, c.code, c.department, c.term, c.my_role]
        .some((field) => field && faNorm(String(field)).includes(q)),
    )
  }, [courses, query])

  if (error) return <div className="error-box">{error}</div>
  if (courses === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت درس‌ها…
      </div>
    )
  }
  if (courses.length === 0) {
    return (
      <div className="empty-box">
        <strong>درسی یافت نشد</strong>
        هنوز درسی به شما اختصاص داده نشده یا در درسی ثبت‌نام نکرده‌اید.
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>درس‌های من</h1>
          <div className="subtitle">
            {user ? `${user.full_name} عزیز، خوش آمدید.` : ''} حالت نمایش دلخواه‌تان را انتخاب کنید و وارد فضای درس شوید.
          </div>
        </div>
        <div className="view-switcher" role="group" aria-label="حالت نمایش درس‌ها">
          {ALLOWED_VIEWS.map((mode) => (
            <button
              key={mode}
              type="button"
              className={`view-btn${view === mode ? ' active' : ''}`}
              aria-pressed={view === mode}
              onClick={() => changeView(mode)}
            >
              <ViewIcon mode={mode} />
              <span>{VIEW_LABELS[mode]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* جستجوی درس‌ها (v3.9.0) — فیلتر زنده روی عنوان/کد/گروه/ترم */}
      <div className="courses-search-row">
        <div className="courses-search">
          <svg className="search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input
            className="input search-input"
            type="search"
            placeholder="جستجوی درس: عنوان، کد، گروه یا ترم…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="جستجوی درس"
          />
          {query && (
            <button type="button" className="search-clear" aria-label="پاک‌کردن جستجو"
                    onClick={() => setQuery('')}>✕</button>
          )}
        </div>
        {query && (
          <div className="search-count muted">
            {filtered.length > 0
              ? `${filtered.length.toLocaleString('fa-IR')} درس از ${courses.length.toLocaleString('fa-IR')} یافت شد`
              : 'درسی با این عبارت یافت نشد'}
          </div>
        )}
      </div>

      {query && filtered.length === 0 && (
        <div className="empty-box">
          <strong>نتیجه‌ای برای «{query}» یافت نشد</strong>
          عبارت کوتاه‌تری امتحان کنید یا جستجو را پاک کنید — همهٔ{' '}
          {courses.length.toLocaleString('fa-IR')} درس شما سر جایشان هستند.
          <div className="btn-row" style={{ marginTop: 10 }}>
            <button type="button" className="btn btn-sm" onClick={() => setQuery('')}>
              نمایش همهٔ درس‌ها
            </button>
          </div>
        </div>
      )}

      {view === 'cards' && filtered.length > 0 && (
        <div className="grid-cards cards-v2">
          {filtered.map((c, i) => (
            <Link key={c.id} className="course-card course-card-v2" to={`/course/${c.id}`}>
              <div className="card-v2-head">
                <span className={`emblem ${EMBLEM_VARIANTS[i % 4]}`}>{emblemText(c.title)}</span>
                <div className="card-v2-titlebox">
                  <h3>{c.title}</h3>
                  <span className="code-chip">{c.code}</span>
                </div>
              </div>
              <div className="course-meta">
                {c.term && <span>ترم {c.term}</span>}
                {c.department && <span>{c.department}</span>}
                {c.credits ? <span>{c.credits} واحد</span> : null}
              </div>
              <div className="badge-row">
                <span className="badge badge-info">{roleLabel(c.my_role)}</span>
                {c.enrolled ? <span className="badge badge-success">ثبت‌نام‌شده</span> : null}
                {c.syllabus_status ? <StatusBadge status={c.syllabus_status} /> : null}
              </div>
              <div className="card-v2-go">ورود به فضای درس ←</div>
            </Link>
          ))}
        </div>
      )}

      {view === 'table' && filtered.length > 0 && (
        <div className="table-wrap">
          <table className="table courses-table">
            <thead>
              <tr>
                <th>درس</th>
                <th>ترم</th>
                <th>دانشکده</th>
                <th>واحد</th>
                <th>نقش شما</th>
                <th>سرفصل</th>
                <th>ثبت‌نام</th>
                <th aria-label="عمل" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link className="table-course-link" to={`/course/${c.id}`}>{c.title}</Link>
                    <div className="cell-code">{c.code}</div>
                  </td>
                  <td>{c.term || '—'}</td>
                  <td>{c.department || '—'}</td>
                  <td>{c.credits ?? '—'}</td>
                  <td><span className="badge badge-info">{roleLabel(c.my_role)}</span></td>
                  <td>{c.syllabus_status ? <StatusBadge status={c.syllabus_status} /> : '—'}</td>
                  <td>
                    {c.enrolled ? <span className="enrolled-yes">✓</span> : <span className="cell-muted">—</span>}
                  </td>
                  <td>
                    <Link className="btn btn-sm table-go-btn" to={`/course/${c.id}`}>ورود</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {view === 'infographic' && filtered.length > 0 && (
        <div className="infographic">
          <div className="info-summary">
            <div className="summary-tile">
              <div className="summary-num">{summary.total}</div>
              <div className="summary-label">درس این ترم</div>
            </div>
            <div className="summary-tile accent">
              <div className="summary-num">{summary.enrolled}</div>
              <div className="summary-label">ثبت‌نام‌شده</div>
            </div>
            <div className="summary-tile warm">
              <div className="summary-num">{summary.staff}</div>
              <div className="summary-label">نقش استادی/دستیاری</div>
            </div>
            <div className="summary-tile deep">
              <div className="summary-num">{summary.credits}</div>
              <div className="summary-label">مجموع واحدها</div>
            </div>
          </div>

          <div className="info-list">
            {filtered.map((c, i) => (
              <Link key={c.id} className="info-banner" to={`/course/${c.id}`}>
                <span className={`emblem ${EMBLEM_VARIANTS[i % 4]}`}>{emblemText(c.title)}</span>
                <div className="info-main">
                  <h3>{c.title}</h3>
                  <div className="info-meta">
                    <span className="code-chip">{c.code}</span>
                    {c.term && <span>ترم {c.term}</span>}
                    {c.department && <span>{c.department}</span>}
                  </div>
                  <div className="info-meter-row">
                    <div className="info-meter" aria-hidden="true">
                      <span style={{ width: `${Math.max(14, Math.round(((c.credits || 0) / maxCredits) * 100))}%` }} />
                    </div>
                    <div className="info-meter-label">{c.credits ?? '—'} واحد</div>
                  </div>
                </div>
                <div className="info-side">
                  <span className="badge badge-info">{roleLabel(c.my_role)}</span>
                  {c.enrolled ? <span className="badge badge-success">ثبت‌نام‌شده</span> : null}
                  {c.syllabus_status ? <StatusBadge status={c.syllabus_status} /> : null}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
