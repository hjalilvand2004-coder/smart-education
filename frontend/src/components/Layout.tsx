import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Course } from '../api'
import { GLOBAL_ADMIN_ROLES, STAFF_COURSE_ROLES, useAuth, hasAnyStaffCourse } from '../auth'
import { roleLabel } from './StatusBadge'
import ThemeToggle from './ThemeToggle'

function Icon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    today: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" />
      </>
    ),
    courses: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </>
    ),
    studio: (
      <>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
      </>
    ),
    quizzes: (
      <>
        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
        <rect x="8" y="2" width="8" height="4" rx="1" />
        <path d="m9 14 2 2 4-4" />
      </>
    ),
    tutor: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
    plan: (
      <>
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <path d="M16 2v4M8 2v4M3 10h18" />
      </>
    ),
    map: (
      <>
        <circle cx="6" cy="6" r="3" />
        <circle cx="18" cy="8" r="3" />
        <circle cx="11" cy="18" r="3" />
        <path d="M8.5 7.2 15 7.8M7.5 8.6l2.4 6.6M14 10l-1.7 5.2" />
      </>
    ),
    clinic: (
      <>
        <path d="M8 3v7c0 2-3 2-3 4v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5c0-2-3-2-3-4V3" />
        <path d="M8 3h8M10 15h4" />
      </>
    ),
    teach: (
      <>
        <circle cx="9" cy="7" r="3" />
        <path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
        <path d="M16 3.5a3 3 0 0 1 0 7M19 21v-2a4 4 0 0 0-2-3.5" />
      </>
    ),
    exam: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    actions: (
      <>
        <path d="M4 12h6M4 12l3-3M4 12l3 3" />
        <path d="M13 6h7M13 12h7M13 18h7" />
      </>
    ),
    admin: (
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1 1 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
    ),
    integration: (
      <>
        <path d="M9 17H7A5 5 0 0 1 7 7h2" />
        <path d="M15 7h2a5 5 0 1 1 0 10h-2" />
        <line x1="8" y1="12" x2="16" y2="12" />
      </>
    ),
    reports: (
      <>
        <path d="M18 20V10" />
        <path d="M12 20V4" />
        <path d="M6 20v-6" />
      </>
    ),
    focus: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="3" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    unique: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        <path d="M9 7h7M9 11h7" />
      </>
    ),
    split: (
      <>
        <circle cx="6" cy="6" r="2.5" />
        <circle cx="6" cy="18" r="2.5" />
        <circle cx="18" cy="12" r="2.5" />
        <path d="M8.2 7.5 15.8 11M8.2 16.5 15.8 13" />
      </>
    ),
    syllabus: (
      <>
        <path d="M4 4h16v16H4z" />
        <path d="M8 8h8M8 12h8M8 16h5" />
      </>
    ),
    points: (
      <>
        <path d="m12 3 2.7 5.5 6.3.9-4.5 4.4 1 6.2-5.5-3-5.5 3 1-6.2L3 9.4l6.3-.9L12 3z" />
      </>
    ),
    sync: (
      <>
        <path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" />
        <path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" />
        <path d="M21 3v5h-5M3 21v-5h5" />
      </>
    ),
    logout: (
      <>
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <path d="m16 17 5-5-5-5" />
        <path d="M21 12H9" />
      </>
    ),
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  )
}

interface NavItem {
  to: string
  label: string
  icon: string
}

/** گروه سایدبار (v3.5.1): با کلیک باز می‌شود و بخش فعال به‌طور خودکار باز می‌ماند */
interface NavGroup {
  key: string
  label: string
  icon: string
  match: RegExp
  items: NavItem[]
}

type NavEntry = NavItem | NavGroup

const isGroup = (e: NavEntry): e is NavGroup => 'items' in e

