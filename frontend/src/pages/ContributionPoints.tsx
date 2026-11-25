import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'

interface PointRow {
  id: string
  action: string
  points: number
  fmt: string | null
  note: string | null
  created_at: string | null
}

interface PointsMe {
  total: number
  by_action: Record<string, number>
  rules: Record<string, number>
  items: PointRow[]
}

interface LeaderRow {
  user_id: string
  name: string
  total: number
}

const ACTION_FA: Record<string, string> = {
  CONTENT_GENERATE: 'تولید محتوا',
  CONTENT_EXPORT: 'خروجی گرفتن',
}

function faTime(v: string | null): string {
  if (!v) return '—'
  return new Date(v).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })
}

/** صفحهٔ «امتیاز اساتید» — ثبت و نمایش مشارکت‌های تولید محتوا (v3.5.0) */
export default function ContributionPoints() {
  const [me, setMe] = useState<PointsMe | null>(null)
  const [board, setBoard] = useState<LeaderRow[]>([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [mine, leaders] = await Promise.all([
        api.get<PointsMe>('/points/me'),
        api.get<{ items: LeaderRow[] }>('/points/leaderboard'),
      ])
      setMe(mine)
      setBoard(leaders.items)
    } catch (e) {
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'دریافت امتیازها ناموفق بود')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <main className="page" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div className="page-header">
        <h1>امتیاز اساتید</h1>
        <p className="subtitle">
          زحمت تولید محتوا ثبت و دیده می‌شود: هر محتوای تولیدشده برای یک سرفصل درسی
          {me?.rules?.CONTENT_GENERATE ? ` ${me.rules.CONTENT_GENERATE} امتیاز` : ' امتیاز'} و هر قالب
          خروجی (PDF/PPTX/HTML/DOCX){me?.rules?.CONTENT_EXPORT ? ` ${me.rules.CONTENT_EXPORT} امتیاز` : ' امتیاز'} دارد.
        </p>
      </div>

      {msg && <div className="card" style={{ color: 'var(--danger-text)', fontSize: '0.85rem' }}>✗ {msg}</div>}

      {/* ---------- خلاصهٔ من ---------- */}
      {me && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <div className="card" style={{ textAlign: 'center', padding: '16px 10px' }}>
            <div style={{ fontSize: '2rem', fontWeight: 800 }}>⭐ {me.total}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>جمع امتیاز من</div>
          </div>
          {Object.entries(me.by_action).map(([a, p]) => (
            <div key={a} className="card" style={{ textAlign: 'center', padding: '16px 10px' }}>
              <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{p}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{ACTION_FA[a] ?? a}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12 }}>
        {/* ---------- رکوردهای اخیر من ---------- */}
        <div className="card" style={{ overflowX: 'auto' }}>
          <strong>رکوردهای اخیر من</strong>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', marginTop: 10 }}>
            <thead>
              <tr style={{ textAlign: 'right', color: 'var(--text-muted)' }}>
                <th style={{ padding: '6px 8px' }}>اقدام</th>
                <th style={{ padding: '6px 8px' }}>امتیاز</th>
                <th style={{ padding: '6px 8px' }}>توضیح</th>
                <th style={{ padding: '6px 8px' }}>زمان</th>
              </tr>
            </thead>
            <tbody>
              {me?.items.map((r) => (
                <tr key={r.id} style={{ borderTop: '1px solid var(--border, #ddd)' }}>
                  <td style={{ padding: '6px 8px' }}>{ACTION_FA[r.action] ?? r.action}{r.fmt ? ` (${r.fmt})` : ''}</td>
                  <td style={{ padding: '6px 8px', fontWeight: 700 }}>+{r.points}</td>
                  <td style={{ padding: '6px 8px', fontSize: '0.78rem' }}>{r.note ?? '—'}</td>
                  <td style={{ padding: '6px 8px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{faTime(r.created_at)}</td>
                </tr>
              ))}
              {!loading && (!me || me.items.length === 0) && (
                <tr><td colSpan={4} style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)' }}>
                  هنوز امتیازی ندارید — از صفحهٔ «سرفصل دروس» محتوا تولید کنید.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ---------- جدول برترین‌ها ---------- */}
        <div className="card" style={{ overflowX: 'auto' }}>
          <strong>برترین مشارکت‌کنندگان</strong>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', marginTop: 10 }}>
            <thead>
              <tr style={{ textAlign: 'right', color: 'var(--text-muted)' }}>
                <th style={{ padding: '6px 8px' }}>#</th>
                <th style={{ padding: '6px 8px' }}>استاد</th>
                <th style={{ padding: '6px 8px' }}>امتیاز</th>
              </tr>
            </thead>
            <tbody>
              {board.map((r, i) => (
                <tr key={r.user_id} style={{ borderTop: '1px solid var(--border, #ddd)' }}>
                  <td style={{ padding: '6px 8px' }}>{['🥇', '🥈', '🥉'][i] ?? i + 1}</td>
                  <td style={{ padding: '6px 8px', fontWeight: i < 3 ? 700 : 400 }}>{r.name}</td>
                  <td style={{ padding: '6px 8px', fontWeight: 700 }}>⭐ {r.total}</td>
                </tr>
              ))}
              {!loading && board.length === 0 && (
                <tr><td colSpan={3} style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)' }}>
                  هنوز مشارکتی ثبت نشده است.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  )
}
