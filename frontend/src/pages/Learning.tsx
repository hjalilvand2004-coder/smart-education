import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import type {
  Block,
  ConceptMapData,
  ContentVersion,
  PublishedContent,
  StuckResult,
} from '../api'
import Blocks from '../components/Blocks'

interface Citation {
  resource_id: string
  locator?: string
  quote?: string
  resource_title?: string
}

interface HistoryMsg {
  id: string
  role: string
  content: string
  citations?: unknown
  meta?: Record<string, unknown> | null
}

interface ChatMsg {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[] | null
  meta?: Record<string, unknown> | null
}

/** «اینجا گیر کردم» — چهار نوع مشکل از بازخورد طراحی */
const STUCK_KINDS: Array<{ kind: string; label: string }> = [
  { kind: 'NOT_UNDERSTOOD', label: 'معنی این عبارت را نمی‌فهمم' },
  { kind: 'CONNECTION_UNCLEAR', label: 'ارتباطش با مطلب قبلی روشن نیست' },
  { kind: 'STEP_UNCLEAR', label: 'نمی‌دانم چرا این مرحله انجام شد' },
  { kind: 'KNOWS_BUT_CANT_SOLVE', label: 'مفهوم را می‌دانم، اما نمی‌توانم حل کنم' },
]

const HELP_MODES: Array<{ mode: string; label: string; hint: string }> = [
  { mode: 'EXPLAIN', label: 'برایم توضیح بده', hint: 'توضیح کامل با مثال ساده‌تر' },
  { mode: 'GUIDE', label: 'با سؤال کمکم کن', hint: 'نردبان راهنما — پاسخ کامل با درخواست شما' },
  { mode: 'PRACTICE', label: 'با من تمرین کن', hint: 'حل گام‌به‌گام مشترک' },
]