/** لایه بصری هر مسیر: کشف (رویایی) / تمرکز (آرام) / تحلیل (دقیق) */
function layerFor(pathname: string): 'discovery' | 'focus' | 'analysis' {
  if (pathname.startsWith('/quiz/')) return 'focus'
  if (/\/learn|\/content\//.test(pathname)) return 'focus'
  if (/\/today|\/map$|\/map\?/.test(pathname) || pathname === '/today') return 'discovery'
  if (/\/reports|\/admin|\/actions|\/smart/.test(pathname)) return 'analysis'
  return 'discovery'
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [courses, setCourses] = useState<Course[]>([])
  const [focusMode, setFocusMode] = useState(false)
  // درس فعال از نشانی فعلی (فقط در حافظه، بدون localStorage اضافی)
  const [activeCourseId, setActiveCourseId] = useState<string | null>(null)
  // وضعیت باز/بسته گروه‌های سایدبار — گروه فعال خودکار باز می‌شود
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})

  // فهرست درس‌ها برای تعیین درس پیش‌فرض لینک‌های درس‌محور
  useEffect(() => {
    let alive = true
    api
      .get<Course[]>('/courses')
      .then((rows) => {
        if (alive) setCourses(rows || [])
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [])

  // درس فعال از نشانی فعلی به‌خاطر سپرده می‌شود
  useEffect(() => {
    const match = location.pathname.match(/\/(?:course|studio)\/([0-9a-fA-F-]{8,})/)
    if (match) setActiveCourseId(match[1])
  }, [location.pathname])

  // لایه بصری + حالت تمرکز روی body — تزئینات در محیط مطالعه/آزمون حذف می‌شوند
  useEffect(() => {
    document.body.dataset.layer = layerFor(location.pathname)
    document.body.classList.toggle('focus-mode', focusMode)
    return () => {
      document.body.classList.remove('focus-mode')
    }
  }, [location.pathname, focusMode])

  const defaultCourseId = activeCourseId && courses.some((c) => c.id === activeCourseId)
    ? activeCourseId
    : courses[0]?.id ?? null

  const staffCourseId = useMemo(() => {
    if (!user || !hasAnyStaffCourse(user)) return null
    if (GLOBAL_ADMIN_ROLES.includes(user.role)) return defaultCourseId
    const staffCourse = courses.find((c) => STAFF_COURSE_ROLES.includes(c.my_role))
    return staffCourse?.id ?? defaultCourseId
  }, [user, courses, defaultCourseId])

  const itemActive = (to: string) => {
    const base = to.split('?')[0]
    const path = location.pathname
    return path === base || path.startsWith(`${base}/`) || path.startsWith(`${base}?`)
  }

  /** ساختار دسته‌بندی‌شدهٔ ناوبری (v3.5.1) — آیتم مستقل یا گروه بازشدنی */
  const navStructure: NavEntry[] = useMemo(() => {
    const entries: NavEntry[] = [
      { to: '/today', label: 'امروزِ من', icon: 'today' },
      { to: '/courses', label: 'درس‌ها', icon: 'courses' },
    ]
    if (defaultCourseId) {
      entries.push({
        key: 'learn',
        label: 'یادگیری هوشمند',
        icon: 'tutor',
        match: /\/learn|\/map(\?|$)|error-clinic|teach-back|exam-prep|\/plan(\?|$)|\/smart/,
        items: [
          { to: `/course/${defaultCourseId}/learn`, label: 'محیط یادگیری', icon: 'tutor' },
          { to: `/course/${defaultCourseId}/map`, label: 'نقشه مفاهیم', icon: 'map' },
          { to: `/me/error-clinic?course_id=${defaultCourseId}`, label: 'کلینیک خطا', icon: 'clinic' },
          { to: `/course/${defaultCourseId}/teach-back`, label: 'به من یاد بده', icon: 'teach' },
          { to: `/course/${defaultCourseId}/exam-prep`, label: 'آمادگی آزمون', icon: 'exam' },
          { to: `/course/${defaultCourseId}/plan`, label: 'برنامه مطالعه', icon: 'plan' },
          { to: `/course/${defaultCourseId}/smart`, label: 'ابزارهای هوشمند', icon: 'integration' },
        ],
      })
      entries.push({
        key: 'quiz',
        label: 'آزمون و سنجش هوشمند',
        icon: 'quizzes',
        match: /\/quizzes|\/mastery/,
        items: [
          { to: `/course/${defaultCourseId}/quizzes`, label: 'کوییز‌ها و آزمون‌ها', icon: 'quizzes' },
          { to: `/course/${defaultCourseId}/mastery`, label: 'سنجش تسلط', icon: 'focus' },
        ],
      })
    }
    if (staffCourseId) {
      entries.push({
        key: 'content',
        label: 'تولید محتوا و تدریس',
        icon: 'studio',
        match: /\/studio|\/actions|\/points/,
        items: [
          { to: `/studio/${staffCourseId}`, label: 'استودیو محتوا', icon: 'studio' },
          { to: `/course/${staffCourseId}/actions`, label: 'اقدام‌های استاد', icon: 'actions' },
          { to: '/points', label: 'امتیاز اساتید', icon: 'points' },
        ],
      })
    }
    if (user && user.role !== 'STUDENT') {
      entries.push({
        key: 'mdm',
        label: 'اطلاعات پایه (پایه‌یار۳۶۰)',
        icon: 'unique',
        match: /\/masterdata/,
        items: [
          { to: '/masterdata/unique', label: 'دروس یکتا', icon: 'unique' },
          { to: '/masterdata/split', label: 'دروس تفکیکی', icon: 'split' },
          { to: '/masterdata/syllabus', label: 'سرفصل دروس', icon: 'syllabus' },
        ],
      })
      const adminItems: NavItem[] = GLOBAL_ADMIN_ROLES.includes(user.role)
        ? [{ to: '/admin', label: 'پنل مدیریت', icon: 'admin' }]
        : []
      entries.push({
        key: 'integration',
        label: 'یکپارچه‌سازی و مدیریت',
        icon: 'integration',
        match: /\/programyar|\/payehyar|\/admin/,
        items: [
          { to: '/programyar', label: 'برنامه‌یار۳۶۰', icon: 'integration' },
          { to: '/payehyar', label: 'همگام‌سازی پایه‌یار', icon: 'sync' },
          ...adminItems,
        ],
      })
      entries.push({ to: '/reports', label: 'گزارش‌ها', icon: 'reports' })
    }
    return entries
  }, [user, staffCourseId, defaultCourseId])

  // کلید گروه حاوی مسیر فعال — برای بازشدن خودکار
  const activeGroupKey = useMemo(() => {
    for (const e of navStructure) {
      if (isGroup(e) && e.items.some((it) => itemActive(it.to))) return e.key
    }
    return null
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navStructure, location.pathname])

  // گروه فعال همیشه باز می‌ماند
  useEffect(() => {
    if (activeGroupKey) {
      setOpenGroups((prev) => (prev[activeGroupKey] ? prev : { ...prev, [activeGroupKey]: true }))
    }
  }, [activeGroupKey])

  const onLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const renderLink = (item: NavItem) => (
    <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
      <Icon name={item.icon} />
      <span>{item.label}</span>
    </NavLink>
  )

  /** سایدبار دسکتاپ: آیتم‌های مستقل + گروه‌های بازشدنی */
  const sidebarNav = (
    <>
      {navStructure.map((entry) =>
        isGroup(entry) ? (
          <div key={entry.key} className="nav-group">
            <button
              type="button"
              className={`nav-group-header${activeGroupKey === entry.key ? ' active' : ''}`}
              onClick={() => setOpenGroups((p) => ({ ...p, [entry.key]: !p[entry.key] }))}
              aria-expanded={!!openGroups[entry.key]}
            >
              <Icon name={entry.icon} />
              <span>{entry.label}</span>
              <svg
                className={`chev${openGroups[entry.key] ? ' open' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="m6 9 6 6 6-6" />
              </svg>
            </button>
            {openGroups[entry.key] && (
              <div className="nav-group-items">{entry.items.map(renderLink)}</div>
            )}
          </div>
        ) : (
          renderLink(entry)
        ),
      )}
    </>
  )

  /** ناوبری موبایل: همهٔ آیتم‌ها به‌صورت تخت و اسکرول‌شونده (گروه‌ها باز می‌شوند) */
  const flatItems: NavItem[] = navStructure.flatMap((e) => (isGroup(e) ? e.items : [e]))

  const userChip = user ? (
    <div className="user-chip">
      <div className="user-name">{user.full_name}</div>
      <div className="user-role">{roleLabel(user.role)}</div>
    </div>
  ) : null

  return (
    <div className="app-shell">
      {/* سحابی رصدخانه — در لایه تمرکز حذف می‌شود */}
      <div className="aurora" aria-hidden="true">
        <i className="b1" />
        <i className="b2" />
        <i className="b3" />
        <i className="b4" />
      </div>
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand">
            <span className="brand-mark">360</span>
            <span>
              دانشجو۳۶۰
              <span className="brand-sub">رصدخانه یادگیری هوشمند</span>
            </span>
          </div>
          <ThemeToggle />
        </div>
        <nav aria-label="ناوبری اصلی">{sidebarNav}</nav>
        <div className="sidebar-footer">
          {userChip}
          <button type="button" className="btn btn-sm" onClick={onLogout}>
            <Icon name="logout" />
            خروج
          </button>
          <div className="sidebar-version">🌌 نسخه ۳.۵.۱ — سایدبار دسته‌بندی‌شده ✨</div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-row">
            <div className="brand">
              <span className="brand-mark">360</span>
              <span>
                دانشجو۳۶۰
                <span className="brand-sub">رصدخانه یادگیری هوشمند</span>
              </span>
            </div>
            <div className="topbar-actions">
              <ThemeToggle />
              <button
                type="button"
                className={`btn btn-sm${focusMode ? ' btn-primary' : ''}`}
                onClick={() => setFocusMode((v) => !v)}
                aria-pressed={focusMode}
                title="حالت تمرکز: حذف تزئینات و منوها"
              >
                <Icon name="focus" />
                {focusMode ? 'خروج از تمرکز' : 'حالت تمرکز'}
              </button>
              <button type="button" className="btn btn-sm" onClick={onLogout}>
                <Icon name="logout" />
                خروج
              </button>
            </div>
          </div>
          <nav className="topnav" aria-label="ناوبری موبایل">
            {flatItems.map(renderLink)}
          </nav>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
