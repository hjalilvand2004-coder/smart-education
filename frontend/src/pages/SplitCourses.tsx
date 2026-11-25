import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { fmtJalali } from '../utils/jalali'

interface MdRecord {
  id: string
  code: string | null
  title: string | null
  units: number | null
  section: string | null
  unique_course_code: string | null
  year_label: string | null
  status: string | null
  updated_at: string | null
}

interface SyncResp {
  ok: boolean
  message?: string
  error?: { code: string; message: string; hint: string | null }
}

function faTime(v: string | null): string {
  if (!v) return '—'
  return fmtJalali(v, { withTime: true })
}

/** صفحهٔ «دروس تفکیکی» — دامنهٔ split-courses پایه‌یار۳۶۰ (v3.5.0) */
export default function SplitCourses() {
  const [params] = useSearchParams()
  const unique = params.get('unique') ?? ''
  const [items, setItems] = useState<MdRecord[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [msgOk, setMsgOk] = useState(true)

  const load = useCallback(async (query: string, parent: string) => {
    setLoading(true)
    try {
      const parentPart = parent ? `&parent_code=${encodeURIComponent(parent)}` : ''
      const list = await api.get<{ total: number; items: MdRecord[] }>(
        `/integration/payehyar/mdm/split-courses?q=${encodeURIComponent(query)}${parentPart}`)
      setItems(list.items)
      setTotal(list.total)
    } catch (e) {
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'دریافت داده ناموفق بود')
      setMsgOk(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load(q, unique) }, [load, unique]) // eslint-disable-line react-hooks/exhaustive-deps

  const sync = async () => {
    setSyncing(true)
    setMsg(null)
    try {
      const r = await api.post<SyncResp>('/integration/payehyar/mdm/split-courses/sync')
      setMsgOk(r.ok)
      setMsg(r.ok ? (r.message ?? 'همگام‌سازی انجام شد')
        : `${r.error?.message ?? 'همگام‌سازی ناموفق بود'}${r.error?.hint ? ` — ${r.error.hint}` : ''}`)
      await load(q, unique)
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'همگام‌سازی ناموفق بود')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <main className="page" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div className="page-header">
        <h1>دروس تفکیکی</h1>
        <p className="subtitle">
          هر درس یکتا می‌تواند چند درس تفکیکی داشته باشد (گروه/سال تحصیلی متفاوت) —
          این صفحه دامنهٔ «split-courses» پایه‌یار۳۶۰ را نشان می‌دهد و با پیوند
          unique_course_code به درس یکتای والد وصل است.
        </p>
      </div>

      {unique && (
        <div className="card" style={{ padding: '10px 14px', fontSize: '0.85rem' }}>
          فیلتر فعال: فقط درس‌های تفکیکیِ درس یکتا با کد{' '}
          <strong style={{ direction: 'ltr', display: 'inline-block' }}>{unique}</strong>{' '}
          — <Link to="/masterdata/unique" style={{ color: 'var(--accent-text)' }}>حذف فیلتر / بازگشت به دروس یکتا</Link>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button type="button" className="btn btn-primary" disabled={syncing} onClick={() => void sync()}>
            {syncing ? '⏳ در حال همگام‌سازی…' : '🔄 همگام‌سازی از پایه‌یار۳۶۰'}
          </button>
          <form onSubmit={(e) => { e.preventDefault(); void load(q, unique) }} style={{ display: 'flex', gap: 8, flex: 1, minWidth: 240 }}>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جستجو بر اساس عنوان یا کد…"
              style={{ flex: 1, padding: '8px 12px', borderRadius: 10, border: '1px solid var(--border, #ccc)', background: 'transparent', color: 'inherit' }}
            />
            <button type="submit" className="btn" disabled={loading}>{loading ? '…' : '🔍'}</button>
          </form>
        </div>
        {msg && (
          <div style={{ marginTop: 8, fontSize: '0.85rem', color: msgOk ? 'var(--success-text)' : 'var(--danger-text)' }}>
            {msgOk ? '✓ ' : '✗ '}{msg}
          </div>
        )}
      </div>

      <div className="card" style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
          <thead>
            <tr style={{ textAlign: 'right', color: 'var(--text-muted)' }}>
              <th style={{ padding: '8px 10px' }}>عنوان درس تفکیکی</th>
              <th style={{ padding: '8px 10px' }}>درس یکتای والد</th>
              <th style={{ padding: '8px 10px' }}>سال/گروه</th>
              <th style={{ padding: '8px 10px' }}>واحد</th>
              <th style={{ padding: '8px 10px' }}>به‌روزرسانی مرجع</th>
              <th style={{ padding: '8px 10px' }}>اقدام</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} style={{ borderTop: '1px solid var(--border, #ddd)' }}>
                <td style={{ padding: '8px 10px', fontWeight: 600 }}>{r.title ?? '—'}</td>
                <td style={{ padding: '8px 10px', fontFamily: 'monospace', direction: 'ltr' }}>
                  {r.unique_course_code ? (
                    <Link to={`/masterdata/unique`} style={{ color: 'var(--accent-text)' }}>{r.unique_course_code}</Link>
                  ) : '—'}
                </td>
                <td style={{ padding: '8px 10px' }}>{r.year_label ?? '—'}</td>
                <td style={{ padding: '8px 10px' }}>{r.units ?? '—'}</td>
                <td style={{ padding: '8px 10px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>{faTime(r.updated_at)}</td>
                <td style={{ padding: '8px 10px' }}>
                  <Link className="btn" style={{ padding: '4px 10px', fontSize: '0.78rem' }} to="/masterdata/syllabus">سرفصل‌ها</Link>
                </td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                رکوردی نیست — دکمهٔ «همگام‌سازی از پایه‌یار۳۶۰» را بزنید.
              </td></tr>
            )}
          </tbody>
        </table>
        {total > 0 && (
          <div style={{ padding: '8px 10px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>کل: {total} رکورد</div>
        )}
      </div>
    </main>
  )
}
