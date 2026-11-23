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
  const [error, setError] = useState<string | null>(null)

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
