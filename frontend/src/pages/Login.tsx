import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../auth'

interface SsoConfig {
  enabled: boolean
  provider: string
  message: string
}

/** صفحه ورود: حساب محلی، ثبت‌نام خودخدمت (با گردش‌کار تایید) و ورود یکگانه SSO. */
export default function Login() {
  const { user, login, loading } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [regRole, setRegRole] = useState('STUDENT')
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
      {/* صحنه رویایی: شفق متحرک + ستاره‌های چشمک‌زن */}
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

      <div className="login-split">
        <div className="login-hero">
          <span className="hero-badge">✨ سامانه یکپارچه یادگیری هوشمند — تم رویایی</span>
          <h1>سفر یادگیری‌ات را با جادوی هوش مصنوعی شروع کن</h1>
          <p className="hero-lead">
            سرفصل‌ها خودکار استخراج می‌شوند، محتوای درسی برای هر موضوع ساخته می‌شود،
            استاد هوشمند همیشه کنارت است و مسیر مطالعه‌ات را شخصی‌سازی می‌کند.
          </p>
          <div className="float-chips">
            <span className="float-chip">📚 استخراج سرفصل</span>
            <span className="float-chip">🪄 تولید محتوای هوشمند</span>
            <span className="float-chip">🎓 استاد ۲۴/۷</span>
            <span className="float-chip">🗺 نقشه مفاهیم</span>
            <span className="float-chip">📈 تسلط مفهومی</span>
          </div>
        </div>

        <div className="login-card">
          <div className="brand">
            <span className="brand-mark">360</span>
            <span>دانشجو۳۶۰</span>
          </div>
          <div className="login-sub">سامانه یکپارچه یادگیری هوشمند</div>

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
          <div className="form-item" style={{ marginBottom: 12 }}>
            <label className="label" htmlFor="username">نام کاربری</label>
            <input id="username" className="input" value={username}
                   onChange={(e) => setUsername(e.target.value)} autoComplete="username" dir="ltr" required />
          </div>
          {tab === 'register' && (
            <div className="form-item" style={{ marginBottom: 12 }}>
              <label className="label" htmlFor="fullname">نام و نام‌خانوادگی</label>
              <input id="fullname" className="input" value={fullName}
                     onChange={(e) => setFullName(e.target.value)} required />
            </div>
          )}
          <div className="form-item" style={{ marginBottom: tab === 'register' ? 12 : 16 }}>
            <label className="label" htmlFor="password">رمز عبور</label>
            <input id="password" className="input" type="password" value={password}
                   onChange={(e) => setPassword(e.target.value)}
                   autoComplete={tab === 'login' ? 'current-password' : 'new-password'} dir="ltr" required />
          </div>
          {tab === 'register' && (
            <div className="form-item" style={{ marginBottom: 16 }}>
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
          <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
            {busy ? 'در حال پردازش…' : tab === 'login' ? 'ورود به سامانه' : 'ثبت‌نام'}
          </button>
        </form>

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

        <div className="demo-hint">
          <strong>حساب‌های نمونه محیط آزمایشی:</strong>
          <div>
            استاد: <code>prof.rezaei</code> — دانشجو: <code>student.sara</code> — مدیر آموزشی: <code>edu.admin</code>
          </div>
          <div>
            رمز همه: <code>Pass1234!</code>
          </div>
        </div>

        <div className="login-footer">نسخه ۲.۹.۰ ✨ طراحی رویایی — اجرا بدون نیاز به نصب پایتون</div>
        </div>
      </div>
    </div>
  )
}
