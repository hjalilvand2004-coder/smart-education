import { useCallback, useEffect, useState } from 'react'
import { api, downloadFile } from '../api'

interface MdRecord {
  id: string
  external_id: string
  title: string | null
  topic_count: number
  source_set: string | null
  source_file: string | null
  updated_at: string | null
}

interface MdTopic {
  seq: number | null
  title: string
  hours: number | null
  document_id: string | null
  version_id: string | null
  points: number
}

interface RecordDetail {
  record: MdRecord
  topics: MdTopic[]
  course: { id: string; code: string; title: string } | null
}

interface SyncResp {
  ok: boolean
  message?: string
  error?: { code: string; message: string; hint: string | null }
}

interface GenerateResp {
  ok: boolean
  version_id?: string
  version_number?: number
  qc_blocks?: number
  points_awarded?: number
  message?: string
}

function faTime(v: string | null): string {
  if (!v) return '—'
  return new Date(v).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })
}

/** صفحهٔ «سرفصل دروس» — دامنهٔ course-syllabi پایه‌یار۳۶۰ (v3.5.0).
 * هر سرفصل درسی میزبان تولید محتوا + خروجی PDF/PPTX/HTML + امتیاز استاد است. */
export default function SyllabusTopics() {
  const [items, setItems] = useState<MdRecord[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [msgOk, setMsgOk] = useState(true)
  const [openId, setOpenId] = useState<string | null>(null)
  const [detail, setDetail] = useState<RecordDetail | null>(null)
  const [busyTopic, setBusyTopic] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)

  const load = useCallback(async (query: string) => {
    setLoading(true)
    try {
      const list = await api.get<{ total: number; items: MdRecord[] }>(
        `/integration/payehyar/mdm/course-syllabi?q=${encodeURIComponent(query)}`)
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
      const r = await api.post<SyncResp>('/integration/payehyar/mdm/course-syllabi/sync')
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

  const open = async (id: string) => {
    if (openId === id) { setOpenId(null); setDetail(null); return }
    setOpenId(id)
    setDetail(null)
    try {
      setDetail(await api.get<RecordDetail>(`/integration/payehyar/syllabus-records/${id}`))
    } catch (e) {
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'دریافت جزئیات ناموفق بود')
      setMsgOk(false)
    }
  }

  const generate = async (recordId: string, seq: number | null, key: string) => {
    setBusyTopic(key)
    setMsg(null)
    try {
      const r = await api.post<GenerateResp>(
        `/integration/payehyar/syllabus-records/${recordId}/generate`,
        seq === null ? {} : { topic_seq: seq })
      setMsgOk(r.ok)
      setMsg(r.message ?? 'تولید محتوا انجام شد')
      await open(recordId)
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'تولید محتوا ناموفق بود')
    } finally {
      setBusyTopic(null)
    }
  }

  const download = async (versionId: string, fmt: string, key: string) => {
    setDownloading(key)
    try {
      const { blob, filename } = await downloadFile(
        `/integration/payehyar/content-versions/${versionId}/export/${fmt}`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setMsgOk(false)
      setMsg(e instanceof Error ? `خطا: ${e.message}` : 'دریافت خروجی ناموفق بود')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <main className="page" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div className="page-header">
        <h1>سرفصل دروس</h1>
        <p className="subtitle">
          رکوردهای سرفصل مصوب از پایه‌یار۳۶۰ — هر رکورد چند «سرفصل درسی» دارد؛
          برای هر سرفصل درسی می‌توانید محتوا تولید کنید و خروجی PDF / PowerPoint / HTML بگیرید.
          امتیاز هر تولید و خروجی در صفحهٔ «امتیاز اساتید» ثبت می‌شود.
        </p>
      </div>

      <div className="card">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button type="button" className="btn btn-primary" disabled={syncing} onClick={() => void sync()}>
            {syncing ? '⏳ در حال همگام‌سازی…' : '🔄 همگام‌سازی از پایه‌یار۳۶۰'}
          </button>
          <form onSubmit={(e) => { e.preventDefault(); void load(q) }} style={{ display: 'flex', gap: 8, flex: 1, minWidth: 240 }}>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جستجوی درس بر اساس عنوان…"
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

      {/* ---------- لیست رکوردهای سرفصل ---------- */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map((r) => (
          <div key={r.id} className="card" style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
              <button type="button" className="btn" style={{ flex: 1, minWidth: 220, textAlign: 'right', background: 'transparent', border: 'none', cursor: 'pointer' }} onClick={() => void open(r.id)}>
                <strong>📚 {r.title ?? r.external_id}</strong>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginRight: 10 }}>
                  {r.topic_count} سرفصل درسی — به‌روزرسانی: {faTime(r.updated_at)}
                </span>
              </button>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{openId === r.id ? '▲ بستن' : '▼ باز کردن'}</span>
            </div>

            {openId === r.id && (
              <div style={{ marginTop: 12, borderTop: '1px dashed var(--border, #ccc)', paddingTop: 12 }}>
                {detail === null && <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>⏳ در حال دریافت جزئیات…</div>}
                {detail && (
                  <>
                    {detail.course && (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 10 }}>
                        درس متناظر: <strong style={{ color: 'inherit' }}>{detail.course.title}</strong> (کد {detail.course.code})
                      </div>
                    )}
                    {!detail.course && (
                      <div style={{ fontSize: '0.8rem', color: 'var(--warn-text)', marginBottom: 10 }}>
                        این سرفصل هنوز به درس یکتایی وصل نشده — پس از همگام‌سازی «دروس یکتا»، تولید محتوا خودکار پیوند می‌خورد.
                      </div>
                    )}
                    {detail.topics.map((t) => {
                      const key = `${r.id}:${t.seq ?? 0}`
                      return (
                        <div key={key} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', borderRadius: 10, background: 'var(--bg-soft, rgba(127,127,127,0.06))', marginBottom: 8 }}>
                          <div style={{ flex: 1, minWidth: 200 }}>
                            <strong style={{ fontSize: '0.9rem' }}>{t.title}</strong>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginRight: 10 }}>
                              {t.hours ? `${t.hours} ساعت` : ''} {t.version_id ? `— نسخهٔ محتوا: v${t.version_id.slice(0, 8)}…` : '— بدون محتوا'} {t.points ? `— ${t.points} امتیاز` : ''}
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            <button type="button" className="btn btn-primary" style={{ padding: '5px 12px', fontSize: '0.8rem' }}
                              disabled={busyTopic === key} onClick={() => void generate(r.id, t.seq, key)}>
                              {busyTopic === key ? '⏳ در حال تولید…' : (t.version_id ? '♻️ تولید مجدد' : '✨ تولید محتوا')}
                            </button>
                            {t.version_id && (
                              <>
                                {(['PDF', 'PPTX', 'HTML'] as const).map((f) => (
                                  <button key={f} type="button" className="btn" style={{ padding: '5px 10px', fontSize: '0.75rem' }}
                                    disabled={downloading === `${key}:${f}`}
                                    onClick={() => void download(t.version_id as string, f, `${key}:${f}`)}>
                                    {downloading === `${key}:${f}` ? '⏳' : f === 'PDF' ? '📄 PDF' : f === 'PPTX' ? '📊 PPTX' : '🌐 HTML'}
                                  </button>
                                ))}
                              </>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </>
                )}
              </div>
            )}
          </div>
        ))}
        {!loading && items.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>
            رکورد سرفصلی نیست — دکمهٔ «همگام‌سازی از پایه‌یار۳۶۰» را بزنید تا سرفصل‌های مصوب دریافت شود.
          </div>
        )}
        {total > 0 && (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>کل رکوردهای سرفصل: {total}</div>
        )}
      </div>
    </main>
  )
}
