import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

/** صفحه همگام‌سازی با پایه‌یار۳۶۰ — مرجع حقیقت دروس و سرفصل‌ها.
 *  وضعیت اتصال + آمار رونوشت + اجرای همگام‌سازی کامل/افزایشی + تاریخچه اجراها. */

interface PyProbe {
  base_url: string
  auth_mode: 'API_KEY' | 'DEV_USER' | 'NONE'
  reachable: boolean
  service_title: string | null
  service_version: string | null
  status: string
  hint: string | null
  detail?: string
  required_roles?: string[]
}

interface PyConfig {
  base_url: string
  api_key_set: boolean
  dev_user_set: boolean
  timeout_seconds: number
}

interface PyLog {
  log_id: string
  mode: 'FULL' | 'INCREMENTAL'
  status: 'OK' | 'PARTIAL' | 'FAILED'
  courses_created: number
  courses_updated: number
  up_to_date: number
  syllabus_drafts_created: number
  review_required: number
  warnings: string[] | null
  duration_ms: number | null
  remote_version: string | null
  error_code: string | null
  error_message: string | null
  message: string
  created_at?: string
}

interface PyStatusResp {
  probe: PyProbe
  config: PyConfig
  counts: {
    reference_courses: number
    linked_courses: number
    pending_drafts: number
    review_required_courses: number
  }
  last_log: PyLog | null
  note: string
}

interface PySystemStatus {
  scheduler: {
    enabled: boolean
    interval_seconds: number
    running: boolean
    cycles: number
    last_run_at: string | null
    last_status: string | null
    last_message: string | null
  }
  events: {
    enabled: boolean
    configured: boolean
    exchange: string
    queue: string
    dlq: string
    routing_key: string
    connected: boolean
    processed: number
    duplicates: number
    failed: number
    last_event_at: string | null
  }
  records_counts: Record<string, number>
  extended_domains: string[]
}

interface PyConnView {
  base_url: string
  api_key_masked: string | null
  has_key: boolean
  key_source: 'DB' | 'ENV' | 'NONE'
  base_url_source: 'DB' | 'DEFAULT'
  updated_at: string | null
}

interface PyTestStep {
  name: string
  ok: boolean
  detail: string
  hint: string | null
}

interface PyTestResp {
  ok: boolean
  steps: PyTestStep[]
  summary: string
}

const EXT_DOMAIN_FA: Record<string, string> = {
  professors: 'اساتید',
  classrooms: 'کلاس‌ها',
  'academic-groups': 'گروه‌های آموزشی',
  'reference-sets': 'مجموعه‌های مرجع',
}

const PROBE_BADGE: Record<string, { cls: string; label: string }> = {
  OK: { cls: 'badge badge-success', label: 'اتصال سالم — احراز هویت موفق' },
  NEEDS_API_KEY: { cls: 'badge badge-warn', label: 'نیازمند کلید API' },
  INVALID_API_KEY: { cls: 'badge badge-warn', label: 'کلید API نامعتبر' },
  NEEDS_ROLE: { cls: 'badge badge-warn', label: 'نقش کافی نیست' },
  NEEDS_TENANT: { cls: 'badge badge-warn', label: 'بدون اتصال tenant' },
  UNREACHABLE: { cls: 'badge badge-danger', label: 'سرویس در دسترس نیست' },
}

const LOG_BADGE: Record<string, string> = {
  OK: 'badge badge-success',
  PARTIAL: 'badge badge-warn',
  FAILED: 'badge badge-danger',
}

const fa = (n: number | null | undefined) =>
  (n ?? 0).toLocaleString('fa-IR')

const faTime = (iso?: string) =>
  iso ? new Date(iso).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' }) : '—'