export default function Learning({ courseId }: { courseId: string }) {
  const [params] = useSearchParams()
  const [contents, setContents] = useState<PublishedContent[] | null>(null)
  const [version, setVersion] = useState<ContentVersion | null>(null)
  const [map, setMap] = useState<ConceptMapData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fontScale, setFontScale] = useState(1)
  const [activeTab, setActiveTab] = useState<'contents' | 'content' | 'tutor'>('content')

  // استاد هوشمند (پنل چپ)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [helpMode, setHelpMode] = useState('GUIDE')
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const chatEndRef = useRef<HTMLDivElement | null>(null)

  // «اینجا گیر کردم»
  const [stuckFor, setStuckFor] = useState<number | null>(null)
  const [stuckNote, setStuckNote] = useState('')

  useEffect(() => {
    document.title = 'محیط یادگیری | دانشجو۳۶۰'
    let alive = true
    api
      .get<PublishedContent[]>(`/courses/${courseId}/contents`)
      .then((rows) => alive && setContents(rows || []))
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'خطا در دریافت محتوا'))
    api
      .get<ConceptMapData>(`/me/courses/${courseId}/concept-map?mode=simple`)
      .then((m) => alive && setMap(m))
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [courseId])

  const loadVersion = useCallback(
    (vid: string) => {
      setVersion(null)
      api
        .get<ContentVersion>(`/content-versions/${vid}`)
        .then((v) => {
          setVersion(v)
          api
            .post('/learning-events', {
              course_id: courseId,
              type: 'CONTENT_VIEWED',
              payload: { content_version_id: vid },
            })
            .catch(() => undefined)
        })
        .catch((e) => setError(e instanceof Error ? e.message : 'خطا در دریافت محتوا'))
    },
    [courseId],
  )

  // نسخه اولیه از پارامتر ?version= یا نخستین محتوای منتشرشده
  useEffect(() => {
    if (!contents) return
    const vid = params.get('version') ?? contents[0]?.version_id
    if (vid) loadVersion(vid)
  }, [contents, params, loadVersion])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId
    const s = await api.post<{ id: string }>('/tutor/sessions', {
      course_id: courseId,
      mode: 'LEARNING',
    })
    setSessionId(s.id)
    return s.id
  }, [courseId, sessionId])

  const loadHistory = useCallback(async (sid: string) => {
    const rows = await api.get<HistoryMsg[]>(`/tutor/sessions/${sid}/messages`)
    setMessages(
      (rows ?? []).map((m) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        citations: (m.citations ?? null) as Citation[] | null,
        meta: (m.meta ?? null) as Record<string, unknown> | null,
      })),
    )
  }, [])

  const sendMessage = useCallback(
    async (text: string, mode: string) => {
      if (!text.trim()) return
      setSending(true)
      try {
        const sid = await ensureSession()
        setMessages((prev) => [...prev, { id: `local-${Date.now()}`, role: 'user', content: text }])
        const reply = await api.post<ChatMsg>(`/tutor/sessions/${sid}/messages`, {
          content: text,
          help_mode: mode,
        })
        setMessages((prev) => [...prev, reply])
        setDraft('')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'پاسخ استاد هوشمند دریافت نشد')
      } finally {
        setSending(false)
      }
    },
    [ensureSession],
  )

  const openStuckTutor = useCallback(
    async (sid: string) => {
      setSessionId(sid)
      await loadHistory(sid)
      setActiveTab('tutor')
    },
    [loadHistory],
  )

  const submitStuck = useCallback(
    async (blockIndex: number, kind: string) => {
      if (!version) return
      const block: Block | undefined = version.blocks?.[blockIndex]
      const anchor = (block?.title || block?.body || '').slice(0, 160)
      try {
        const res = await api.post<StuckResult>(`/me/courses/${courseId}/stuck-marks`, {
          kind,
          content_version_id: version.id,
          block_index: blockIndex,
          block_anchor: anchor,
          note: stuckNote || undefined,
          start_tutor: true,
        })
        setStuckFor(null)
        setStuckNote('')
        if (res.tutor_session_id) {
          await openStuckTutor(res.tutor_session_id)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'ثبت «اینجا گیر کردم» ناموفق بود')
      }
    },
    [courseId, version, stuckNote, openStuckTutor],
  )

  const sendForm = (e: FormEvent) => {
    e.preventDefault()
    void sendMessage(draft, helpMode)
  }

  const conceptList = (map?.stages ?? []).flatMap((stage, si) =>
    stage.map((n) => ({ ...n, stage: si + 1 })),
  )

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>محیط یادگیری</h1>
          <p className="page-sub">محتوا را بخوانید، هرجا گیر کردید علامت بدهید و از استاد هوشمند درس بپرسید — هر سه ستون با هم کار می‌کنند.</p>
        </div>
        <div className="fb-group">
          <span className="fb-label">اندازهٔ متن</span>
          <button
            type="button"
            className={`fb-btn${fontScale > 1 ? ' on' : ''}`}
            onClick={() => setFontScale((f) => Math.min(1.3, f + 0.1))}
          >
            A+
          </button>
          <button
            type="button"
            className={`fb-btn${fontScale < 1 ? ' on' : ''}`}
            onClick={() => setFontScale((f) => Math.max(0.9, f - 0.1))}
          >
            A−
          </button>
          <button type="button" className="fb-btn" onClick={() => setFontScale(1)}>
            بازنشانی
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {/* تب‌های موبایل: سه پنل فشرده نمی‌شوند؛ هر بخش یک تب است */}
      <div className="learning-tabs" role="tablist" aria-label="بخش‌های محیط یادگیری">
        <button className={`tab${activeTab === 'contents' ? ' active' : ''}`} onClick={() => setActiveTab('contents')} type="button">
          مسیر و فهرست
        </button>
        <button className={`tab${activeTab === 'content' ? ' active' : ''}`} onClick={() => setActiveTab('content')} type="button">
          محتوای اصلی
        </button>
        <button className={`tab${activeTab === 'tutor' ? ' active' : ''}`} onClick={() => setActiveTab('tutor')} type="button">
          استاد هوشمند
        </button>
      </div>

      <div className="learning-grid">
        {/* پنل راست: مسیر و فهرست */}
        <aside className={`learning-pane${activeTab === 'contents' ? ' mobile-on' : ''}`} aria-label="مسیر و فهرست مفاهیم">
          <div className="pane-head">
            <span className="pane-ico" aria-hidden="true">🧭</span>
            <div>
              <h3>مسیر مفاهیم</h3>
              <p className="pane-desc">ترتیب مفاهیم درس و وضعیت پیشرفت شما؛ نقطهٔ رنگی کنار هر مفهوم = وضعیت. با کلیک به مفهوم بروید.</p>
            </div>
          </div>
          <div className="concept-list">
            {conceptList.map((n) => (
              <Link
                key={n.concept_id}
                className={`concept-item${params.get('concept') === n.concept_id ? ' active' : ''}`}
                to={`/course/${courseId}/learn?concept=${n.concept_id}`}
              >
                <span>
                  {n.stage}. {n.concept_name}
                </span>
                <span className={`dot ${n.status}`} title={n.state_label ?? ''} />
              </Link>
            ))}
            {conceptList.length === 0 && <p className="muted">نقشه مفاهیم این درس هنوز ثبت نشده است.</p>}
          </div>
          <div className="pane-head" style={{ marginTop: 16 }}>
            <span className="pane-ico" aria-hidden="true">📚</span>
            <div>
              <h3>محتواهای منتشرشده</h3>
              <p className="pane-desc">جزوه‌های منتشرشدهٔ استاد؛ با کلیک، همان جزوه در ستون میانی باز می‌شود.</p>
            </div>
          </div>
          <div className="concept-list">
            {(contents ?? []).map((c) => (
              <button
                key={c.version_id}
                type="button"
                className={`concept-item${version?.id === c.version_id ? ' active' : ''}`}
                onClick={() => loadVersion(c.version_id)}
              >
                <span>{c.document_title}</span>
                <span className="muted" style={{ fontSize: '0.7rem' }}>
                  نسخه {c.version_number}
                </span>
              </button>
            ))}
            {contents !== null && contents.length === 0 && (
              <p className="muted">هنوز محتوایی منتشر نشده است.</p>
            )}
          </div>
        </aside>

        {/* مرکز: محتوای اصلی + «اینجا گیر کردم» */}
        <section className={`learning-pane${activeTab === 'content' ? ' mobile-on' : ''}`} aria-label="محتوای اصلی">
          {version ? (
            <>
              <div className="pane-head">
                <span className="pane-ico" aria-hidden="true">📖</span>
                <div>
                  <h3>{version.document_title}</h3>
                  <p className="pane-desc">زیر هر بخش دکمهٔ «📍 اینجا گیر کردم» هست؛ مشکل را علامت بزنید تا استاد هوشمند از همان نقطه وارد گفتگو شود.</p>
                </div>
              </div>
              <div style={{ fontSize: `${fontScale}em` }}>
                <Blocks blocks={version.blocks ?? []} />
              </div>
              {(version.blocks ?? []).map((_, i) => (
                <div key={`stuck-${i}`}>
                  {stuckFor === i ? (
                    <div className="stuck-options">
                      <strong style={{ fontSize: '0.85rem' }}>مشکل شما دقیقاً چیست؟</strong>
                      <span className="muted" style={{ fontSize: '0.72rem' }}>
                        با انتخاب نوع مشکل، استاد هوشمند از همین نقطه وارد گفتگو می‌شود.
                      </span>
                      {STUCK_KINDS.map((k) => (
                        <button key={k.kind} type="button" onClick={() => void submitStuck(i, k.kind)}>
                          {k.label}
                        </button>
                      ))}
                      <input
                        className="input"
                        placeholder="توضیح اختیاری — مثلاً کدام قسمت"
                        value={stuckNote}
                        onChange={(e) => setStuckNote(e.target.value)}
                      />
                      <button type="button" className="link-btn" onClick={() => setStuckFor(null)}>
                        انصراف
                      </button>
                    </div>
                  ) : (
                    <div className="stuck-bar">
                      <button type="button" className="stuck-btn" onClick={() => setStuckFor(i)}>
                        📍 اینجا گیر کردم
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </>
          ) : (
            <div className="center-note">
              <div className="spinner" />
            </div>
          )}
        </section>

        {/* پنل چپ: استاد هوشمند با نردبان راهنمایی */}
        <section className={`learning-pane pane-tutor${activeTab === 'tutor' ? ' mobile-on' : ''}`} aria-label="استاد هوشمند">
          <div className="pane-head">
            <span className="pane-ico" aria-hidden="true">🤖</span>
            <div>
              <h3>استاد هوشمند</h3>
              <p className="pane-desc">پاسخ فقط بر پایهٔ منابع مجاز درس؛ حالت نردبان را انتخاب کنید تا سطح کمک را کنترل کنید.</p>
            </div>
          </div>
          <div className="ladder-bar">
            {HELP_MODES.map((m) => (
              <button
                key={m.mode}
                type="button"
                className={`ladder-btn${helpMode === m.mode ? ' on' : ''}`}
                onClick={() => setHelpMode(m.mode)}
                aria-pressed={helpMode === m.mode}
              >
                {m.label}
              </button>
            ))}
          </div>
          <div className="ladder-note">
            {HELP_MODES.find((m) => m.mode === helpMode)?.hint}
          </div>
          <div className="chat-box">
            {messages.length === 0 && (
              <p className="muted" style={{ fontSize: '0.82rem' }}>
                بپرس، یا روی «اینجا گیر کردم» بزن تا گفتگو از همان نقطه شروع شود. پاسخ‌ها فقط بر پایه منابع مجاز درس است.
              </p>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`chat-msg ${m.role}`}>
                <div>{m.content}</div>
                {(m.meta?.help_mode ?? null) && (
                  <div className="muted" style={{ fontSize: '0.7rem', marginTop: 4 }}>
                    حالت: {String(m.meta?.help_mode)} — پله نردبان: {String(m.meta?.ladder_level ?? '—')}/5
                  </div>
                )}
                {(m.citations ?? []).length > 0 && (
                  <div className="chat-citations">
                    {(m.citations ?? []).map((c, i) => (
                      <span key={i} className="citation-card" title={c.quote}>
                        📚 {c.resource_title ?? c.locator ?? 'منبع درس'}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {sending && (
              <div className="center-note" style={{ padding: 6 }}>
                <div className="spinner" />
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form className="chat-input-row" onSubmit={sendForm}>
            <input
              className="input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="پرسش خود را بنویس…"
              aria-label="متن پیام"
            />
            <button className="btn btn-primary btn-sm" type="submit" disabled={sending}>
              ارسال
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}
