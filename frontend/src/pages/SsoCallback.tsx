import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, setStoredUser, setToken } from '../api'

const ERROR_MESSAGES: Record<string, string> = {
  state: 'نشست ورود یکگانه نامعتبر یا منقضی شد؛ دوباره تلاش کنید.',
  exchange: 'تبادل توکن با پرتال SSO ناموفق بود؛ تنظیمات Client ID/Secret را بررسی کنید.',
  no_sub: 'هویت دریافتی از پرتال SSO معتبر نیست.',
  pending: 'حساب شما در پرتال مرکزی موجود است اما در سامانه در انتظار تایید مدیر است.',
}

/** صفحه بازگشت جریان SSO: تبادل بلیت یک‌بارمصرف با توکن سامانه و ورود. */
export default function SsoCallback() {
  const [status, setStatus] = useState<'working' | 'done' | 'error'>('working')
  const [message, setMessage] = useState('در حال تکمیل ورود یکگانه…')

  useEffect(() => {
    document.title = 'ورود یکگانه | دانشجو۳۶۰'
    const params = new URLSearchParams(window.location.search)
    const ticket = params.get('ticket')
    const error = params.get('error')

    if (!ticket) {
      setStatus('error')
      setMessage(ERROR_MESSAGES[error || ''] || 'ورود یکگانه ناتمام ماند.')
      return
    }
    api
      .post<{ access_token: string; user: unknown }>('/auth/sso/exchange', { ticket })
      .then((res) => {
        setToken(res.access_token)
        setStoredUser(res.user as never)
        setStatus('done')
        setMessage('ورود موفق — در حال انتقال به سامانه…')
        window.setTimeout(() => window.location.replace('/courses'), 400)
      })
      .catch((err: unknown) => {
        setStatus('error')
        setMessage(err instanceof Error && err.message ? err.message : 'تبادل بلیت ناموفق بود.')
      })
  }, [])

  return (
    <div className="login-page">
      <div className="login-card" style={{ textAlign: 'center' }}>
        <div className="brand" style={{ justifyContent: 'center' }}>
          <span className="brand-mark">360</span>
          <span>دانشجو۳۶۰</span>
        </div>
        <div className="login-sub">ورود یکگانه (SSO)</div>
        {status === 'working' && (
          <div className="center-note">
            <div className="spinner" />
            {message}
          </div>
        )}
        {status === 'done' && <div className="success-box">{message}</div>}
        {status === 'error' && <div className="error-box"><span>{message}</span></div>}
        <div className="btn-row" style={{ justifyContent: 'center', marginTop: 14 }}>
          <Link className="btn" to="/login">بازگشت به صفحه ورود</Link>
        </div>
      </div>
    </div>
  )
}
