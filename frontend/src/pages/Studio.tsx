import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, downloadBlob } from '../api'
import type {
  Block,
  ConceptGraph,
  ContentDocument,
  ContentVersion,
  DocumentSummary,
  ExportStatus,
  Job,
  Paged,
  Syllabus,
} from '../api'
import { isCourseStaff, useAuth } from '../auth'
import Blocks from '../components/Blocks'
import StatusBadge, { AIEstimateBadge, HumanApprovedBadge, kindLabel } from '../components/StatusBadge'

const POLL_INTERVAL_MS = 1500

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

function errText(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) return err.message
  return fallback
}

/** پیگیری یک Job تا وضعیت نهایی با فاصله ۱.۵ ثانیه. */
async function pollJob(
  jobId: string,
  onJob: (job: Job) => void,
  isCancelled: () => boolean,
): Promise<Job> {
  for (;;) {
    if (isCancelled()) throw new Error('پیگیری متوقف شد')
    const job = await api.get<Job>(`/jobs/${jobId}`)
    onJob(job)
    if (job.status === 'SUCCEEDED' || job.status === 'FAILED' || job.status === 'CANCELLED') {
      return job
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
  }
}

function JobPanel({ job, title }: { job: Job; title: string }) {
  const tone = job.status === 'RUNNING' || job.status === 'QUEUED' ? '' : job.status === 'SUCCEEDED' ? 'success' : 'danger'
  return (
    <div className="job-panel">
      <div className="card-title">
        <h3>{title}</h3>
        <StatusBadge status={job.status} />
      </div>
      <div className="progress-row">
        <div className="progress">
          <div className={`progress-fill ${tone}`} style={{ width: `${job.progress || 0}%` }} />
        </div>
        <span className="progress-value">{job.progress || 0}٪</span>
      </div>
      {job.steps && job.steps.length > 0 && (
        <ul className="steps-list-job">
          {job.steps.map((s, i) => (
            <li key={i}>
              <StatusBadge status={s.status === 'PENDING' ? 'QUEUED' : s.status === 'RUNNING' ? 'RUNNING' : s.status === 'SUCCEEDED' ? 'SUCCEEDED' : 'FAILED'} />
              <span>{s.name}</span>
              {s.note ? <span className="muted"> — {s.note}</span> : null}
            </li>
          ))}
        </ul>
      )}
      {job.error && <div className="error-box">{job.error}</div>}
    </div>
  )
}



// ---------------- درج سریع محتوای خودم (چسباندن متن) ----------------

type RawBlock = Record<string, unknown>

/** تحلیل متن آزادِ چسبانده‌شده به بلوک‌های ساختاری سند (عنوان/متن/فهرست/نکته/کد/فرمول). */
export function parsePastedText(text: string): RawBlock[] {
  const blocks: RawBlock[] = []
  const lines = text.replace(/\r/g, '').split('\n')
  let para: string[] = []
  let items: string[] = []
  let code: string[] | null = null
  const flushText = () => {
    const body = para.join(' ').trim()
    if (body) blocks.push({ type: 'text', body })
    para = []
  }
  const flushItems = () => {
    if (items.length) blocks.push({ type: 'text', items })
    items = []
  }
  for (const raw of lines) {
    const line = raw.trim()
    if (code !== null) {
      if (/^```\s*$/.test(line)) {
        blocks.push({ type: 'code', body: code.join('\n') })
        code = null
      } else {
        code.push(raw)
      }
      continue
    }
    if (!line) { flushText(); flushItems(); continue }
    if (/^```/.test(line)) { flushText(); flushItems(); code = []; continue }
    const heading = line.match(/^(#{1,4})\s+(.+)$/)
    if (heading) { flushText(); flushItems(); blocks.push({ type: 'heading', title: heading[2].trim() }); continue }
    const bullet = line.match(/^[-*•]\s+(.+)$/)
    if (bullet) { flushText(); items.push(bullet[1].trim()); continue }
    const formula = line.match(/^\$\$(.+)\$\$$/)
    if (formula) { flushText(); flushItems(); blocks.push({ type: 'formula', formula: formula[1].trim() }); continue }
    const note = line.match(/^(?:نکته|توجه)\s*[:：]\s*(.+)$/)
    if (note) { flushText(); flushItems(); blocks.push({ type: 'note', title: 'نکته', body: note[1].trim() }); continue }
    const ex = line.match(/^مثال\s*[:：]\s*(.+)$/)
    if (ex) { flushText(); flushItems(); blocks.push({ type: 'worked_example', question: ex[1].trim() }); continue }
    const drill = line.match(/^تمرین\s*[:：]\s*(.+)$/)
    if (drill) { flushText(); flushItems(); blocks.push({ type: 'exercise', question: drill[1].trim() }); continue }
    para.push(line)
  }
  if (code !== null && code.length) blocks.push({ type: 'code', body: code.join('\n') })
  flushText()
  flushItems()
  return blocks
}

/** مودال درج سریع: چسباندن متن، شمارش بلوک‌های شناسایی‌شده و افزودن به نسخهٔ پیش‌نویس. */
function PasteModal({
  onClose,
  onAdd,
  busy,
  error,
}: {
  onClose: () => void
  onAdd: (blocks: RawBlock[]) => void
  busy: boolean
  error: string | null
}) {
  const [text, setText] = useState('')
  const blocks = text.trim() ? parsePastedText(text) : []
  return (
    <div className="paste-overlay" onClick={onClose} role="presentation">
      <div className="paste-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="درج سریع محتوا">
        <div className="card-title">
          <h3>📝 درج سریع محتوای من</h3>
          <button type="button" className="btn btn-sm" onClick={onClose}>بستن</button>
        </div>
        <p className="muted paste-hint">
          محتوای خودتان را از هر جا کپی و اینجا بچسبانید؛ سامانه متن را به بلوک‌های ساختاری
          (عنوان با <code>#</code>، فهرست با <code>-</code>، کد با <code>```</code>، فرمول با
          <code>$$...$$</code> و نکته/مثال/تمرین با پیشوند همان واژه) تبدیل می‌کند و به نسخهٔ
          پیش‌نویسِ همین سند — در همان چارچوب سرفصل — اضافه می‌سازد.
        </p>
        <textarea
          className="textarea paste-textarea"
          placeholder={'مثال:\n## تعریف مشتق\nمشتق، نرخ تغییر لحظه‌ای تابع است.\n- دقیق و فرم‌پذیر\n- پایهٔ بهینه‌سازی\nنکته: اهمیت حد چپ و راست'}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="paste-meta">
          {blocks.length > 0
            ? <>✅ <b>{blocks.length}</b> بلوک شناسایی شد — با «افزودن» به سند می‌روند</>
            : 'متن را بچسبانید تا بلوک‌ها شناسایی شوند'}
        </div>
        {error && <div className="error-box">{error}</div>}
        <div className="btn-row" style={{ marginTop: 10 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || blocks.length === 0}
            onClick={() => onAdd(blocks)}
          >
            {busy ? '⏳ در حال افزودن…' : `➕ افزودن ${blocks.length || ''} بلوک به سند`}
          </button>
          <button type="button" className="btn" onClick={() => setText('')} disabled={busy}>پاک‌کردن</button>
        </div>
      </div>
    </div>
  )
}

// ---------------- فرم سند جدید ----------------

const GOALS = ['INTRO', 'CONCEPT_TEACHING', 'PROBLEM_SOLVING', 'REVIEW', 'PRACTICE']
const STYLES = ['ACADEMIC', 'APPLIED', 'EXAMPLE_BASED', 'STEPWISE']
const LANGS = ['FA', 'EN', 'FA_EN']
const COMPONENTS = [
  { key: 'definition', label: 'تعریف' },
  { key: 'example', label: 'مثال' },
  { key: 'exercise', label: 'تمرین' },
  { key: 'diagram', label: 'نمودار' },
  { key: 'summary', label: 'جمع‌بندی' },
  { key: 'references', label: 'منابع' },
]

function NewDocumentForm({
  courseId,
  onCreated,
  onCancel,
}: {
  courseId: string
  onCreated: (docId: string) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState('')
  const [goal, setGoal] = useState('CONCEPT_TEACHING')
  const [style, setStyle] = useState('EXAMPLE_BASED')
  const [language, setLanguage] = useState('FA')
  const [duration, setDuration] = useState('45')
  const [audience, setAudience] = useState('')
  const [graph, setGraph] = useState<ConceptGraph | null>(null)
  const [selectedConcepts, setSelectedConcepts] = useState<string[]>([])
  const [selectedTopics, setSelectedTopics] = useState<string[]>([])
  const [topicOptions, setTopicOptions] = useState<{ id: string; title: string }[]>([])
  const [components, setComponents] = useState<string[]>(['definition', 'example', 'exercise', 'summary', 'references'])
  const [resources, setResources] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .get<ConceptGraph>(`/courses/${courseId}/concept-graph`)
      .then((g) => alive && setGraph(g))
      .catch(() => alive && setGraph({ nodes: [], edges: [] }))
    return () => {
      alive = false
    }
  }, [courseId])

  // سرفصل‌های درس برای انتخاب دامنه تولید محتوا (متناسب با هر سرفصل)
  useEffect(() => {
    let alive = true
    api
      .get<Syllabus>(`/courses/${courseId}/syllabus`)
      .then((s) => {
        if (!alive) return
        setTopicOptions(s.chapters.flatMap((ch) => ch.topics.map((t) => ({ id: t.id, title: t.title }))))
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [courseId])

  const toggle = (list: string[], value: string, setter: (v: string[]) => void) => {
    setter(list.includes(value) ? list.filter((v) => v !== value) : [...list, value])
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const syllabus = await api.get<Syllabus>(`/courses/${courseId}/syllabus`)
      const resourceLines = resources
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean)
      const doc = await api.post<ContentDocument>('/content-documents', {
        course_id: courseId,
        syllabus_version_id: syllabus.id,
        title,
        goal,
        scope: { topic_ids: selectedTopics, concept_ids: selectedConcepts },
        audience_level: audience || null,
        duration_minutes: Number(duration) || null,
        language,
        style,
        components,
        source_resource_ids: [],
        constraints: resourceLines.length ? { extra_resources_text: resourceLines } : null,
      })
      onCreated(doc.id)
    } catch (err) {
      setError(errText(err, 'ایجاد سند ناموفق بود'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <div className="card-title">
        <h2>سند آموزشی جدید</h2>
        <button type="button" className="btn btn-sm" onClick={onCancel}>انصراف</button>
      </div>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="form-item form-item-full">
            <label className="label" htmlFor="doc-title">عنوان سند</label>
            <input id="doc-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="form-item">
            <label className="label" htmlFor="doc-goal">هدف آموزشی</label>
            <select id="doc-goal" className="select" value={goal} onChange={(e) => setGoal(e.target.value)}>
              {GOALS.map((g) => (
                <option key={g} value={g}>{kindLabel(g)}</option>
              ))}
            </select>
          </div>
          <div className="form-item">
            <label className="label" htmlFor="doc-style">سبک تدوین</label>
            <select id="doc-style" className="select" value={style} onChange={(e) => setStyle(e.target.value)}>
              {STYLES.map((s) => (
                <option key={s} value={s}>{kindLabel(s)}</option>
              ))}
            </select>
          </div>
          <div className="form-item">
            <label className="label" htmlFor="doc-lang">زبان</label>
            <select id="doc-lang" className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGS.map((l) => (
                <option key={l} value={l}>{kindLabel(l)}</option>
              ))}
            </select>
          </div>
          <div className="form-item">
            <label className="label" htmlFor="doc-duration">مدت مطالعه (دقیقه)</label>
            <input id="doc-duration" className="input" type="number" min="5" max="240" value={duration} onChange={(e) => setDuration(e.target.value)} />
          </div>
          <div className="form-item form-item-full">
            <label className="label" htmlFor="doc-audience">سطح مخاطب (اختیاری)</label>
            <input id="doc-audience" className="input" value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="مثلاً: سال دوم کارشناسی" />
          </div>
          <div className="form-item form-item-full">
            <span className="label">سرفصل‌های هدف</span>
            {topicOptions.length === 0 ? (
              <div className="muted">سرفصلی برای این درس ثبت نشده است؛ از صفحه «برنامه‌یار۳۶۰» یا ورود سرفصل اضافه کنید.</div>
            ) : (
              <div className="chip-list">
                {topicOptions.map((t) => (
                  <button
                    type="button"
                    key={t.id}
                    className={`chip${selectedTopics.includes(t.id) ? ' selected' : ''}`}
                    onClick={() => toggle(selectedTopics, t.id, setSelectedTopics)}
                  >
                    {t.title}
                  </button>
                ))}
              </div>
            )}
            <div className="hint">اگر سرفصلی انتخاب شود، محتوا متناسب با همان سرفصل(ها) تولید می‌شود.</div>
          </div>
          <div className="form-item form-item-full">
            <span className="label">مفاهیم هدف</span>
            {graph === null ? (
              <div className="muted">در حال دریافت مفاهیم…</div>
            ) : graph.nodes.length === 0 ? (
              <div className="muted">برای این درس مفهومی ثبت نشده است.</div>
            ) : (
              <div className="chip-list">
                {graph.nodes.map((n) => (
                  <button
                    type="button"
                    key={n.id}
                    className={`chip${selectedConcepts.includes(n.id) ? ' selected' : ''}`}
                    onClick={() => toggle(selectedConcepts, n.id, setSelectedConcepts)}
                  >
                    {n.name}
                  </button>
                ))}
              </div>
            )}
            <div className="hint">مفاهیم انتخابی به AI برای پوشش محتوا معرفی می‌شوند.</div>
          </div>
          <div className="form-item form-item-full">
            <span className="label">اجزای محتوا</span>
            <div className="chip-list">
              {COMPONENTS.map((c) => (
                <button
                  type="button"
                  key={c.key}
                  className={`chip${components.includes(c.key) ? ' selected' : ''}`}
                  onClick={() => toggle(components, c.key, setComponents)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
          <div className="form-item form-item-full">
            <label className="label" htmlFor="doc-resources">منابع ساده متنی (هر خط یک منبع)</label>
            <textarea
              id="doc-resources"
              className="textarea"
              value={resources}
              onChange={(e) => setResources(e.target.value)}
              placeholder={'فصل ۳ کتاب مبانی…\nجزوه استاد…'}
            />
          </div>
        </div>
        {error && <div className="error-box">{error}</div>}
        <div className="btn-row" style={{ marginTop: 10 }}>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? 'در حال ایجاد…' : 'ایجاد سند'}
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------- ویرایشگر بلوک ----------------

function BlockEditor({
  block,
  revision,
  onSave,
  onCancel,
}: {
  block: Block
  revision: number
  onSave: (patch: Partial<Block>) => Promise<void>
  onCancel: () => void
}) {
  const [title, setTitle] = useState(block.title || '')
  const [body, setBody] = useState(block.body || '')
  const [question, setQuestion] = useState(block.question || '')
  const [answer, setAnswer] = useState(block.answer || '')
  const [explanation, setExplanation] = useState(block.explanation || '')
  const [formula, setFormula] = useState(block.formula || '')
  const [items, setItems] = useState((block.items || []).join('\n'))
  const [steps, setSteps] = useState((block.steps || []).join('\n'))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const patch: Partial<Block> = {}
    if (title !== (block.title || '')) patch.title = title
    if (body !== (block.body || '')) patch.body = body
    if (question !== (block.question || '')) patch.question = question
    if (answer !== (block.answer || '')) patch.answer = answer
    if (explanation !== (block.explanation || '')) patch.explanation = explanation
    if (formula !== (block.formula || '')) patch.formula = formula
    const itemsList = items.split('\n').map((l) => l.trim()).filter(Boolean)
    if (JSON.stringify(itemsList) !== JSON.stringify(block.items || [])) patch.items = itemsList
    const stepsList = steps.split('\n').map((l) => l.trim()).filter(Boolean)
    if (JSON.stringify(stepsList) !== JSON.stringify(block.steps || [])) patch.steps = stepsList
    try {
      await onSave(patch)
    } catch (err) {
      setError(errText(err, 'ذخیره تغییرات ناموفق بود'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="edit-form" onSubmit={submit}>
      <h4>ویرایش بلوک «{kindLabel(BLOCK_LABELS[block.type] || block.type)}»</h4>
      <div className="hint" style={{ marginBottom: 8 }}>
        نسخه مرجع: {revision} — در صورت تداخل هم‌زمان، پیام مناسب نمایش داده می‌شود.
      </div>
      <div className="form-item" style={{ marginBottom: 8 }}>
        <label className="label" htmlFor={`b-${block.id}-title`}>عنوان</label>
        <input id={`b-${block.id}-title`} className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      {block.type === 'formula' ? (
        <div className="form-item" style={{ marginBottom: 8 }}>
          <label className="label" htmlFor={`b-${block.id}-formula`}>فرمول (LaTeX)</label>
          <textarea id={`b-${block.id}-formula`} className="textarea" dir="ltr" value={formula} onChange={(e) => setFormula(e.target.value)} />
        </div>
      ) : (
        <div className="form-item" style={{ marginBottom: 8 }}>
          <label className="label" htmlFor={`b-${block.id}-body`}>متن</label>
          <textarea id={`b-${block.id}-body`} className="textarea" value={body} onChange={(e) => setBody(e.target.value)} />
        </div>
      )}
      {(block.type === 'worked_example' || block.type === 'exercise' || block.type === 'self_check') && (
        <div className="form-item" style={{ marginBottom: 8 }}>
          <label className="label" htmlFor={`b-${block.id}-question`}>صورت مسئله / پرسش</label>
          <textarea id={`b-${block.id}-question`} className="textarea" value={question} onChange={(e) => setQuestion(e.target.value)} />
        </div>
      )}
      {(block.type === 'worked_example' || block.type === 'self_check') && (
        <>
          <div className="form-item" style={{ marginBottom: 8 }}>
            <label className="label" htmlFor={`b-${block.id}-steps`}>گام‌های حل (هر خط یک گام)</label>
            <textarea id={`b-${block.id}-steps`} className="textarea" value={steps} onChange={(e) => setSteps(e.target.value)} />
          </div>
          <div className="form-item" style={{ marginBottom: 8 }}>
            <label className="label" htmlFor={`b-${block.id}-answer`}>پاسخ</label>
            <textarea id={`b-${block.id}-answer`} className="textarea" value={answer} onChange={(e) => setAnswer(e.target.value)} />
          </div>
        </>
      )}
      {(block.type === 'exercise' || block.type === 'reference' || block.type === 'self_check' || block.type === 'text') && (
        <div className="form-item" style={{ marginBottom: 8 }}>
          <label className="label" htmlFor={`b-${block.id}-items`}>موارد فهرستی (هر خط یک مورد)</label>
          <textarea id={`b-${block.id}-items`} className="textarea" value={items} onChange={(e) => setItems(e.target.value)} />
        </div>
      )}
      <div className="form-item" style={{ marginBottom: 8 }}>
        <label className="label" htmlFor={`b-${block.id}-expl`}>توضیح تکمیلی</label>
        <textarea id={`b-${block.id}-expl`} className="textarea" value={explanation} onChange={(e) => setExplanation(e.target.value)} />
      </div>
      {error && <div className="error-box">{error}</div>}
      <div className="btn-row">
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
          {busy ? 'در حال ذخیره…' : 'ذخیره تغییرات'}
        </button>
        <button type="button" className="btn btn-sm" onClick={onCancel}>انصراف</button>
      </div>
    </form>
  )
}

const BLOCK_LABELS: Record<string, string> = {
  heading: 'عنوان',
  text: 'متن',
  definition: 'تعریف',
  note: 'نکته',
  worked_example: 'مثال حل‌شده',
  exercise: 'تمرین',
  table: 'جدول',
  formula: 'فرمول',
  image: 'تصویر',
  code: 'کد',
  self_check: 'خودارزیابی',
  summary: 'جمع‌بندی',
  reference: 'منبع',
}

// ---------------- نمای نسخه محتوا ----------------

interface ExportState {
  busy: boolean
  jobId?: string
  exportJobId?: string
  job?: Job | null
  result?: ExportStatus | null
  error?: string | null
}

function VersionView({
  courseId,
  doc,
  version,
  onVersionUpdate,
  onDocRefresh,
}: {
  courseId: string
  doc: ContentDocument
  version: ContentVersion
  onVersionUpdate: (v: ContentVersion) => void
  onDocRefresh: () => Promise<void>
}) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [editingBlockId, setEditingBlockId] = useState<string | null>(null)
  const [regenBlockId, setRegenBlockId] = useState<string | null>(null)
  const [regenInstruction, setRegenInstruction] = useState('')
  const [reviewNotes, setReviewNotes] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [exportStates, setExportStates] = useState<Record<string, ExportState>>({})
  const [pasteOpen, setPasteOpen] = useState(false)
  const [pasteBusy, setPasteBusy] = useState(false)
  const [pasteError, setPasteError] = useState<string | null>(null)
  const pollCancelRef = useRef(false)

  useEffect(() => {
    pollCancelRef.current = false
    return () => {
      pollCancelRef.current = true
    }
  }, [])

  const trackJob = useCallback(
    async (jobId: string, title: string, onDone: (j: Job) => Promise<void>) => {
      setError(null)
      setNotice(null)
      try {
        const finalJob = await pollJob(jobId, setJob, () => pollCancelRef.current)
        if (finalJob.status === 'FAILED') {
          setError(`«${title}» ناموفق بود: ${finalJob.error || 'خطای نامشخص'}`)
        } else if (finalJob.status === 'CANCELLED') {
          setError(`«${title}» لغو شد.`)
        } else {
          await onDone(finalJob)
          setNotice(`«${title}» با موفقیت انجام شد.`)
        }
      } catch (err) {
        if (!pollCancelRef.current) setError(errText(err, 'پیگیری Job ناموفق بود'))
      }
    },
    [],
  )

  const saveBlock = async (blockId: string, patch: Partial<Block>) => {
    setError(null)
    try {
      const updated = await api.patch<ContentVersion>(
        `/content-versions/${version.id}/blocks/${blockId}`,
        { patch, expected_revision: version.revision },
      )
      onVersionUpdate(updated)
      setEditingBlockId(null)
      setNotice('تغییرات بلوک ذخیره شد.')
    } catch (err) {
      const apiErr = err as { status?: number; code?: string; message?: string }
      if (apiErr.status === 409 || apiErr.code === 'CONFLICT') {
        setError('تغییر هم‌زمان توسط کاربر دیگری انجام شده است؛ صفحه را تازه‌سازی کنید و دوباره تلاش کنید.')
        try {
          const fresh = await api.get<ContentVersion>(`/content-versions/${version.id}`)
          onVersionUpdate(fresh)
        } catch {
          /* نادیده */
        }
      } else {
        setError(apiErr.message || 'ذخیره تغییرات ناموفق بود')
      }
      throw err
    }
  }

  const regenerateBlock = async (blockId: string) => {
    setError(null)
    setBusyAction(`regen-${blockId}`)
    try {
      const start = await api.post<Record<string, string>>(
        `/content-versions/${version.id}/blocks/${blockId}/regenerate`,
        { instruction: regenInstruction || null },
        newIdempotencyKey(),
      )
      setRegenBlockId(null)
      setRegenInstruction('')
      await trackJob(start.job_id, 'بازتولید بلوک', async () => {
        const fresh = await api.get<ContentVersion>(`/content-versions/${version.id}`)
        onVersionUpdate(fresh)
        await onDocRefresh()
      })
    } catch (err) {
      setError(errText(err, 'شروع بازتولید ناموفق بود'))
    } finally {
      setBusyAction(null)
    }
  }

  const review = async (decision: string) => {
    setError(null)
    setBusyAction(decision)
    try {
      await api.post(`/content-versions/${version.id}/reviews`, {
        decision,
        notes: reviewNotes || null,
      })
      setReviewNotes('')
      const fresh = await api.get<ContentVersion>(`/content-versions/${version.id}`)
      onVersionUpdate(fresh)
      await onDocRefresh()
      setNotice(
        decision === 'SUBMIT_FOR_REVIEW'
          ? 'نسخه برای بررسی ارسال شد.'
          : decision === 'APPROVE'
            ? 'نسخه تأیید شد؛ برای انتشار آماده است.'
            : 'درخواست اصلاح ثبت شد.',
      )
    } catch (err) {
      setError(errText(err, 'ثبت بررسی ناموفق بود'))
    } finally {
      setBusyAction(null)
    }
  }

  const publish = async () => {
    setError(null)
    setBusyAction('publish')
    try {
      await api.post(`/content-versions/${version.id}/publish`)
      const fresh = await api.get<ContentVersion>(`/content-versions/${version.id}`)
      onVersionUpdate(fresh)
      await onDocRefresh()
      setNotice('محتوا منتشر شد و برای دانشجویان درس قابل مشاهده است.')
    } catch (err) {
      setError(errText(err, 'انتشار ناموفق بود'))
    } finally {
      setBusyAction(null)
    }
  }

  const startExport = async (format: string) => {
    setError(null)
    setExportStates((prev) => ({ ...prev, [format]: { busy: true } }))
    try {
      const start = await api.post<Record<string, string>>(
        `/content-versions/${version.id}/exports`,
        { format },
        newIdempotencyKey(),
      )
      const exportJobId = start.export_job_id
      setExportStates((prev) => ({ ...prev, [format]: { busy: true, jobId: start.job_id, exportJobId } }))
      await trackJob(start.job_id, `خروجی ${format}`, async () => {
        if (!exportJobId) return
        const status = await api.get<ExportStatus>(`/exports/${exportJobId}`)
        setExportStates((prev) => ({ ...prev, [format]: { busy: false, jobId: start.job_id, exportJobId, result: status } }))
      })
      setExportStates((prev) => ({ ...prev, [format]: { ...prev[format], busy: false } }))
    } catch (err) {
      setExportStates((prev) => ({ ...prev, [format]: { busy: false, error: errText(err, 'شروع خروجی ناموفق بود') } }))
    }
  }

  const downloadExport = async (exportJobId: string, fileName: string) => {
    try {
      const blob = await api.getBlob(`/exports/${exportJobId}/download`)
      downloadBlob(blob, fileName)
    } catch (err) {
      setError(errText(err, 'دانلود فایل ناموفق بود'))
    }
  }

  const submitPaste = async (blocks: RawBlock[]) => {
    setPasteBusy(true)
    setPasteError(null)
    try {
      const updated = await api.post<ContentVersion>(
        `/content-versions/${version.id}/blocks/bulk`,
        { blocks },
      )
      onVersionUpdate(updated)
      setPasteOpen(false)
      setNotice('محتوای شما به‌صورت بلوک‌های ساختاری به سند اضافه شد.')
    } catch (err) {
      setPasteError(errText(err, 'افزودن بلوک‌ها ناموفق بود'))
    } finally {
      setPasteBusy(false)
    }
  }

  const qc = version.qc_report
  const coveredCount = qc?.coverage?.filter((c) => c.covered).length ?? 0
  const coverageTotal = qc?.coverage?.length ?? 0
  const coveragePct = coverageTotal ? Math.round((coveredCount / coverageTotal) * 100) : 0
  const staffUser = isCourseStaff(user, courseId)
  const isProfessor = doc && (user?.course_roles || []).some((cr) => cr.course_id === courseId && cr.role === 'PROFESSOR')
  const canPublish = Boolean(user && (isProfessor || user.role === 'EDUCATION_ADMIN' || user.role === 'TECH_ADMIN'))

  return (
    <>
      <div className="card">
        <div className="card-title">
          <h3>
            نسخه {version.version_number} — بازبینی {version.revision}
          </h3>
          <div className="badge-row">
            <StatusBadge status={version.status} />
            {version.generated_by === 'AI' ? <AIEstimateBadge label="تولید با AI" /> : <HumanApprovedBadge label="ویرایش انسانی" />}
          </div>
        </div>
        <div className="muted">
          نسخه‌های دیگر: {doc.versions.map((v) => `v${v.version_number}`).join('، ') || '—'}
        </div>
        {notice && <div className="success-box">{notice}</div>}
        {error && <div className="error-box">{error}</div>}
        {/* گام‌نمای جریان کار استودیو */}
        <div className="studio-stepper" aria-label="مراحل جریان کار محتوا">
          {[
            { n: '۱', label: 'سند و دامنه', active: true },
            { n: '۲', label: 'تولید / درج محتوا', active: ['DRAFT', 'GENERATED', 'NEEDS_REVISION'].includes(version.status) },
            { n: '۳', label: 'بازبینی', active: version.status === 'UNDER_REVIEW' },
            { n: '۴', label: 'تأیید و انتشار', active: ['APPROVED', 'PUBLISHED'].includes(version.status) },
          ].map((s) => (
            <span key={s.n} className={`stepper-step${s.active ? ' active' : ''}`}>
              <span className="stepper-num">{s.n}</span>
              <span className="stepper-label">{s.label}</span>
            </span>
          ))}
        </div>

        {staffUser && ['DRAFT', 'GENERATED', 'NEEDS_REVISION'].includes(version.status) && (
          <div className="studio-toolbar" style={{ marginTop: 10 }}>
            <button type="button" className="btn studio-paste-btn" onClick={() => { setPasteError(null); setPasteOpen(true) }}>
              📝 درج سریع محتوای من (کپی/چسباندن)
            </button>
            <span className="muted studio-toolbar-hint">متن آزاد ← بلوک ساختاری، در چارچوب سرفصل همان سند</span>
          </div>
        )}

        {pasteOpen && (
          <PasteModal
            onClose={() => setPasteOpen(false)}
            onAdd={(blocks) => void submitPaste(blocks)}
            busy={pasteBusy}
            error={pasteError}
          />
        )}

        {staffUser && (
          <div className="edit-form" style={{ marginTop: 10 }}>
            <span className="label">اقدامات نسخه</span>
            <textarea
              className="textarea"
              placeholder="یادداشت بررسی (اختیاری)"
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              style={{ minHeight: 60 }}
            />
            <div className="btn-row" style={{ marginTop: 8 }}>
              {(version.status === 'GENERATED' || version.status === 'NEEDS_REVISION') && (
                <button type="button" className="btn btn-primary btn-sm" disabled={busyAction !== null} onClick={() => review('SUBMIT_FOR_REVIEW')}>
                  ارسال به بررسی
                </button>
              )}
              {version.status === 'UNDER_REVIEW' && (
                <button type="button" className="btn btn-success btn-sm" disabled={busyAction !== null} onClick={() => review('APPROVE')}>
                  تأیید نسخه
                </button>
              )}
              {(version.status === 'UNDER_REVIEW' || version.status === 'GENERATED') && (
                <button type="button" className="btn btn-sm" disabled={busyAction !== null} onClick={() => review('REQUEST_CHANGES')}>
                  درخواست اصلاح
                </button>
              )}
              {version.status === 'APPROVED' && canPublish && (
                <button type="button" className="btn btn-success btn-sm" disabled={busyAction !== null} onClick={publish}>
                  انتشار نسخه
                </button>
              )}
              {version.status === 'APPROVED' && !canPublish && (
                <span className="inline-alert">انتشار فقط توسط استاد درس انجام می‌شود.</span>
              )}
              {version.status === 'PUBLISHED' && (
                <span className="badge badge-success">این نسخه منتشر شده و برای دانشجویان قابل مشاهده است.</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* گزارش QC */}
      {qc && (
        <div className="card">
          <div className="card-title">
            <h3>گزارش کنترل کیفیت (QC)</h3>
            <div className="badge-row">
              <span className={`badge badge-${qc.overall === 'PASS' ? 'success' : qc.overall === 'WARN' ? 'warn' : 'danger'}`}>
                {qc.overall === 'PASS' ? 'بدون اشکال' : qc.overall === 'WARN' ? 'با هشدار' : 'نامنطبق'}
              </span>
              <span className="badge badge-neutral">پوشش اهداف: {coveragePct}٪</span>
            </div>
          </div>
          <div className="progress-row">
            <div className="progress">
              <div
                className={`progress-fill ${coveragePct === 100 ? 'success' : coveragePct >= 60 ? 'warn' : 'danger'}`}
                style={{ width: `${coveragePct}%` }}
              />
            </div>
            <span className="progress-value">{coveragePct}٪</span>
          </div>
          {qc.coverage && qc.coverage.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {qc.coverage.map((c) => (
                <div key={c.objective_id} className="objective-row">
                  <span className={`badge badge-${c.covered ? 'success' : 'danger'}`}>
                    {c.covered ? 'پوشش داده شده' : 'پوشش نیافته'}
                  </span>
                  <span className="muted">هدف {c.objective_id.slice(0, 8)}… — شواهد: {c.evidence_blocks?.length || 0} بلوک</span>
                </div>
              ))}
            </div>
          )}
          {qc.structure_warnings && qc.structure_warnings.length > 0 && (
            <div className="qc-warnings" style={{ marginTop: 8 }}>
              <strong className="qc-warning-item">هشدارهای ساختاری:</strong>
              <ul>
                {qc.structure_warnings.map((w, i) => (
                  <li key={i} className="qc-warning-item">{w}</li>
                ))}
              </ul>
            </div>
          )}
          {(qc.out_of_scope_concepts?.length ?? 0) > 0 || (qc.missing_sources?.length ?? 0) > 0 || (qc.invalid_refs?.length ?? 0) > 0 ? (
            <div className="inline-alert">
              مفاهیم خارج از دامنه: {qc.out_of_scope_concepts?.length || 0} — منابع جاافتاده: {qc.missing_sources?.length || 0} — ارجاع نامعتبر: {qc.invalid_refs?.length || 0}
            </div>
          ) : null}
        </div>
      )}

      {job && <JobPanel job={job} title="وضعیت فرایند پس‌زمینه" />}

      {/* بلوک‌ها */}
      <div className="card">
        <div className="card-title">
          <h3>بلوک‌های محتوا ({version.blocks?.length || 0})</h3>
          <span className="muted">برای ویرایش، نشانگر را روی بلوک ببرید یا لمس کنید</span>
        </div>
        {(version.blocks || []).map((block) => (
          <div key={block.id} className="block-shell">
            <div className="block-shell-bar">
              <button type="button" className="btn btn-sm" onClick={() => setEditingBlockId(editingBlockId === block.id ? null : block.id)}>
                ویرایش
              </button>
              <button type="button" className="btn btn-sm" onClick={() => setRegenBlockId(regenBlockId === block.id ? null : block.id)}>
                بازتولید این بخش
              </button>
            </div>
            {regenBlockId === block.id && (
              <div className="edit-form">
                <label className="label" htmlFor={`regen-${block.id}`}>دستور بازتولید (اختیاری)</label>
                <input
                  id={`regen-${block.id}`}
                  className="input"
                  value={regenInstruction}
                  onChange={(e) => setRegenInstruction(e.target.value)}
                  placeholder="مثلاً: مثال را ملموس‌تر کن و به صنعت نفت اشاره کن"
                />
                <div className="btn-row" style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={busyAction === `regen-${block.id}`}
                    onClick={() => regenerateBlock(block.id)}
                  >
                    {busyAction === `regen-${block.id}` ? 'در حال بازتولید…' : 'شروع بازتولید'}
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setRegenBlockId(null)}>انصراف</button>
                </div>
              </div>
            )}
            {editingBlockId === block.id ? (
              <BlockEditor
                block={block}
                revision={version.revision}
                onSave={(patch) => saveBlock(block.id, patch)}
                onCancel={() => setEditingBlockId(null)}
              />
            ) : (
              <Blocks blocks={[block]} />
            )}
          </div>
        ))}
        {version.human_changes && version.human_changes.length > 0 && (
          <div className="muted" style={{ marginTop: 8 }}>
            تغییرات انسانی ثبت‌شده: {version.human_changes.length} مورد
          </div>
        )}
      </div>

      {/* خروجی‌ها */}
      <div className="card">
        <div className="card-title">
          <h3>خروجی‌های قابل دانلود</h3>
        </div>
        <div className="export-row">
          {['PDF', 'PPTX', 'HTML', 'DOCX'].map((f) => {
            const st = exportStates[f]
            return (
              <div key={f} className="export-result">
                <button type="button" className="btn btn-sm" disabled={st?.busy} onClick={() => startExport(f)}>
                  {st?.busy ? `در حال ساخت ${f}…` : `ساخت ${f}`}
                </button>
                {st?.error && <span className="error-box" style={{ margin: 0 }}>{st.error}</span>}
                {st?.result &&
                  (st.result.artifacts.length > 0 ? (
                    st.result.artifacts.map((a) => (
                      <button
                        key={a.id}
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => downloadExport(st.exportJobId || st.result!.id, a.file_name)}
                      >
                        دانلود {f} ({a.size ? Math.round(a.size / 1024) : '?'} KB)
                      </button>
                    ))
                  ) : (
                    <span className="muted">فایل هنوز آماده نیست</span>
                  ))}
                {st?.job && !st.result && st.job.status !== 'SUCCEEDED' && (
                  <span className="muted">{st.job.status === 'FAILED' ? 'ساخت ناموفق بود' : 'در حال پردازش…'}</span>
                )}
              </div>
            )
          })}
        </div>
        <p className="hint">
          هر خروجی با شناسه یکتا (Idempotency-Key) ساخته می‌شود؛ تکرار کلیک کوتاه فایل تکراری نمی‌سازد.
        </p>
        <button type="button" className="link-btn" onClick={() => navigate(`/studio/${courseId}`)}>
          بازگشت به فهرست اسناد
        </button>
      </div>
    </>
  )
}

// ---------------- نمای سند ----------------

function DocumentView({
  courseId,
  docId,
  onBackToList,
}: {
  courseId: string
  docId: string
  onBackToList: () => void
}) {
  const { user } = useAuth()
  const [doc, setDoc] = useState<ContentDocument | null>(null)
  const [version, setVersion] = useState<ContentVersion | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const pollCancelRef = useRef(false)

  useEffect(() => {
    pollCancelRef.current = false
    return () => {
      pollCancelRef.current = true
    }
  }, [])

  const selectedVersionRef = useRef<string | null>(null)

  const loadDoc = useCallback(async () => {
    const d = await api.get<ContentDocument>(`/content-documents/${docId}`)
    setDoc(d)
    const vid = selectedVersionRef.current || d.current_version_id || (d.versions[0]?.id ?? null)
    if (vid) {
      selectedVersionRef.current = vid
      setSelectedVersionId(vid)
      const v = await api.get<ContentVersion>(`/content-versions/${vid}`)
      setVersion(v)
    } else {
      setVersion(null)
    }
  }, [docId])

  useEffect(() => {
    let alive = true
    loadDoc().catch((err) => alive && setError(errText(err, 'دریافت سند ناموفق بود')))
    return () => {
      alive = false
    }
  }, [docId, loadDoc])

  const loadVersionById = async (vid: string) => {
    selectedVersionRef.current = vid
    setSelectedVersionId(vid)
    setError(null)
    try {
      const v = await api.get<ContentVersion>(`/content-versions/${vid}`)
      setVersion(v)
    } catch (err) {
      setError(errText(err, 'دریافت نسخه ناموفق بود'))
    }
  }

  const startGeneration = async () => {
    setError(null)
    setNotice(null)
    setGenerating(true)
    setJob(null)
    try {
      const start = await api.post<Record<string, string>>(
        `/content-documents/${docId}/generation-jobs`,
        { mode: 'FULL', auto_confirm: true },
        newIdempotencyKey(),
      )
      if (start.idempotent_replay) {
        setNotice('این عملیات پیش‌تر با همین کلید ثبت شده بود؛ همان Job ادامه یافت.')
      }
      const finalJob = await pollJob(start.job_id, setJob, () => pollCancelRef.current)
      if (finalJob.status === 'SUCCEEDED') {
        selectedVersionRef.current = null
        setSelectedVersionId(null)
        await loadDoc()
        setNotice('تولید محتوا با موفقیت کامل شد.')
      } else {
        setError(`تولید محتوا ناموفق بود: ${finalJob.error || 'خطای نامشخص'}`)
      }
    } catch (err) {
      if (!pollCancelRef.current) setError(errText(err, 'شروع تولید ناموفق بود'))
    } finally {
      setGenerating(false)
    }
  }

  if (error && doc === null) return <div className="error-box">{error}</div>
  if (doc === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت سند…
      </div>
    )
  }

  const staffUser = isCourseStaff(user, courseId)

  return (
    <>
      <div className="page-header">
        <div>
          <h1>{doc.title}</h1>
          <div className="subtitle">
            هدف: {kindLabel(doc.goal)} — سبک: {kindLabel(doc.style)} — زبان: {kindLabel(doc.language)}
            {doc.duration_minutes ? ` — مدت: ${doc.duration_minutes} دقیقه` : ''}
          </div>
          <div className="badge-row" style={{ marginTop: 6 }}>
            {doc.components.map((c) => (
              <span key={c} className="badge badge-neutral">{kindLabel(c) || c}</span>
            ))}
          </div>
        </div>
        <div className="btn-row">
          <button type="button" className="btn btn-sm" onClick={onBackToList}>فهرست اسناد</button>
          <button type="button" className="btn btn-primary btn-sm" disabled={generating} onClick={startGeneration}>
            {generating ? 'تولید در جریان است…' : 'تولید با AI (کامل)'}
          </button>
        </div>
      </div>

      {notice && <div className="success-box">{notice}</div>}
      {error && <div className="error-box">{error}</div>}

      {doc.versions.length > 0 && (
        <div className="card">
          <h3>نسخه‌های سند</h3>
          <div className="chip-list">
            {doc.versions.map((v) => (
              <button
                key={v.id}
                type="button"
                className={`version-chip${selectedVersionId === v.id ? ' selected' : ''}`}
                onClick={() => loadVersionById(v.id)}
              >
                نسخه {v.version_number}
                <StatusBadge status={v.status} />
              </button>
            ))}
          </div>
        </div>
      )}

      {job && generating && <JobPanel job={job} title="تولید محتوا با AI" />}

      {version ? (
        <VersionView
          courseId={courseId}
          doc={doc}
          version={version}
          onVersionUpdate={setVersion}
          onDocRefresh={async () => {
            const d = await api.get<ContentDocument>(`/content-documents/${docId}`)
            setDoc(d)
          }}
        />
      ) : (
        <div className="empty-box">
          <strong>هنوز نسخه‌ای تولید نشده است</strong>
          با دکمه «تولید با AI (کامل)» پیش‌نویس آموزشی بر اساس سرفصل مصوب ساخته می‌شود؛ سپس می‌توانید بلوک‌ها را ویرایش، بررسی، تأیید و منتشر کنید.
          {staffUser ? '' : ' (فقط کارکنان درس اجازه تولید دارند.)'}
        </div>
      )}
    </>
  )
}

// ---------------- صفحه اصلی استودیو ----------------

export default function Studio() {
  const { courseId = '' } = useParams()
  const { user } = useAuth()
  const [docs, setDocs] = useState<Paged<DocumentSummary> | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [openDocId, setOpenDocId] = useState<string | null>(null)
  const [creatingNew, setCreatingNew] = useState(false)

  useEffect(() => {
    document.title = 'استودیوی محتوا | دانشجو۳۶۰'
  }, [])

  const loadDocs = useCallback(async () => {
    try {
      const rows = await api.get<Paged<DocumentSummary>>(`/content-documents?course_id=${encodeURIComponent(courseId)}`)
      setDocs(rows)
      setListError(null)
    } catch (err) {
      setListError(errText(err, 'دریافت فهرست اسناد ناموفق بود'))
    }
  }, [courseId])

  useEffect(() => {
    loadDocs()
  }, [loadDocs])

  const staffUser = isCourseStaff(user, courseId)

  if (!staffUser) {
    return (
      <div className="empty-box">
        <strong>دسترسی به استودیو مجاز نیست</strong>
        استودیوی محتوا فقط برای استاد، دستیار آموزشی، مدیر گروه و مدیران سامانه فعال است.
      </div>
    )
  }

  if (openDocId) {
    return (
      <DocumentView
        courseId={courseId}
        docId={openDocId}
        onBackToList={() => {
          setOpenDocId(null)
          loadDocs()
        }}
      />
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>استودیوی محتوا</h1>
          <div className="subtitle">
            ساخت، ویرایش، بررسی و انتشار محتوای آموزشی با کمک AI — همه تغییرات با «بازبینی انسانی» کنترل می‌شود.
          </div>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setCreatingNew(!creatingNew)}>
          {creatingNew ? 'بستن فرم' : 'سند جدید'}
        </button>
      </div>

      {creatingNew && (
        <NewDocumentForm
          courseId={courseId}
          onCreated={(docId) => {
            setCreatingNew(false)
            loadDocs()
            setOpenDocId(docId)
          }}
          onCancel={() => setCreatingNew(false)}
        />
      )}

      {listError && <div className="error-box">{listError}</div>}

      {docs === null ? (
        <div className="center-note">
          <div className="spinner" />
          در حال دریافت اسناد…
        </div>
      ) : docs.items.length === 0 ? (
        <div className="empty-box">
          <strong>هیچ سندی برای این درس ثبت نشده است</strong>
          با دکمه «سند جدید» اولین محتوای آموزشی را بسازید.
        </div>
      ) : (
        <div className="grid-cards">
          {docs.items.map((d) => (
            <button
              key={d.id}
              type="button"
              className="course-card"
              style={{ textAlign: 'start', cursor: 'pointer', fontFamily: 'inherit' }}
              onClick={() => setOpenDocId(d.id)}
            >
              <h3>{d.title}</h3>
              <div className="course-meta">
                <span>هدف: {kindLabel(d.goal)}</span>
                <span>سبک: {kindLabel(d.style)}</span>
              </div>
              {d.current_version_id ? (
                <span className="badge badge-info">نسخه فعال موجود</span>
              ) : (
                <span className="badge badge-warn">بدون نسخه — نیازمند تولید</span>
              )}
            </button>
          ))}
        </div>
      )}
    </>
  )
}
