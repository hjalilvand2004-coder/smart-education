import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { fmtJalali } from '../utils/jalali'

/** صفحهٔ درس‌یار۳۶۰ (darsyar360.ir) — v3.9.0:
 *  تنظیمات اتصال + تست گام‌به‌گام + همگام‌سازی گروهی مطلوبیات درسی/زمانی اساتید.
 *  مالک دادهٔ مطلوبیات سامانهٔ درس‌یار است؛ اینجا فقط رونوشت همگام‌شده نگه داشته می‌شود. */

interface DarsyarConnectionView {
  base_url: string
  api_key_masked: string | null
  has_key: boolean
  key_source: 'DB' | 'ENV' | 'NONE'
  base_url_source: 'DB' | 'DEFAULT'
  timeout_seconds: number
  timeout_source: 'DB' | 'DEFAULT'
  updated_at: string | null
  data_owner: string
}

interface TestStep {
  name: string
  ok: boolean
  detail: string
  hint: string | null
}

interface TestResult {
  ok: boolean
  steps: TestStep[]
  summary: string
}

interface SyncItem {
  ext_id: string
  name: string
  department: string
  source: 'live' | 'demo' | 'error'
  error?: string
  subjects_count: number
  time_slots_count: number
  constraints_count: number
  fetched_at: string | null
}

interface SyncResult {
  ok: boolean
  message: string
  total: number
  live: number
  demo: number
  items: SyncItem[]
}

interface SubjectPref {
  title: string
  course_code: string
  weekly_hours: number
  level: string
}

interface OverviewItem {
  ext_id: string
  name: string
  source: string
  fetched_at: string | null
  subjects: SubjectPref[]
  time_slots_count: number
  constraints_count: number
  constraints: string[]
}

interface OverviewResult {
  ok: boolean
  total: number
  items: OverviewItem[]
}

