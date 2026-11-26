import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { MsuAgentConnectionView, MsuAgentTestResult } from '../api'
import { notifyMsuAgentChanged } from '../utils/msuAgent'

/**
 * کارت تنظیمات دستیار هوشمند «دانشگاه هوشمند من» در پنل مدیریت (v3.11.0).
 * اتصال به هستهٔ عامل (widget.js نسخهٔ 1.2.0): آدرس، مبدأ، رنگ‌ها، موقعیت،
 * توکن دانشجوی صادرشده از هسته و روشن/خاموش؛ پس از ذخیره، ویجت در همهٔ
 * صفحات بی‌درنگ تازه می‌شود (رخداد msu-agent-config-changed).
 */
export default function MsuAgentSettings() {
  const [conn, setConn] = useState<MsuAgentConnectionView | null>(null)
  const [baseUrl, setBaseUrl] = useState('')
  const [origin, setOrigin] = useState('student360')
  const [accent, setAccent] = useState('#7c3aed')
  const [accent2, setAccent2] = useState('#5b21b6')
  const [position, setPosition] = useState<'br' | 'bl'>('br')
  const [enabled, setEnabled] = useState(true)
  const [token, setToken] = useState('')
  const [test, setTest] = useState<MsuAgentTestResult | null>(null)
  const [busy, setBusy] = useState<'save' | 'test' | null>(null)
  const [msg, setMsg] = useState('')
  const [msgOk, setMsgOk] = useState(true)

  useEffect(() => {
    document.title = 'پنل مدیریت | دانشجو۳۶۰'
    api.get<MsuAgentConnectionView>('/integration/msu-agent/connection')
      .then((v) => {
        setConn(v)
        setBaseUrl(v.base_url)
        setOrigin(v.origin)
        setAccent(v.accent)
        setAccent2(v.accent2)
        setPosition(v.position)
        setEnabled(v.enabled)
      })
      .catch(() => setMsg('تنظیمات دستیار بارگذاری نشد — نقش مدیر لازم است.'))
  }, [])

  const runTest = useCallback(async () => {
    setBusy('test')
    setMsg('')
    setTest(null)
    try {
      const r = await api.post<MsuAgentTestResult>('/integration/msu-agent/test-connection',
        baseUrl ? { base_url: baseUrl } : {})
      setTest(r)
      setMsgOk(r.ok)
      setMsg(r.ok ? 'اتصال به هستهٔ عامل برقرار است.' : 'اتصال کامل نشد — گام‌ها را ببینید.')
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? e.message : 'تست اتصال ناموفق بود.')
    } finally {
      setBusy(null)
    }
  }, [baseUrl])

  const save = useCallback(async () => {
    setBusy('save')
    setMsg('')
    try {
      const v = await api.put<MsuAgentConnectionView>('/integration/msu-agent/connection', {
        base_url: baseUrl,
        origin,
        accent,
        accent2,
        position,
        enabled,
        // توکن خالی یعنی بدون تغییر؛ «-» یعنی پاک‌کردن
        ...(token === '-' ? { token: '' } : token.trim() ? { token: token.trim() } : {}),
      })
      setConn(v)
      setToken('')
      setMsgOk(true)
      setMsg('ذخیره شد — ویجت در همهٔ صفحات با تنظیمات جدید تازه می‌شود.')
      notifyMsuAgentChanged()
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? e.message : 'ذخیرهٔ تنظیمات ناموفق بود.')
    } finally {
      setBusy(null)
    }
  }, [baseUrl, origin, accent, accent2, position, enabled, token])

  const srcBadge = (s: string) =>
    s === 'DB' ? 'badge-success' : s === 'ENV' ? 'badge-warn' : 'badge-neutral'

  return (
    <div className="card" id="msu-agent">
      <div className="card-title">
        <h2>دستیار هوشمند «دانشگاه هوشمند من»</h2>
        {conn && <span className={`badge ${srcBadge(conn.base_url_source)}`}>
          منبع: {conn.base_url_source === 'DB' ? 'دیتابیس' : conn.base_url_source === 'DEFAULT' ? 'پیش‌فرض' : conn.base_url_source}
        </span>}
        {conn && <span className={`badge ${enabled ? 'badge-success' : 'badge-neutral'}`}>
          {enabled ? 'ویجت روشن' : 'ویجت خاموش'}
        </span>}
      </div>
      <p className="muted">
        اتصال به هستهٔ عامل سامانهٔ دانشگاه هوشمند من: ویجت شناور گفت‌وگو در همهٔ صفحاتِ
        دانشجو۳۶۰ رندر می‌شود و آخرین وضعیت دانشجو (درس‌ها، مهارت‌ها، کارآموزی، درخواست‌ها و مالی)
        را از هستهٔ عامل احصا می‌کند. پیش‌فرض هستهٔ عامل روی همان میزبان است (localhost:8000).
      </p>
      <div className="form-grid" style={{ marginTop: 10 }}>
        <div className="form-item">
          <label className="label" htmlFor="msu-url">آدرس هستهٔ عامل</label>
          <input id="msu-url" className="input" dir="ltr" value={baseUrl}
                 onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:8000" />
        </div>
        <div className="form-item">
          <label className="label" htmlFor="msu-origin">شناسهٔ سامانهٔ میزبان (origin)</label>
          <input id="msu-origin" className="input" dir="ltr" value={origin}
                 onChange={(e) => setOrigin(e.target.value)} placeholder="student360" />
        </div>
        <div className="form-item">
          <label className="label" htmlFor="msu-accent">رنگ اصلی ویجت</label>
          <input id="msu-accent" className="input" type="color" value={accent}
                 onChange={(e) => setAccent(e.target.value)} style={{ height: 38 }} />
        </div>
        <div className="form-item">
          <label className="label" htmlFor="msu-accent2">رنگ دوم (گرادیان)</label>
          <input id="msu-accent2" className="input" type="color" value={accent2}
                 onChange={(e) => setAccent2(e.target.value)} style={{ height: 38 }} />
        </div>
        <div className="form-item">
          <label className="label" htmlFor="msu-pos">موقعیت ویجت</label>
          <select id="msu-pos" className="select" value={position}
                  onChange={(e) => setPosition(e.target.value === 'bl' ? 'bl' : 'br')}>
            <option value="br">پایین‌راست</option>
            <option value="bl">پایین‌چپ</option>
          </select>
        </div>
        <div className="form-item">
          <label className="label" htmlFor="msu-token">توکن دستیار (اختیاری)</label>
          <input id="msu-token" className="input" dir="ltr" type="password" value={token}
                 onChange={(e) => setToken(e.target.value)}
                 placeholder={conn?.has_token ? (conn.token_masked ?? '●●●') : 'JWT صادرشده از هستهٔ عامل'} />
          <div className="hint">
            توکن دانشجوی «هستهٔ عامل» است، نه توکن همین سامانه. برای پاک‌کردن، «-» بنویسید.
            {conn?.has_token && conn.token_source === 'ENV' && ' (فعلاً از متغیر محیطی)'}
          </div>
        </div>
        <div className="form-item">
          <label className="label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            نمایش ویجت در همهٔ صفحات
          </label>
        </div>
      </div>

      {test && (
        <div className="hint" style={{ margin: '8px 0' }}>
          {test.steps.map((s, i) => (
            <div key={i}>
              {s.ok ? '✅' : '⚠'} <b>{s.step}</b> — {s.detail}
            </div>
          ))}
        </div>
      )}
      {msg && <div className={msgOk ? 'success-box' : 'error-box'}>{msg}</div>}

      <div className="btn-row" style={{ marginTop: 10 }}>
        <button className="btn" type="button" onClick={runTest} disabled={busy !== null}>
          {busy === 'test' ? 'در حال تست…' : 'تست اتصال'}
        </button>
        <button className="btn btn-primary" type="button" onClick={save} disabled={busy !== null}>
          {busy === 'save' ? 'در حال ذخیره…' : 'ذخیره و اعمال'}
        </button>
      </div>
    </div>
  )
}