export default function Payehyar() {
  const [status, setStatus] = useState<PyStatusResp | null>(null)
  const [logs, setLogs] = useState<PyLog[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState<'FULL' | 'INCREMENTAL' | null>(null)
  const [lastResult, setLastResult] = useState<PyLog | null>(null)
  const [sys, setSys] = useState<PySystemStatus | null>(null)
  const [extRunning, setExtRunning] = useState(false)
  const [extMsg, setExtMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [conn, setConn] = useState<PyConnView | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [keyInput, setKeyInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testRes, setTestRes] = useState<PyTestResp | null>(null)
  const [connMsg, setConnMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [st, lg] = await Promise.all([
        api.get<PyStatusResp>('/integration/payehyar/status'),
        api.get<{ items: PyLog[] }>('/integration/payehyar/logs?limit=25'),
      ])
      setStatus(st)
      setLogs(lg.items || [])
      try {
        setSys(await api.get<PySystemStatus>('/integration/payehyar/system-status'))
      } catch {
        setSys(null) // نسخه‌های قدیمی‌تر بدون این endpoint
      }
      try {
        const cv = await api.get<PyConnView>('/integration/payehyar/connection')
        setConn(cv)
        setUrlInput((prev) => prev || cv.base_url)
      } catch {
        setConn(null) // نسخه‌های قدیمی‌تر بدون endpoint تنظیمات
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'دریافت وضعیت همگام‌سازی ناموفق بود')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const runSync = async (mode: 'FULL' | 'INCREMENTAL') => {
    setRunning(mode)
    setError(null)
    setLastResult(null)
    try {
      const res = await api.post<PyLog>('/integration/payehyar/sync', { mode })
      setLastResult(res)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'اجرای همگام‌سازی ناموفق بود')
    } finally {
      setRunning(null)
    }
  }

  const runExtendedSync = async () => {
    setExtRunning(true)
    setExtMsg(null)
    try {
      const res = await api.post<{ message: string; courses_created: number; courses_updated: number }>('/integration/payehyar/sync-extended', {})
      setExtMsg(res.message || 'همگام‌سازی دامنه‌های گسترش‌یافته انجام شد.')
      await load()
    } catch (e) {
      setExtMsg(e instanceof Error ? `خطا: ${e.message}` : 'اجرای همگام‌سازی ناموفق بود')
    } finally {
      setExtRunning(false)
    }
  }

  const saveConnection = async () => {
    setSaving(true)
    setConnMsg(null)
    try {
      await api.put<PyConnView>('/integration/payehyar/connection', {
        base_url: urlInput,
        api_key: keyInput === '' ? undefined : keyInput,
      })
      setKeyInput('')
      setConnMsg('تنظیمات ذخیره شد ✓ — از این پس همهٔ همگام‌سازی‌ها با همین کلید انجام می‌شود.')
      await load()
    } catch (e) {
      setConnMsg(e instanceof Error ? `خطا: ${e.message}` : 'ذخیرهٔ تنظیمات ناموفق بود')
    } finally {
      setSaving(false)
    }
  }

  const testConnection = async () => {
    setTesting(true)
    setTestRes(null)
    try {
      const res = await api.post<PyTestResp>('/integration/payehyar/test-connection', {
        base_url: urlInput || undefined,
        api_key: keyInput === '' ? undefined : keyInput,
      })
      setTestRes(res)
      await load()
    } catch (e) {
      setTestRes({
        ok: false,
        steps: [],
        summary: e instanceof Error ? `خطا: ${e.message}` : 'اجرای تست اتصال ناموفق بود',
      })
    } finally {
      setTesting(false)
    }
  }

  const probeBadge = status ? (PROBE_BADGE[status.probe.status] ?? {
    cls: 'badge badge-neutral',
    label: status.probe.status,
  }) : null

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>همگام‌سازی پایه‌یار۳۶۰</h1>
          <div className="subtitle">
            مرجع حقیقت دروس و سرفصل‌ها — واکشی کاتالوگ از سامانه مرکزی و نگهداری «رونوشت همگام‌شده»
          </div>
        </div>
        <button type="button" className="btn btn-sm" onClick={() => void load()} disabled={loading}>
          ↻ به‌روزرسانی وضعیت
        </button>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger-border)', background: 'var(--danger-bg)' }}>
          <strong style={{ color: 'var(--danger-text)' }}>خطا: </strong>
          <span style={{ color: 'var(--danger-text)' }}>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          در حال دریافت وضعیت…
        </div>
      ) : status ? (
        <>
          {/* ---------- کارت اتصال ---------- */}
          <div className="card">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <strong>وضعیت اتصال به سرویس مرجع</strong>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 4 }}>
                  {status.probe.service_title || 'پایه‌یار۳۶۰'}
                  {status.probe.service_version ? ` — نسخه ${status.probe.service_version}` : ''}
                </div>
              </div>
              <span className={probeBadge?.cls}>{probeBadge?.label}</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, marginTop: 12, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              <span>آدرس: <code>{status.config.base_url}</code></span>
              <span>
                احراز هویت: {status.config.api_key_set ? 'کلید API تنظیم شده ✓'
                  : status.config.dev_user_set ? 'کاربر توسعه تنظیم شده ✓'
                    : 'هیچ اعتبارنامه‌ای تنظیم نشده'}
              </span>
            </div>
            {status.probe.status !== 'OK' && status.probe.hint && (
              <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 12, background: 'var(--warn-bg)', border: '1px solid var(--warn-border)', color: 'var(--warn-text)', fontSize: '0.85rem', lineHeight: 1.9 }}>
                <strong>راهنمای اقدام: </strong>
                {status.probe.detail ? `${status.probe.detail} — ` : ''}
                {status.probe.hint}
                {status.probe.required_roles?.length ? (
                  <div style={{ marginTop: 4 }}>نقش‌های لازم: {status.probe.required_roles.join('، ')}</div>
                ) : null}
              </div>
            )}
          </div>

          {/* ---------- تنظیمات و تست اتصال (v3.4.2) ---------- */}
          <div className="card">
            <strong>تنظیمات و تست اتصال</strong>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: '6px 0 12px' }}>
              کلید API را یک‌بار همین‌جا ذخیره کنید — نیازی به فایل .env نیست؛ کلید در
              دیتابیس محلی همین دستگاه نگه داشته می‌شود و بلافاصله اعمال می‌شود.
              {conn?.has_key ? ` کلید فعلی: ${conn.api_key_masked}` : ' کلید فعلی: تنظیم نشده'}
              {conn?.updated_at ? ` — آخرین ذخیره: ${faTime(conn.updated_at)}` : ''}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 560 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                آدرس سرویس پایه‌یار
                <input
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="http://188.212.96.235:8094"
                  dir="ltr"
                  style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--border, #ccc)', background: 'transparent', color: 'inherit' }}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                کلید API (X-API-Key)
                <input
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  type="password"
                  placeholder={conn?.has_key ? 'برای تغییر کلید، مقدار جدید را وارد کنید' : 'pyk_…'}
                  dir="ltr"
                  style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--border, #ccc)', background: 'transparent', color: 'inherit' }}
                />
              </label>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <button type="button" className="btn btn-primary" disabled={saving} onClick={() => void saveConnection()}>
                  {saving ? '⏳ در حال ذخیره…' : '💾 ذخیره تنظیمات'}
                </button>
                <button type="button" className="btn" disabled={testing} onClick={() => void testConnection()}>
                  {testing ? '⏳ در حال تست…' : '🔍 تست اتصال'}
                </button>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  تست با مقادیر همین فیلدها انجام می‌شود؛ اگر خالی باشند با تنظیمات ذخیره‌شده.
                </span>
              </div>
            </div>
            {connMsg && (
              <div style={{ marginTop: 10, fontSize: '0.85rem', color: connMsg.includes('خطا') ? 'var(--danger-text)' : 'var(--success-text)' }}>
                {connMsg}
              </div>
            )}
            {testRes && (
              <div style={{
                marginTop: 12, padding: '10px 12px', borderRadius: 12,
                background: testRes.ok ? 'var(--success-bg)' : 'var(--danger-bg)',
                border: `1px solid ${testRes.ok ? 'var(--success-border)' : 'var(--danger-border)'}`,
                fontSize: '0.86rem', lineHeight: 1.9,
              }}>
                <strong style={{ color: testRes.ok ? 'var(--success-text)' : 'var(--danger-text)' }}>
                  {testRes.ok ? '✓ نتیجهٔ تست: ' : '✗ نتیجهٔ تست: '}
                </strong>
                <span style={{ color: testRes.ok ? 'var(--success-text)' : 'var(--danger-text)' }}>{testRes.summary}</span>
                {testRes.steps.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {testRes.steps.map((s, i) => (
                      <div key={i} style={{ padding: '6px 8px', borderTop: i ? '1px dashed var(--border, #ccc)' : 'none' }}>
                        <strong>{s.ok ? '✓' : '✗'} {s.name}: </strong>
                        <span style={{ color: 'var(--text-muted)' }}>{s.detail}</span>
                        {s.hint && (
                          <div style={{ color: 'var(--warn-text)', fontSize: '0.8rem', marginTop: 2 }}>
                            راهنما: {s.hint}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ---------- آمار رونوشت ---------- */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, margin: '14px 0' }}>
            {[
              { label: 'درس مرجع (رونوشت)', value: status.counts.reference_courses },
              { label: 'درس پیوندشده با مرجع', value: status.counts.linked_courses },
              { label: 'سرفصل در انتظار تأیید', value: status.counts.pending_drafts },
              { label: 'درس نیازمند بررسی', value: status.counts.review_required_courses },
            ].map((t) => (
              <div key={t.label} className="card" style={{ textAlign: 'center', padding: '14px 10px' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--brand-deep)' }}>{fa(t.value)}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>{t.label}</div>
              </div>
            ))}
          </div>

          {/* ---------- زیرساخت خودکار یکپارچگی (سند فنی v3.4.0) ---------- */}
          {sys && (
            <div className="card">
              <strong>زیرساخت خودکار یکپارچگی</strong>
              <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginTop: 8, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                <span>
                  زمان‌بند همگام‌سازی: {sys.scheduler.enabled
                    ? `فعال ✓ (هر ${fa(sys.scheduler.interval_seconds)} ثانیه)`
                    : 'غیرفعال (S360_PAYEHYAR_AUTO_SYNC=true)'}
                  {sys.scheduler.last_run_at ? ` — آخرین اجرا: ${faTime(sys.scheduler.last_run_at)}` : ''}
                </span>
                <span>
                  رویدادهای RabbitMQ: {!sys.events.enabled
                    ? 'غیرفعال (نیازمند اعتبارنامه از مدیر پایه‌یار)'
                    : sys.events.connected ? 'متصل ✓' : 'در انتظار اتصال…'}
                  {sys.events.enabled ? ` — پردازش‌شده: ${fa(sys.events.processed)} | تکراری: ${fa(sys.events.duplicates)} | ناموفق: ${fa(sys.events.failed)}` : ''}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
                {sys.extended_domains.map((d) => (
                  <span key={d} className="badge badge-neutral" style={{ fontSize: '0.75rem' }}>
                    {EXT_DOMAIN_FA[d] || d}: {fa(sys.records_counts[d] ?? 0)}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 12 }}>
                <button type="button" className="btn" disabled={extRunning}
                  onClick={() => void runExtendedSync()}>
                  {extRunning ? '⏳ در حال واکشی…' : '⇄ همگام‌سازی دامنه‌های گسترش‌یافته'}
                </button>
                {extMsg && <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{extMsg}</span>}
              </div>
            </div>
          )}

          {/* ---------- اجرای همگام‌سازی ---------- */}
          <div className="card">
            <strong>اجرای همگام‌سازی</strong>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: '6px 0 12px' }}>
              {status.note} تغییر نسخه سرفصل هرگز بی‌صدا اعمال نمی‌شود؛ برای هر تغییر، نسخه پیش‌نویس
              برای بررسی استاد ساخته می‌شود.
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-primary" disabled={running !== null}
                onClick={() => void runSync('FULL')}>
                {running === 'FULL' ? '⏳ در حال همگام‌سازی…' : '⟳ همگام‌سازی کامل کاتالوگ'}
              </button>
              <button type="button" className="btn" disabled={running !== null}
                onClick={() => void runSync('INCREMENTAL')}>
                {running === 'INCREMENTAL' ? '⏳ در حال دریافت تغییرات…' : '⇄ همگام‌سازی افزایشی'}
              </button>
            </div>
            {lastResult && (
              <div style={{
                marginTop: 12, padding: '10px 12px', borderRadius: 12,
                background: lastResult.status === 'FAILED' ? 'var(--danger-bg)' : 'var(--success-bg)',
                border: `1px solid ${lastResult.status === 'FAILED' ? 'var(--danger-border)' : 'var(--success-border)'}`,
                color: lastResult.status === 'FAILED' ? 'var(--danger-text)' : 'var(--success-text)',
                fontSize: '0.88rem', lineHeight: 1.9,
              }}>
                <strong>نتیجه آخرین اجرا: </strong>
                {lastResult.status === 'FAILED'
                  ? `${lastResult.error_message}${lastResult.error_code ? ` (کد: ${lastResult.error_code})` : ''}`
                  : lastResult.message}
                {lastResult.review_required > 0 && (
                  <div>⚠️ {fa(lastResult.review_required)} درس نیازمند بررسی استاد شد — نسخه‌های پیش‌نویس در صفحه سرفصل هر درس آماده بررسی است.</div>
                )}
              </div>
            )}
          </div>

          {/* ---------- تاریخچه اجراها ---------- */}
          <div className="card" style={{ marginTop: 14 }}>
            <strong>تاریخچه اجراها</strong>
            {logs.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 8 }}>
                هنوز همگام‌سازی‌ای اجرا نشده است.
              </div>
            ) : (
              <div className="table-wrap" style={{ marginTop: 10 }}>
                <table>
                  <thead>
                    <tr>
                      <th>زمان</th>
                      <th>حالت</th>
                      <th>وضعیت</th>
                      <th>جدید</th>
                      <th>به‌روزرسانی</th>
                      <th>بدون تغییر</th>
                      <th>پیش‌نویس</th>
                      <th>بررسی</th>
                      <th>مدت</th>
                      <th>جزئیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((l) => (
                      <tr key={l.log_id}>
                        <td style={{ whiteSpace: 'nowrap' }}>{faTime(l.created_at)}</td>
                        <td>{l.mode === 'FULL' ? 'کامل' : 'افزایشی'}</td>
                        <td><span className={LOG_BADGE[l.status]}>{l.status === 'OK' ? 'موفق' : l.status === 'PARTIAL' ? 'نیمه‌کامل' : 'ناموفق'}</span></td>
                        <td>{fa(l.courses_created)}</td>
                        <td>{fa(l.courses_updated)}</td>
                        <td>{fa(l.up_to_date)}</td>
                        <td>{fa(l.syllabus_drafts_created)}</td>
                        <td>{l.review_required ? <span className="badge badge-warn">{fa(l.review_required)}</span> : '—'}</td>
                        <td>{l.duration_ms != null ? `${fa(l.duration_ms)}ms` : '—'}</td>
                        <td style={{ maxWidth: 320, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {l.status === 'FAILED' ? l.error_message : l.message}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          وضعیت همگام‌سازی دریافت نشد؛ دکمه «به‌روزرسانی وضعیت» را بزنید.
        </div>
      )}
    </div>
  )
}