/** نرمال‌سازی فارسی برای جستجوی جدول مطلوبیات */
function faNorm(text: string): string {
  return (text || '')
    .replace(/\u200c/g, ' ')
    .replace(/[يى]/g, 'ی')
    .replace(/ك/g, 'ک')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

const SOURCE_LABEL: Record<string, string> = {
  live: 'زنده از درس‌یار۳۶۰',
  demo: 'نمونهٔ قطعی توسعه',
  error: 'خطا',
}

export default function Darsyar() {
  // تنظیمات اتصال
  const [conn, setConn] = useState<DarsyarConnectionView | null>(null)
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [timeoutSec, setTimeoutSec] = useState('8')
  // تست اتصال
  const [test, setTest] = useState<TestResult | null>(null)
  // همگام‌سازی
  const [sync, setSync] = useState<SyncResult | null>(null)
  // مطلوبیات ذخیره‌شده
  const [overview, setOverview] = useState<OverviewResult | null>(null)
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState<'save' | 'test' | 'sync' | 'load' | null>(null)
  const [msg, setMsg] = useState('')
  const [msgOk, setMsgOk] = useState(true)

  const errText = (e: unknown) => (e instanceof ApiError ? e.message : 'خطای ارتباط با سرور')

  const loadAll = async () => {
    setBusy('load')
    try {
      const [c, ov] = await Promise.all([
        api.get<DarsyarConnectionView>('/integration/darsyar/connection'),
        api.get<OverviewResult>('/integration/darsyar/preferences'),
      ])
      setConn(c)
      setTimeoutSec(String(c.timeout_seconds || 8))
      setOverview(ov)
    } catch (e) {
      setMsg(errText(e)); setMsgOk(false)
    } finally {
      setBusy(null)
    }
  }

  useEffect(() => {
    document.title = 'درس‌یار۳۶۰ — مطلوبیات اساتید | دانشجو۳۶۰'
    void loadAll()
  }, [])

  const saveConnection = async () => {
    setBusy('save'); setMsg(''); setTest(null)
    try {
      const body: Record<string, unknown> = {
        base_url: baseUrl.trim() || '',
        api_key: apiKey.trim() || '',
        timeout_seconds: Number(timeoutSec) || 8,
      }
      const v = await api.put<DarsyarConnectionView>('/integration/darsyar/connection', body)
      setConn(v); setApiKey('')
      setMsg('تنظیمات اتصال ذخیره شد — از همین لحظه در واکشی‌های بعدی اعمال می‌شود.'); setMsgOk(true)
    } catch (e) {
      setMsg(errText(e)); setMsgOk(false)
    } finally {
      setBusy(null)
    }
  }

  const runTest = async () => {
    setBusy('test'); setMsg(''); setTest(null)
    try {
      const r = await api.post<TestResult>('/integration/darsyar/test-connection', {
        base_url: baseUrl.trim() || undefined,
        api_key: apiKey.trim() || undefined,
      })
      setTest(r)
    } catch (e) {
      setMsg(errText(e)); setMsgOk(false)
    } finally {
      setBusy(null)
    }
  }

  const runSync = async () => {
    setBusy('sync'); setMsg(''); setSync(null)
    try {
      const r = await api.post<SyncResult>('/integration/darsyar/sync', { refresh: true, limit: 100 })
      setSync(r)
      setMsgOk(r.ok)
      const ov = await api.get<OverviewResult>('/integration/darsyar/preferences')
      setOverview(ov)
    } catch (e) {
      setMsg(errText(e)); setMsgOk(false)
    } finally {
      setBusy(null)
    }
  }

  const filteredItems = useMemo(() => {
    const rows = overview?.items || []
    const query = faNorm(q)
    if (!query) return rows
    return rows.filter((r) =>
      [r.name, r.ext_id, ...(r.subjects || []).map((s) => s.title)]
        .some((field) => field && faNorm(String(field)).includes(query)),
    )
  }, [overview, q])

  return (
    <>
      <div className="hero">
        <div className="hero-icon">📊</div>
        <div>
          <h2>درس‌یار۳۶۰ — نظرسنجی و مطلوبیات اساتید</h2>
          <p>
            واکشی «مطلوبیات درسی و زمانی» اساتید از سامانهٔ نظرسنجی <b>درس‌یار۳۶۰</b>
            {' '}(darsyar360.ir) و نگهداری رونوشت همگام‌شده در این سامانه. مالک دادهٔ
            مطلوبیات سامانهٔ درس‌یار است؛ مطلوبیات در صفحهٔ «اساتید و مطلوبیات» به استاد
            نمایش داده می‌شود و درس‌های متناسب برای تولید محتوا فیلتر می‌گردند.
          </p>
        </div>
      </div>

      {/* ---------- تنظیمات اتصال ---------- */}
      <div className="card">
        <div className="card-title">
          <h3>تنظیمات اتصال به درس‌یار۳۶۰</h3>
          {conn && (
            <span className="muted">
              منبع آدرس: {conn.base_url_source === 'DB' ? 'ذخیره‌شده در سامانه' : 'پیش‌فرض'} · کلید: {conn.has_key ? `${conn.api_key_masked} (${conn.key_source === 'DB' ? 'دیتابیس' : 'متغیر محیطی'})` : 'تنظیم نشده'}
            </span>
          )}
        </div>
        <div className="form-grid">
          <div className="form-item">
            <label className="label">آدرس سرویس</label>
            <input className="input" dir="ltr" placeholder="https://darsyar360.ir"
                   value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            <div className="hint">برای بازگشت به پیش‌فرض، خالی بگذارید و ذخیره کنید.</div>
          </div>
          <div className="form-item">
            <label className="label">کلید API (X-API-Key)</label>
            <input className="input" type="password" dir="ltr" autoComplete="new-password"
                   placeholder={conn?.has_key ? 'ذخیره‌شده — برای تغییر مقدار جدید بدهید' : 'کلید سامانهٔ مصرف‌کننده از مدیر درس‌یار'}
                   value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
            <div className="hint">کلید فقط در همین دستگاه (دیتابیس محلی) ذخیره و هرگز کامل نمایش داده نمی‌شود.</div>
          </div>
          <div className="form-item">
            <label className="label">تایم‌اوت (ثانیه)</label>
            <input className="input" type="number" min="1" max="60" value={timeoutSec}
                   onChange={(e) => setTimeoutSec(e.target.value)} />
          </div>
        </div>
        <div className="btn-row section-gap">
          <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={saveConnection}>
            {busy === 'save' ? 'در حال ذخیره…' : 'ذخیرهٔ تنظیمات'}
          </button>
          <button type="button" className="btn" disabled={busy !== null} onClick={runTest}>
            {busy === 'test' ? 'در حال تست…' : 'تست اتصال'}
          </button>
        </div>
        {msg && <div className={msgOk ? 'success-box' : 'inline-alert'}>{msg}</div>}
        {conn?.updated_at && (
          <div className="hint">آخرین به‌روزرسانی تنظیمات: {fmtJalali(conn.updated_at, { withTime: true })}</div>
        )}
        {test && (
          <div style={{ marginTop: 12 }}>
            {test.steps.map((s, i) => (
              <div key={i} className={s.ok ? 'success-box' : 'error-box'}>
                <strong>{s.ok ? '✓' : '✕'} {s.name}</strong>
                <div>{s.detail}</div>
                {s.hint && <div className="hint">راهنما: {s.hint}</div>}
              </div>
            ))}
            <div className={test.ok ? 'success-box' : 'inline-alert'}><b>{test.summary}</b></div>
          </div>
        )}
      </div>

      {/* ---------- همگام‌سازی گروهی مطلوبیات ---------- */}
      <div className="card">
        <div className="card-title">
          <h3>همگام‌سازی مطلوبیات اساتید</h3>
          <span className="muted">برای همهٔ اساتیدِ همگام‌شده از پایه‌یار۳۶۰</span>
        </div>
        <div className="hint" style={{ marginTop: -6, marginBottom: 10 }}>
          مطلوبیات درسی (موضوع‌های تخصصی) و زمانی (بازه‌های مطلوب/غیرمطلوب هفتگی) هر استاد
          از درس‌یار۳۶۰ واکشی و در این سامانه رونویسی می‌شود؛ اگر سرویس در دسترس نباشد
          «نمونهٔ قطعی توسعه» با برچسب شفاف نمایش داده می‌شود.
        </div>
        <div className="btn-row">
          <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={runSync}>
            {busy === 'sync' ? '⏳ در حال همگام‌سازی…' : '🔄 همگام‌سازی مطلوبیات همهٔ اساتید'}
          </button>
        </div>
        {sync && (
          <div style={{ marginTop: 12 }}>
            <div className={sync.ok ? 'success-box' : 'inline-alert'}>{sync.message}</div>
            {sync.ok && sync.items.map((it) => (
              <div key={it.ext_id} className="sync-progress-row">
                <div>
                  <b>{it.name}</b>
                  {it.department ? <span className="muted"> · {it.department}</span> : null}
                  {it.source === 'error' && <span className="muted"> — {it.error}</span>}
                </div>
                <div className="muted">
                  موضوع: {it.subjects_count.toLocaleString('fa-IR')} · بازهٔ زمانی: {it.time_slots_count.toLocaleString('fa-IR')} · قید: {it.constraints_count.toLocaleString('fa-IR')}
                  {' '}· <span className={`badge ${it.source === 'live' ? 'badge-success' : 'badge-info'}`}>{SOURCE_LABEL[it.source] || it.source}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---------- مطلوبیات ذخیره‌شده ---------- */}
      <div className="card">
        <div className="card-title">
          <h3>مطلوبیات ذخیره‌شده ({(overview?.total || 0).toLocaleString('fa-IR')} استاد)</h3>
          <Link className="btn btn-sm" to="/professors">نمایش به استاد و درس‌های متناسب ←</Link>
        </div>
        <div className="courses-search-row" style={{ margin: '8px 0 12px' }}>
          <div className="courses-search">
            <input
              className="input search-input"
              type="search"
              placeholder="جستجوی استاد یا موضوع مطلوب…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              aria-label="جستجوی مطلوبیات"
            />
            {q && (
              <button type="button" className="search-clear" aria-label="پاک‌کردن جستجو"
                      onClick={() => setQ('')}>✕</button>
            )}
          </div>
          {q && <div className="search-count muted">{filteredItems.length.toLocaleString('fa-IR')} نتیجه</div>}
        </div>
        {!overview || overview.items.length === 0 ? (
          <div className="empty-box">
            <strong>هنوز مطلوبیاتی ذخیره نشده</strong>
            ابتدا اساتید را از پایه‌یار۳۶۰ همگام کنید (صفحهٔ «اساتید و مطلوبیات») و سپس
            دکمهٔ «همگام‌سازی مطلوبیات» را بزنید.
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="empty-box">
            <strong>نتیجه‌ای برای «{q}» یافت نشد</strong>
            عبارت دیگری را امتحان کنید.
          </div>
        ) : (
          filteredItems.map((r) => (
            <div key={r.ext_id} className="pyc-row">
              <div>
                <strong>{r.name}</strong>{' '}
                <span className={`badge ${r.source === 'live' ? 'badge-success' : 'badge-info'}`}>
                  {SOURCE_LABEL[r.source] || r.source}
                </span>
                <div className="pref-subjects" style={{ marginTop: 6 }}>
                  {r.subjects.map((s, i) => (
                    <span key={i} className="pref-subject-chip">
                      {s.title}{s.weekly_hours ? ` · ${s.weekly_hours} ساعت/هفته` : ''}
                    </span>
                  ))}
                </div>
                <div className="pref-slots">
                  {r.constraints.map((c, i) => (
                    <span key={i} className="pref-slot acceptable">قید: {c}</span>
                  ))}
                </div>
                <div className="muted" style={{ marginTop: 6, fontSize: '0.76rem' }}>
                  آخرین واکشی: {r.fetched_at ? fmtJalali(r.fetched_at, { withTime: true }) : '—'} ·
                  {' '}بازهٔ زمانی: {r.time_slots_count.toLocaleString('fa-IR')}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  )
}
