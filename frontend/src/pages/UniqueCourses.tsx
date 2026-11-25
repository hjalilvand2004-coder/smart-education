import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { fmtJalali } from '../utils/jalali'

interface MdOverview {
  domains: Record<string, { count: number; last_synced_at: string | null }>
  topic_total: number
}

interface MdRecord {
  id: string
  code: string | null
  title: string | null
  units: number | null
  section: string | null
  capacity: number | null
  prerequisite: string | null
  status: string | null
  updated_at: string | null
}

interface SyncResp {
  ok: boolean
  message?: string
  error?: { code: string; message: string; hint: string | null }
}

function faTime(v: string | null | undefined): string {
  if (!v) return '—'
  return fmtJalali(v, { withTime: true })
}

/** صفحهٔ «دروس یکتا» — دامنهٔ MDM پایه‌یار۳۶۰ (v3.5.0) */
export default function UniqueCourses() {
  const [overview, setOverview] = useState<MdOverview | null>(null)
  const [items, setItems] = useState<MdRecord[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [msgOk, setMsgOk] = useState(true)

  const load = useCallback(async (query: string) => {
    setLoading(true)
    try {
      const [ov, list] = await Promise.all([
        api.get<MdOverview>('/integration/payehyar/mdm/overview'),
        api.get<{ total: number; items: MdRecord[] }>(
          `/integration/payehyar/mdm/unique-courses?q=${encodeURIComponent(query)}`),
      ])
      setOverview(ov)
      setItems(list.items)
      setTotal(list.total)
    } catch (e) {
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'دریافت داده ناموفق بود')
      setMsgOk(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load('') }, [load])

  const sync = async () => {
    setSyncing(true)
    setMsg(null)
    try {
      const r = await api.post<SyncResp>('/integration/payehyar/mdm/unique-courses/sync')
      setMsgOk(r.ok)
      setMsg(r.ok ? (r.message ?? 'همگام‌سازی انجام شد')
        : `${r.error?.message ?? 'همگام‌سازی ناموفق بود'}${r.error?.hint ? ` — ${r.error.hint}` : ''}`)
      await load(q)
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'همگام‌سازی ناموفق بود')
    } finally {
      setSyncing(false)
    }
  }

  const lastSync = overview?.domains['unique-courses']?.last_synced_at

  return (
    <main className="page" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div className="page-header">
        <h1>دروس یکتا</h1>
        <p className="subtitle">
          رونوشت دامنهٔ «unique-courses» از سامانهٔ MDM پایه‌یار۳۶۰ — منبع حقیقت کاتالوگ دروس؛
          این صفحه با دکمهٔ همگام‌سازی، مستقیماً از پایه‌یار به‌روز می‌شود.
        </p>
      </div>

      {/* ---------- سربرگ آمار سه دامنه ---------- */}
      {overview && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
          {[
            { label: 'دروس یکتا', value: overview.domains['unique-courses']?.count, to: '/masterdata/unique' },
            { label: 'دروس تفکیکی', value: overview.domains['split-courses']?.count, to: '/masterdata/split' },
            { label: 'رکورد سرفصل', value: overview.domains['course-syllabi']?.count, to: '/masterdata/syllabus' },
            { label: 'سرفصل درسی', value: overview.topic_total, to: '/masterdata/syllabus' },
          ].map((s) => (
            <Link key={s.label} to={s.to} className="card" style={{ textAlign: 'center', textDecoration: 'none', color: 'inherit', padding: '14px 10px' }}>
              <div style={{ fontSize: '1.6rem', fontWeight: 800 }}>{s.value ?? 0}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{s.label}</div>
            </Link>
          ))}
        </div>
      )}

      {/* ---------- فرم همگام‌سازی و جستجو ---------- */}
      <div className="card">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button type="button" className="btn btn-primary" disabled={syncing} onClick={() => void sync()}>
            {syncing ? '⏳ در حال همگام‌سازی…' : '🔄 همگام‌سازی از پایه‌یار۳۶۰'}
          </button>
          <form onSubmit={(e) => { e.preventDefault(); void load(q) }} style={{ display: 'flex', gap: 8, flex: 1, minWidth: 240 }}>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جستجو بر اساس عنوان یا کد درس…"
              style={{ flex: 1, padding: '8px 12px', borderRadius: 10, border: '1px solid var(--border, #ccc)', background: 'transparent', color: 'inherit' }}
            />
            <button type="submit" className="btn" disabled={loading}>{loading ? '…' : '🔍'}</button>
          </form>
        </div>
        <div style={{ marginTop: 8, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          آخرین همگام‌سازی این دامنه: {faTime(lastSync)} — کل رکوردهای یافت‌شده: {total}
        </div>
        {msg && (
          <div style={{ marginTop: 8, fontSize: '0.85rem', color: msgOk ? 'var(--success-text)' : 'var(--danger-text)' }}>
            {msgOk ? '✓ ' : '✗ '}{msg}
          </div>
        )}
      </div>

      {/* ---------- لیست دروس یکتا ---------- */}
      <div className="card" style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
          <thead>
            <tr style={{ textAlign: 'right', color: 'var(--text-muted)' }}>
              <th style={{ padding: '8px 10px' }}>کد</th>
              <th style={{ padding: '8px 10px' }}>عنوان درس</th>
              <th style={{ padding: '8px 10px' }}>واحد</th>
              <th style={{ padding: '8px 10px' }}>گروه</th>
              <th style={{ padding: '8px 10px' }}>پیش‌نیاز</th>
              <th style={{ padding: '8px 10px' }}>به‌روزرسانی مرجع</th>
              <th style={{ padding: '8px 10px' }}>اقدام</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} style={{ borderTop: '1px solid var(--border, #ddd)' }}>
                <td style={{ padding: '8px 10px', fontFamily: 'monospace', direction: 'ltr' }}>{r.code ?? '—'}</td>
                <td style={{ padding: '8px 10px', fontWeight: 600 }}>{r.title ?? '—'}</td>
                <td style={{ padding: '8px 10px' }}>{r.units ?? '—'}</td>
                <td style={{ padding: '8px 10px' }}>{r.section ?? '—'}</td>
                <td style={{ padding: '8px 10px', fontSize: '0.8rem' }}>{r.prerequisite ?? '—'}</td>
                <td style={{ padding: '8px 10px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>{faTime(r.updated_at)}</td>
                <td style={{ padding: '8px 10px', whiteSpace: 'nowrap' }}>
                  {r.code && (
                    <>
                      <Link className="btn" style={{ padding: '4px 10px', fontSize: '0.78rem', marginLeft: 6 }} to={`/masterdata/split?unique=${encodeURIComponent(r.code ?? '')}`}>دروس تفکیکی</Link>
                      <Link className="btn" style={{ padding: '4px 10px', fontSize: '0.78rem' }} to={`/masterdata/syllabus?q=${encodeURIComponent(r.title ?? '')}`}>سرفصل‌ها</Link>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr><td colSpan={7} style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                رکوردی نیست — دکمهٔ «همگام‌سازی از پایه‌یار۳۶۰» را بزنید تا کاتالوگ دریافت شود.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  )
}
