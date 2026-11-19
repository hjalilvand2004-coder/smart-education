import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api'

/** صفحه یکپارچه‌سازی با سامانه «برنامه‌یار۳۶۰»: واکشی درس‌های یکتا → فرم اطلاعات درس
 *  → ثبت سرفصل‌ها → ورود به دانشجو۳۶۰ و تولید محتوا برای هر سرفصل. */

interface PyStatus {
  base_url: string
  reachable: boolean
  auth_required: boolean
  credentials_configured: boolean
  message: string
}

interface PyCourse {
  code: string
  title: string
  units?: number | null
  department?: string | null
  term?: string | null
  field_of_study?: string | null
  degree_level?: string | null
  description?: string | null
  already_imported?: boolean
}

interface PyFetchResult {
  items: PyCourse[]
  total: number
  auth_used: boolean
  reachable: boolean
  message: string
}

interface PyImportResult {
  course_id: string
  syllabus_version_id: string
  topics_count: number
  message: string
}

interface TopicRow {
  title: string
  description: string
  suggested_hours: string
}

const STEP_LABELS = ['۱. واکشی درس‌ها', '۲. فرم اطلاعات درس', '۳. ثبت سرفصل‌ها']

const emptyTopic: TopicRow = { title: '', description: '', suggested_hours: '' }

