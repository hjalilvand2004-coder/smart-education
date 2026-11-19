import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { Citation } from '../api'

interface ChatEntry {
  id: string
  role: string
  content: string
  citations?: Citation[] | null
  reported?: boolean
}

/** استاد هوشمند گفتگو‌محور — بدون جریان SSE برای سادگی. */
export default function Tutor({ courseId }: { courseId: string }) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatEntry[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reportFor, setReportFor] = useState<string | null>(null)
  const [reportText, setReportText] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const chatEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let alive = true
    api
      .post<{ id: string; mode: string; course_id: string }>('/tutor/sessions', {
        course_id: courseId,
        mode: 'LEARNING',
      })
      .then(async (s) => {
        if (!alive) return
        setSessionId(s.id)
        const history = await api.get<ChatEntry[]>(`/tutor/sessions/${s.id}/messages`)
        if (alive) setMessages(history || [])
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'ایجاد جلسه گفتگو ناموفق بود')
      })
    return () => {
      alive = false
    }
  }, [courseId])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages, sending])

  const send = useCallback(
    async (e: FormEvent) => {
      e.preventDefault()
      if (!sessionId || !input.trim() || sending) return
      const content = input.trim()
      setInput('')
      setMessages((prev) => [...prev, { id: `local-${Date.now()}`, role: 'user', content }])
      setSending(true)
      setError(null)
      try {
        const res = await api.post<ChatEntry>(`/tutor/sessions/${sessionId}/messages`, {
          content,
          stream: false,
        })
        setMessages((prev) => [
          ...prev,
          { id: res.id, role: 'assistant', content: res.content, citations: res.citations },
        ])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'ارسال پیام ناموفق بود')
      } finally {
        setSending(false)
      }
    },
    [sessionId, input, sending],
  )

  const submitReport = async (messageId: string) => {
    if (!reportText.trim()) return
    try {
      await api.post(`/tutor/messages/${messageId}/report`, { issue: reportText.trim() })
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, reported: true } : m)))
      setReportFor(null)
      setReportText('')
      setNotice('گزارش شما برای استاد درس ثبت شد.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ثبت گزارش ناموفق بود')
    }
  }

  if (error && sessionId === null) {
    return <div className="error-box">{error}</div>
  }

  return (
    <div className="card">
      <div className="card-title">
        <h2>استاد هوشمند — پرسش و پاسخ درسی</h2>
        <span className="badge badge-ai">پاسخ‌ها بر اساس منابع درس با ارجاع</span>
      </div>

      {notice && <div className="success-box">{notice}</div>}
      {error && <div className="error-box">{error}</div>}

      <div className="chat-box">
        {messages.length === 0 && !sending ? (
          <div className="empty-box">
            <strong>گفتگو را شروع کنید</strong>
            سؤال درسی خود را بنویسید؛ پاسخ با ارجاع به منابع درس ارائه می‌شود.
          </div>
        ) : null}
        {messages.map((m) => (
          <div key={m.id} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div className={`chat-msg ${m.role === 'user' ? 'user' : 'assistant'}`}>{m.content}</div>
            {m.role === 'assistant' && m.citations && m.citations.length > 0 && (
              <div className="chat-citations">
                <div className="muted">ارجاع‌ها:</div>
                {m.citations.map((c, i) => (
                  <div key={i} className="citation-card">
                    <div className="cite-title">{c.resource_title || 'منبع درس'}</div>
                    {c.locator ? <div>{c.locator}</div> : null}
                    {c.quote ? <div className="cite-quote">«{c.quote}»</div> : null}
                  </div>
                ))}
              </div>
            )}
            {m.role === 'assistant' && (
              <div className="report-issue-row">
                {m.reported ? (
                  <span className="badge badge-warn">گزارش‌شده — در دست بررسی استاد</span>
                ) : (
                  <button type="button" className="link-btn" onClick={() => setReportFor(reportFor === m.id ? null : m.id)}>
                    گزارش پاسخ نادرست
                  </button>
                )}
              </div>
            )}
            {reportFor === m.id && (
              <div className="edit-form" style={{ alignSelf: 'flex-end', width: '100%' }}>
                <label className="label" htmlFor={`issue-${m.id}`}>چه اشکالی در پاسخ وجود دارد؟</label>
                <textarea
                  id={`issue-${m.id}`}
                  className="textarea"
                  value={reportText}
                  onChange={(e) => setReportText(e.target.value)}
                  placeholder="مثلاً: پاسخ با تعریف کتاب هم‌خوانی ندارد"
                />
                <div className="btn-row" style={{ marginTop: 6 }}>
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => submitReport(m.id)}>
                    ثبت گزارش
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setReportFor(null)}>انصراف</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="chat-msg assistant">
            <div className="spinner" style={{ margin: 0, width: 18, height: 18, borderWidth: 2 }} />
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <form className="chat-input-row" onSubmit={send}>
        <textarea
          className="textarea"
          placeholder="سؤال خود را بنویسید…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send(e as unknown as FormEvent)
            }
          }}
        />
        <button type="submit" className="btn btn-primary" disabled={sending || !input.trim()}>
          ارسال
        </button>
      </form>
    </div>
  )
}
