import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth'
import HelpButton from '../components/HelpButton'

interface SsoConfig {
  enabled: boolean
  provider: string
  message: string
}

const DEMO_PASSWORD = 'Pass1234!'

/** حساب‌های نمونه محیط آزمایشی — با یک کلیک فرم پر می‌شود. */
const DEMO_ACCOUNTS = [
  { username: 'student.sara', label: '🎓 سارا — دانشجو' },
  { username: 'prof.rezaei', label: '👩‍🏫 رضایی — استاد' },
  { username: 'edu.admin', label: '🏫 مدیر آموزشی' },
  { username: 'tech.admin', label: '🛠 مدیر فنی' },
]

const IconUser = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
  </svg>
)

const IconLock = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
)

const IconEye = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
  </svg>
)

const IconEyeOff = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
)

const FEATURES = [
  {
    title: 'استخراج خودکار سرفصل',
    desc: 'از متن سیلابس تا گراف مفاهیم، بدون ورود دستی',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </svg>
    ),
  },
  {
    title: 'محتوای درسی هوشمند',
    desc: 'طرح درس، تولید و انتشار نسخه‌های بازبینی‌شده',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 7.7l5.4-.8z" />
      </svg>
    ),
  },
  {
    title: 'ارزیابی تطبیقی و تسلط',
    desc: 'بانک سؤال، آزمون سازگار و تحلیل تسلط مفهومی',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 3v18h18" /><path d="M7 14l4-4 3 3 5-6" />
      </svg>
    ),
  },
  {
    title: 'استاد هوشمند ۲۴/۷',
    desc: 'گفتگوی آموزشی با ارجاع به منابع درس',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z" />
      </svg>
    ),
  },
]