export default function Programyar() {
  const navigate = useNavigate()

  // اتصال
  const [baseUrl, setBaseUrl] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<PyStatus | null>(null)

  // واکشی
  const [courses, setCourses] = useState<PyCourse[] | null>(null)
  const [fetchMsg, setFetchMsg] = useState('')
  const [busy, setBusy] = useState<'status' | 'fetch' | 'import' | null>(null)
  const [error, setError] = useState('')

  // فرم درس
  const [selected, setSelected] = useState<PyCourse | null>(null)
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [department, setDepartment] = useState('')
  const [degreeLevel, setDegreeLevel] = useState('')
  const [field, setField] = useState('')
  const [credits, setCredits] = useState('')
  const [term, setTerm] = useState('')
  const [description, setDescription] = useState('')
  const [prereq, setPrereq] = useState('')
  const [topics, setTopics] = useState<TopicRow[]>([{ ...emptyTopic }])

  // ثبت
  const [result, setResult] = useState<PyImportResult | null>(null)

  const step = result ? 4 : selected ? 3 : courses ? 2 : 1

  const errText = (e: unknown) =>
    e instanceof ApiError ? e.message : 'خطای ارتباط با سرور'

  const checkStatus = async () => {
    setBusy('status'); setError(''); setStatus(null)
    try {
      setStatus(await api.get<PyStatus>('/integration/programyar/status'))
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(null)
    }
  }

  const fetchCourses = async () => {
    setBusy('fetch'); setError(''); setFetchMsg(''); setCourses(null); setSelected(null); setResult(null)
    try {
      const r = await api.post<PyFetchResult>('/integration/programyar/courses', {
        username: username || undefined,
        password: password || undefined,
        base_url: baseUrl || undefined,
      })
      setCourses(r.items)
      setFetchMsg(r.message)
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(null)
    }
  }

  const pickCourse = (c: PyCourse) => {
    setSelected(c)
    setCode(c.code || '')
    setTitle(c.title || '')
    setDepartment(c.department || '')
    setDegreeLevel(c.degree_level || '')
    setField(c.field_of_study || '')
    setCredits(c.units != null ? String(c.units) : '')
    setTerm(c.term || '')
    setDescription(c.description || '')
    setPrereq('')
    setTopics([{ ...emptyTopic }])
    setResult(null)
    window.scrollTo({ top: 0 })
  }

  const updateTopic = (idx: number, patch: Partial<TopicRow>) => {
    setTopics((rows) => rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)))
  }

  const importCourse = async () => {
    setBusy('import'); setError('')
    try {
      const r = await api.post<PyImportResult>('/integration/programyar/import', {
        code: code.trim(), title: title.trim(),
        department: department || undefined, degree_level: degreeLevel || undefined,
        field_of_study: field || undefined,
        credits: credits ? Number(credits) : undefined,
        term: term || undefined, description: description || undefined,
        prerequisites_note: prereq || undefined,
        source_ref: selected?.code || undefined,
        topics: topics
          .filter((t) => t.title.trim())
          .map((t) => ({
            title: t.title.trim(), description: t.description || undefined,
            suggested_hours: t.suggested_hours ? Number(t.suggested_hours) : undefined,
          })),
      })
      setResult(r)
      window.scrollTo({ top: 0 })
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(null)
    }
  }

  const resetAll = () => {
    setSelected(null); setResult(null); setCourses(null); setFetchMsg('')
  }

  return (
    <>
      <div className="hero">
        <div className="hero-icon">۳۶۰</div>
        <div>
          <h2>یکپارچه‌سازی با برنامه‌یار۳۶۰</h2>
          <p>
            واکشی «درس‌های یکتا» از سامانه برنامه‌ریزی درسی، تکمیل فرم اطلاعات درس، ثبت سرفصل‌ها و
            سپس تولید محتوای آموزشی متناسب با هر سرفصل در استودیو.
          </p>
        </div>
      </div>

      <div className="card">
        <div className="step-flow">
          {STEP_LABELS.map((label, i) => (
            <span key={label} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <span className={`step-pill${step === i + 1 ? ' current' : step > i + 1 ? ' done' : ''}`}>{label}</span>
              {i < STEP_LABELS.length - 1 && <span className="step-arrow">←</span>}
            </span>
          ))}
        </div>

        {/* مرحله ۱: اتصال و واکشی */}
        <h3>اتصال به برنامه‌یار۳۶۰</h3>
        <div className="form-grid">
          <div className="form-item">
            <label className="label">آدرس سامانه (اختیاری)</label>
            <input className="input" dir="ltr" placeholder="پیش‌فرض سامانه استفاده می‌شود"
                   value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </div>
          <div className="form-item">
            <label className="label">نام کاربری برنامه‌یار (اختیاری)</label>
            <input className="input" dir="ltr" autoComplete="off"
                   value={username} onChange={(e) => setUsername(e.target.value)} />
            <div className="hint">اگر برنامه‌یار۳۶۰ احراز هویت بخواهد، این فیلد لازم است.</div>
          </div>
          <div className="form-item">
            <label className="label">رمز عبور برنامه‌یار (اختیاری)</label>
            <input className="input" type="password" dir="ltr" autoComplete="new-password"
                   value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        </div>
        <div className="btn-row section-gap">
          <button type="button" className="btn" disabled={busy !== null} onClick={checkStatus}>
            {busy === 'status' ? 'در حال بررسی…' : 'تست اتصال'}
          </button>
          <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={fetchCourses}>
            {busy === 'fetch' ? 'در حال واکشی…' : 'واکشی درس‌های یکتا'}
          </button>
          {courses && (
            <button type="button" className="btn btn-sm" onClick={resetAll}>پاک‌سازی نتایج</button>
          )}
        </div>

        {status && (
          <div className={status.reachable ? 'success-box' : 'inline-alert'}>
            {status.reachable ? '✓ ' : '✕ '}
            {status.message}
            {status.auth_required && ' — احراز هویت لازم است؛ نام کاربری و رمز را وارد کنید.'}
          </div>
        )}
        {fetchMsg && <div className="inline-alert">{fetchMsg}</div>}
        {error && <div className="error-box"><span>{error}</span></div>}
      </div>

      {/* مرحله ۲: لیست درس‌های یکتا */}
      {courses && !selected && (
        <div className="card">
          <div className="card-title">
            <h3>درس‌های یکتای برنامه‌یار۳۶۰ ({courses.length})</h3>
            <span className="muted">برای هر درس، «افزودن به دانشجو۳۶۰» را بزنید</span>
          </div>
          {courses.length === 0 ? (
            <div className="empty-box">
              <strong>درسی واکشی نشد</strong>
              اگر برنامه‌یار نیاز به ورود دارد، نام کاربری و رمز را وارد کنید؛ در غیر این صورت
              درس‌ها را می‌توانید در همین فرم به‌صورت دستی ثبت کنید.
            </div>
          ) : (
            courses.map((c) => (
              <div key={c.code || c.title} className={`pyc-row${c.already_imported ? ' imported' : ''}`}>
                <div>
                  <strong>{c.title || 'بدون عنوان'}</strong>{' '}
                  {c.code && <span className="pyc-code">{c.code}</span>}
                  <div className="muted">
                    {c.department && <>گروه: {c.department} · </>}
                    {c.units != null && <>{c.units} واحد · </>}
                    {c.term && <>{c.term}</>}
                  </div>
                </div>
                {c.already_imported ? (
                  <span className="badge badge-success">ثبت‌شده در دانشجو۳۶۰</span>
                ) : (
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => pickCourse(c)}>
                    افزودن به دانشجو۳۶۰
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* مرحله ۳: فرم اطلاعات درس + سرفصل‌ها */}
      {selected && !result && (
        <div className="card">
          <div className="card-title">
            <h3>فرم اطلاعات درس</h3>
            <span className="muted">پیش‌پرشده از داده واکشی‌شده — قابل ویرایش</span>
          </div>
          <div className="form-grid">
            <div className="form-item">
              <label className="label">کد درس *</label>
              <input className="input" dir="ltr" value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
            <div className="form-item form-item-full">
              <label className="label">عنوان درس *</label>
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="form-item">
              <label className="label">گروه/دانشکده</label>
              <input className="input" value={department} onChange={(e) => setDepartment(e.target.value)} />
            </div>
            <div className="form-item">
              <label className="label">مقطع</label>
              <input className="input" value={degreeLevel} onChange={(e) => setDegreeLevel(e.target.value)} />
            </div>
            <div className="form-item">
              <label className="label">رشته</label>
              <input className="input" value={field} onChange={(e) => setField(e.target.value)} />
            </div>
            <div className="form-item">
              <label className="label">تعداد واحد</label>
              <input className="input" type="number" min="0" max="12" value={credits}
                     onChange={(e) => setCredits(e.target.value)} />
            </div>
            <div className="form-item">
              <label className="label">ترم/نیم‌سال</label>
              <input className="input" value={term} onChange={(e) => setTerm(e.target.value)} />
            </div>
            <div className="form-item form-item-full">
              <label className="label">توضیحات درس</label>
              <textarea className="textarea" value={description}
                        onChange={(e) => setDescription(e.target.value)} />
            </div>
            <div className="form-item form-item-full">
              <label className="label">پیش‌نیازها</label>
              <input className="input" value={prereq} onChange={(e) => setPrereq(e.target.value)} />
            </div>
          </div>

          <hr className="divider" />
          <div className="card-title">
            <h3>سرفصل‌های درس</h3>
            <button type="button" className="btn btn-sm" onClick={() => setTopics((r) => [...r, { ...emptyTopic }])}>
              + افزودن سرفصل
            </button>
          </div>
          <div className="hint" style={{ marginTop: -6, marginBottom: 10 }}>
            برای هر سرفصل، عنوان و (اختیاری) توضیح و ساعت پیشنهادی را وارد کنید؛ در استودیو می‌توانید
            برای هر سرفصل جداگانه محتوا تولید کنید.
          </div>
          {topics.map((t, idx) => (
            <div key={idx} className="topic-editor-row">
              <input className="input" placeholder={`عنوان سرفصل ${idx + 1}`} value={t.title}
                     onChange={(e) => updateTopic(idx, { title: e.target.value })} />
              <input className="input" placeholder="توضیح (اختیاری)" value={t.description}
                     onChange={(e) => updateTopic(idx, { description: e.target.value })} />
              <input className="input" type="number" min="0" step="0.5" placeholder="ساعت"
                     value={t.suggested_hours}
                     onChange={(e) => updateTopic(idx, { suggested_hours: e.target.value })} />
              <button type="button" className="btn btn-sm btn-danger" disabled={topics.length === 1}
                      onClick={() => setTopics((rows) => rows.filter((_, i) => i !== idx))}>
                حذف
              </button>
            </div>
          ))}

          <div className="btn-row section-gap">
            <button type="button" className="btn btn-primary" disabled={busy !== null || !code.trim() || !title.trim()}
                    onClick={importCourse}>
              {busy === 'import' ? 'در حال ثبت…' : 'ثبت درس در دانشجو۳۶۰'}
            </button>
            <button type="button" className="btn" onClick={() => setSelected(null)}>انصراف</button>
          </div>
        </div>
      )}

      {/* مرحله ۴: نتیجه */}
      {result && (
        <div className="card">
          <div className="success-box">✓ {result.message}</div>
          <div className="btn-row">
            <button type="button" className="btn btn-primary" onClick={() => navigate(`/studio/${result.course_id}`)}>
              رفتن به استودیو برای تولید محتوا
            </button>
            <button type="button" className="btn" onClick={() => navigate(`/course/${result.course_id}`)}>
              صفحه درس
            </button>
            <button type="button" className="btn" onClick={resetAll}>ورود درس بعدی</button>
          </div>
        </div>
      )}
    </>
  )
}