/** صفحه ورود: حساب محلی، ثبت‌نام خودخدمت (با گردش‌کار تایید) و ورود یکگانه SSO. */
export default function Login() {
  const { user, login, loading } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [regRole, setRegRole] = useState('STUDENT')
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [okMsg, setOkMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [sso, setSso] = useState<SsoConfig | null>(null)

  useEffect(() => {
    document.title = 'ورود | دانشجو۳۶۰ — سامانه یکپارچه یادگیری هوشمند'
    import('../api').then(({ api }) =>
      api.get<SsoConfig>('/auth/sso/config').then(setSso).catch(() => setSso(null)),
    )
  }, [])

  if (!loading && user) return <Navigate to="/courses" replace />

  const fillDemo = (u: string) => {
    setTab('login')
    setUsername(u)
    setPassword(DEMO_PASSWORD)
    setError(null)
    setOkMsg(null)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setOkMsg(null)
    setBusy(true)
    try {
      if (tab === 'login') {
        await login(username.trim(), password)
        navigate('/courses', { replace: true })
      } else {
        const { api } = await import('../api')
        const res = await api.post<{ status: string; message: string }>('/auth/register', {
          username: username.trim(),
          password,
          full_name: fullName.trim(),
          role: regRole,
        })
        setOkMsg(res.message)
        if (res.status === 'ACTIVE') {
          setTab('login')
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('ارتباط با سرور برقرار نشد؛ اتصال اینترنت یا اجرای بک‌اند را بررسی کنید.')
      }
    } finally {
      setBusy(false)
    }
  }

  const startSso = () => {
    window.location.href = '/api/v1/auth/sso/login'
  }

  return (
    <div className="login-page">
      {/* صحنه aurora + ستاره‌ها */}
      <div className="aurora" aria-hidden="true">
        <i className="b1" />
        <i className="b2" />
        <i className="b3" />
      </div>
      <div className="stars" aria-hidden="true">
        {Array.from({ length: 14 }, (_, i) => (
          <span
            key={i}
            className="star"
            style={{
              top: `${(i * 37 + 13) % 92}%`,
              insetInlineStart: `${(i * 53 + 7) % 95}%`,
              animationDelay: `${(i % 7) * 0.5}s`,
            }}
          />
        ))}
      </div>
      <div className="lp-ring" aria-hidden="true" />

      <div className="login-split">
        <div className="login-hero">
          <div className="lp-brand-row">
            <span className="lp-logo">۳۶۰</span>
            <span className="lp-brand-name">دانشجو۳۶۰</span>
          </div>
          <span className="hero-badge">✨ سامانه یکپارچه یادگیری هوشمند</span>
          <h1>سفر یادگیری‌ات را با هوش مصنوعی شروع کن</h1>
          <p className="hero-lead">
            سرفصل‌ها خودکار استخراج می‌شوند، محتوای درسی برای هر موضوع ساخته می‌شود،
            استاد هوشمند همیشه کنارت است و مسیر مطالعه‌ات را شخصی‌سازی می‌کند.
          </p>
          <ul className="lp-features">
            {FEATURES.map((f) => (
              <li key={f.title}>
                <span className="lp-feat-ico">{f.icon}</span>
                <div>
                  <strong>{f.title}</strong>
                  <small>{f.desc}</small>
                </div>
              </li>
            ))}
          </ul>
          <div className="lp-stats">
            <div><b>+۳۰</b><small>سرویس هوشمند</small></div>
            <div><b>۵۰</b><small>جدول داده یکپارچه</small></div>
            <div><b>۱۰۰٪</b><small>آفلاین در نسخه پرتیبل</small></div>
          </div>
        </div>

        <div className="login-card">
          <div className="lp-card-head">
            <span className="lp-logo lp-logo-sm">۳۶۰</span>
            <div>
              <div className="lp-card-title">خوش آمدید 👋</div>
              <div className="lp-card-sub">برای ادامه وارد شوید یا ثبت‌نام کنید</div>
            </div>
          </div>

          <div className="auth-tabs">
            <button type="button" className={`auth-tab${tab === 'login' ? ' active' : ''}`}
                    onClick={() => { setTab('login'); setError(null); setOkMsg(null) }}>
              ورود
            </button>
            <button type="button" className={`auth-tab${tab === 'register' ? ' active' : ''}`}
                    onClick={() => { setTab('register'); setError(null); setOkMsg(null) }}>
              ثبت‌نام
            </button>
          </div>

          <form onSubmit={onSubmit}>
            <div className="lp-field">
              <label className="label" htmlFor="username">نام کاربری</label>
              <span className="lp-ico"><IconUser /></span>
              <input id="username" className="input" value={username}
                     onChange={(e) => setUsername(e.target.value)} autoComplete="username"
                     dir="ltr" placeholder="student.sara" required />
            </div>
            {tab === 'register' && (
              <div className="lp-field">
                <label className="label" htmlFor="fullname">نام و نام‌خانوادگی</label>
                <input id="fullname" className="input" value={fullName}
                       onChange={(e) => setFullName(e.target.value)} required />
              </div>
            )}
            <div className="lp-field">
              <label className="label" htmlFor="password">رمز عبور</label>
              <span className="lp-ico"><IconLock /></span>
              <input id="password" className="input" type={showPass ? 'text' : 'password'}
                     value={password} onChange={(e) => setPassword(e.target.value)}
                     autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                     dir="ltr" placeholder="••••••••" required />
              <button type="button" className="lp-eye" aria-label={showPass ? 'پنهان‌کردن رمز' : 'نمایش رمز'}
                      onClick={() => setShowPass((v) => !v)}>
                {showPass ? <IconEyeOff /> : <IconEye />}
              </button>
            </div>
            {tab === 'register' && (
              <div className="lp-field">
                <label className="label" htmlFor="regrole">نقش درخواستی</label>
                <select id="regrole" className="select" value={regRole} onChange={(e) => setRegRole(e.target.value)}>
                  <option value="STUDENT">دانشجو — فعال‌سازی فوری</option>
                  <option value="PROFESSOR">استاد — پس از تایید مدیر</option>
                  <option value="GROUP_ADMIN">مدیرگروه — پس از تایید مدیر</option>
                </select>
              </div>
            )}
            {error && <div className="error-box"><span>{error}</span></div>}
            {okMsg && <div className="success-box">{okMsg}</div>}
            <button type="submit" className="btn btn-primary btn-block lp-submit" disabled={busy}>
              {busy && <span className="lp-spinner" aria-hidden="true" />}
              {busy ? 'در حال پردازش…' : tab === 'login' ? 'ورود به سامانه' : 'ثبت‌نام'}
            </button>
          </form>

          {tab === 'login' && (
            <div className="lp-demo">
              <span className="lp-demo-label">ورود سریع با حساب نمونه (محیط آزمایشی):</span>
              <div className="lp-demo-chips">
                {DEMO_ACCOUNTS.map((a) => (
                  <button key={a.username} type="button" className="lp-chip"
                          title={a.username}
                          onClick={() => fillDemo(a.username)}>
                    {a.label}
                  </button>
                ))}
              </div>
              <small>
                رمز همه: <code>{DEMO_PASSWORD}</code> — با کلیک روی هر چیپ، فرم خودکار پر می‌شود.
              </small>
            </div>
          )}

          {sso?.enabled && (
            <>
              <div className="sso-divider"><span>یا</span></div>
              <button type="button" className="btn sso-btn btn-block" onClick={startSso}>
                🔐 ورود یکگانه با پرتال مرکزی SSO
              </button>
              <div className="hint" style={{ textAlign: 'center' }}>
                احراز هویت یکپارچه سازمانی ({sso.provider})
              </div>
            </>
          )}
          {sso && !sso.enabled && (
            <div className="inline-alert" style={{ marginTop: 14, fontSize: '0.78rem' }}>
              ورود یکگانه (SSO) هنوز تنظیم نشده است.
            </div>
          )}

          <div className="login-footer">نسخه ۳.۱۲.۰ ✨ مقاطع تحصیلی (کاردانی تا دکترا) + دستیار هوشمند در سمت چپ — در نسخه پرتیبل</div>
        </div>
      </div>
      <HelpButton />
    </div>
  )
}
