import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { JDate } from '../components/JDate'

// ---------- انواع سرویس‌های هوشمند ----------

type TabKey =
  | 'overview' | 'weak' | 'resources' | 'remedial' | 'analysis'
  | 'style' | 'forget' | 'load' | 'micro' | 'gen'

interface Mastery {
  known: number; partial: number; weak: number; unknown: number; total: number
}
interface WeakItem {
  concept_id: string; concept_name: string; estimated_mastery: number
  severity: number; impact_downstream: number; evidence_count: number
  confidence: number | null
}
interface RootCause {
  concept_id: string; concept_name: string; root_concept_id: string | null
  root_concept_name: string | null; depth: number
  chains: { path: string[]; ids: string[] }[]; interpretation: string
}
interface ResourceRec {
  kind: string; title: string; ref_id: string; url: string | null
  matched_concepts: string[] | string; reason: string
}
interface RemedialConcept {
  concept_id: string; concept_name: string; severity: number
  review_hint: string; misconception: string | null
  questions: { question_version_id: string; type: string; difficulty: string; body: string; options: { key: string; text: string }[] }[]
}
interface AnswerAnalysis {
  status: string; total?: number; accuracy?: number; avg_time_ms?: number | null
  by_difficulty?: Record<string, { total: number; correct: number; accuracy: number }>
  patterns?: Record<string, number>
  per_concept?: { concept_id: string; concept_name: string | null; total: number; accuracy: number }[]
  insights?: string[]; note?: string
}
interface LearningStyle {
  status: string; event_count?: number; distribution?: Record<string, number>
  dominant_style?: string; label?: string; recommendation?: string; note?: string
}
interface ForgetItem {
  concept_id: string; concept_name: string; mastery_status: string
  retention_now: number | null; retention_target: number
  predicted_review_at: string; overdue_for_review: boolean
}
interface Forgetting { concepts: ForgetItem[]; urgent_count: number; summary: string }
interface CognitiveLoad {
  status: string; sample?: number; load_index?: number; band?: string
  components?: Record<string, number>; recommendation?: string
  suggested_difficulty?: string; note?: string
}
interface MicroLesson {
  document_id: string; version_id: string; title: string; section: string
  estimated_minutes: number; word_count: number; step_count: number
  steps: string[]; self_check: string
}
interface Overview {
  mastery: Mastery
  top_weaknesses: WeakItem[]
  cognitive_load: CognitiveLoad
  learning_style: LearningStyle
  forgetting: { urgent_count: number; concepts: ForgetItem[] }
  due_reviews: { concept_name: string; due_at: string; overdue: boolean }[]
  next_actions: { type: string; label: string; ref: string | null }[]
}
interface ValidationItem {
  question_id: string; question_version_id: string; status: string; type: string
  source: string | null; difficulty_estimated: string; cognitive_level: string
  similarity_score: number | null; warnings: string | null; body: string
  concepts: string[]
}
interface QuizStart {
  assessment_id: string; attempt_id: string; mode: string
  url: string; note: string
}

// ---------- متادیتای ۱۶ سرویس (نقشه کامل دسته) ----------

const SERVICE_MAP: { title: string; hint: string; tag: string; link?: { to: string; label: string } }[] = [
  { title: 'تحلیل فهم مفاهیم', hint: 'گراف مفاهیم + تسلط', tag: 'Knowledge Graph', link: { to: 'mastery', label: 'صفحه تسلط' } },
  { title: 'شناسایی نقاط ضعف مفهومی', hint: 'شدت‌دار با شواهد', tag: 'Learning Analytics' },
  { title: 'تشخیص ریشه مشکلات یادگیری', hint: 'زنجیره پیش‌نیازها', tag: 'AI Diagnosis' },
  { title: 'طراحی برنامه مطالعه', hint: 'شخصی‌سازی هدفمند', tag: 'Personalization', link: { to: 'plan', label: 'برنامه مطالعه' } },
  { title: 'پیشنهاد منابع آموزشی', hint: 'محتوا + کتاب/ویدیو', tag: 'Recommender' },
  { title: 'کوییز هوشمند', hint: 'سوال هدفمند از ضعف', tag: 'AI Question Gen' },
  { title: 'آزمون تطبیقی', hint: 'انتخاب سوال بعدی هوشمند', tag: 'Adaptive Testing', link: { to: 'quizzes', label: 'آزمون‌ها' } },
  { title: 'تحلیل پاسخ دانشجو', hint: 'الگوهای خطا و زمان', tag: 'NLP + ML' },
  { title: 'بسته تمرین جبرانی', hint: 'تمرین رفع ضعف', tag: 'Personalization' },
  { title: 'تحلیل سبک یادگیری', hint: 'دیداری/تمرینی/گفتگومحور', tag: 'Behavioral Analytics' },
  { title: 'پیش‌بینی فراموشی مطالب', hint: 'منحنی فراموشی + مرور', tag: 'Spaced Repetition AI' },
  { title: 'فشار شناختی یادگیرنده', hint: 'تنظیم دشواری محتوا', tag: 'Cognitive Modeling' },
  { title: 'آموزش‌های کوتاه و مرحله‌ای', hint: 'قطعه‌بندی هوشمند', tag: 'Content Chunking AI' },
  { title: 'استاد هوشمند گفتگومحور', hint: 'دستیار تعاملی', tag: 'Conversational AI', link: { to: 'tutor', label: 'گفتگو' } },
  { title: 'طراحی هوشمند سوال و ارزیابی', hint: 'شبیه‌سازی امتحان + تایید انسانی', tag: 'Generative Assessment' },
  { title: 'یادگیری مشارکتی و خلاقیت', hint: 'دانشجو تولیدکننده + منتور AI', tag: 'Student-as-Creator' },
]

const TABS: { key: TabKey; label: string; staffOnly?: boolean }[] = [
  { key: 'overview', label: 'داشبورد' },
  { key: 'weak', label: 'ضعف و ریشه' },
  { key: 'resources', label: 'منابع پیشنهادی' },
  { key: 'remedial', label: 'تمرین جبرانی' },
  { key: 'analysis', label: 'تحلیل پاسخ' },
  { key: 'style', label: 'سبک یادگیری' },
  { key: 'forget', label: 'منحنی فراموشی' },
  { key: 'load', label: 'فشار شناختی' },
  { key: 'micro', label: 'آموزش کوتاه' },
  { key: 'gen', label: 'سوال‌ساز و اعتبارسنجی', staffOnly: true },
]

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${Math.round(v * 100)}٪`
}

export default function SmartHub({ courseId }: { courseId: string }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const isStaff = !!user && user.role !== 'STUDENT'
  const tabs = TABS.filter((t) => !t.staffOnly || isStaff)
  const [tab, setTab] = useState<TabKey>('overview')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [overview, setOverview] = useState<Overview | null>(null)
  const [weak, setWeak] = useState<{ weak_count: number; unknown_count: number; weaknesses: WeakItem[]; summary: string } | null>(null)
  const [roots, setRoots] = useState<RootCause[] | null>(null)
  const [resources, setResources] = useState<ResourceRec[] | null>(null)
  const [remedial, setRemedial] = useState<{ status: string; concepts?: RemedialConcept[]; estimated_minutes?: number; note?: string } | null>(null)
  const [analysis, setAnalysis] = useState<AnswerAnalysis | null>(null)
  const [style, setStyle] = useState<LearningStyle | null>(null)
  const [forget, setForget] = useState<Forgetting | null>(null)
  const [load, setLoad] = useState<CognitiveLoad | null>(null)
  const [micro, setMicro] = useState<MicroLesson[] | null>(null)
  const [vq, setVq] = useState<{ items: ValidationItem[]; pending_count: number; duplicate_risk_count: number; note: string } | null>(null)
  const [simResult, setSimResult] = useState<{ assessment: { id: string; title: string }; sections: number; total_questions: number } | null>(null)

  const startSmartQuiz = useCallback(async () => {
    setBusy(true); setErr(null)
    try {
      const data = await api.post<QuizStart>(`/me/courses/${courseId}/smart/quiz`)
      navigate(`/quiz/${data.assessment_id}`)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'خطا در ساخت کوییز هوشمند')
    } finally { setBusy(false) }
  }, [courseId, navigate])

  const runSimulation = useCallback(async () => {
    setBusy(true); setErr(null)
    try {
      const data = await api.post<{ assessment: { id: string; title: string }; sections: number; total_questions: number }>(
        `/courses/${courseId}/smart/exam-simulation`)
      setSimResult(data)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'خطا در شبیه‌سازی امتحان')
    } finally { setBusy(false) }
  }, [courseId])

  // بارگذاری داده هر تب
  useEffect(() => {
    let alive = true
    setErr(null)
    const base = `/me/courses/${courseId}/smart`
    const jobs: Promise<void>[] = []
    if (tab === 'overview' && !overview) {
      jobs.push(api.get<Overview>(`${base}/overview`).then((d) => { if (alive) setOverview(d) }))
    } else if (tab === 'weak') {
      if (!weak) jobs.push(api.get<{ weak_count: number; unknown_count: number; weaknesses: WeakItem[]; summary: string }>(`${base}/weaknesses`).then((d) => { if (alive) setWeak(d) }))
      if (!roots) jobs.push(api.get<RootCause[]>(`${base}/root-causes`).then((d) => { if (alive) setRoots(d) }))
    } else if (tab === 'resources' && !resources) {
      jobs.push(api.get<{ recommendations: ResourceRec[] }>(`${base}/resources`).then((d) => { if (alive) setResources(d.recommendations) }))
    } else if (tab === 'remedial' && !remedial) {
      jobs.push(api.get<{ status: string; concepts?: RemedialConcept[]; estimated_minutes?: number; note?: string }>(`${base}/remedial-pack`).then((d) => { if (alive) setRemedial(d) }))
    } else if (tab === 'analysis' && !analysis) {
      jobs.push(api.get<AnswerAnalysis>(`${base}/answer-analysis`).then((d) => { if (alive) setAnalysis(d) }))
    } else if (tab === 'style' && !style) {
      jobs.push(api.get<LearningStyle>(`${base}/learning-style`).then((d) => { if (alive) setStyle(d) }))
    } else if (tab === 'forget' && !forget) {
      jobs.push(api.get<Forgetting>(`${base}/forgetting-curve`).then((d) => { if (alive) setForget(d) }))
    } else if (tab === 'load' && !load) {
      jobs.push(api.get<CognitiveLoad>(`${base}/cognitive-load`).then((d) => { if (alive) setLoad(d) }))
    } else if (tab === 'micro' && !micro) {
      jobs.push(api.get<{ lessons: MicroLesson[] }>(`${base}/micro-lessons`).then((d) => { if (alive) setMicro(d.lessons) }))
    } else if (tab === 'gen' && isStaff && !vq) {
      jobs.push(api.get<{ items: ValidationItem[]; pending_count: number; duplicate_risk_count: number; note: string }>(`/courses/${courseId}/smart/validation-queue`).then((d) => { if (alive) setVq(d) }))
    }
    Promise.all(jobs).catch((e: unknown) => {
      if (alive) setErr(e instanceof Error ? e.message : 'خطا در دریافت داده سرویس‌های هوشمند')
    })
    return () => { alive = false }
  }, [tab, courseId, overview, weak, roots, resources, remedial, analysis, style, forget, load, micro, vq, isStaff])

  const loading = err === null && (() => {
    switch (tab) {
      case 'overview': return !overview
      case 'weak': return !weak || !roots
      case 'resources': return !resources
      case 'remedial': return !remedial
      case 'analysis': return !analysis
      case 'style': return !style
      case 'forget': return !forget
      case 'load': return !load
      case 'micro': return !micro
      case 'gen': return isStaff && !vq
    }
  })()

  return (
    <div className="page page-wide">
      <div className="page-header">
        <div>
          <h1>✨ سرویس‌های یادگیری هوشمند</h1>
          <p className="muted">تحلیل یادگیری مفهومی، شخصی‌سازی مسیر و پشتیبانی هوشمند مستمر — دسته کامل ۱۶ سرویس</p>
        </div>
        <button className="btn btn-primary" disabled={busy} onClick={startSmartQuiz}>
          {busy ? '…' : '🚀 کوییز هوشمند الآن'}
        </button>
      </div>

      <div className="card">
        <div className="card-title"><h2>نقشه دسته سرویس‌ها</h2></div>
        <div className="smart-map">
          {SERVICE_MAP.map((s) => (
            <div key={s.title} className="smart-map-item">
              <strong>{s.title}</strong>
              <span className="muted">{s.hint}</span>
              <span className="chip">{s.tag}</span>
              {s.link && (
                <Link className="link-btn" to={`/course/${courseId}/${s.link.to}`}>
                  {s.link.label} →
                </Link>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="smart-tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`smart-tab${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {err && <div className="error-box">{err}</div>}
      {loading && (
        <div className="center-note"><div className="spinner" /> در حال تحلیل…</div>
      )}

      {!loading && tab === 'overview' && overview && (
        <>
          <div className="grid-cards">
            <div className="card">
              <div className="card-title"><h2>تسلط مفهومی</h2></div>
              {[['مسلط', overview.mastery.known, 'success'], ['جزئی', overview.mastery.partial, 'warn'],
                ['ضعیف', overview.mastery.weak, 'danger'], ['نامشخص', overview.mastery.unknown, '']].map(([label, n, cls]) => (
                <div className="progress-row" key={String(label)}>
                  <span className="progress-label">{String(label)}</span>
                  <div className="progress"><div className={`progress-fill ${cls}`} style={{ width: `${(Number(n) / Math.max(1, overview.mastery.total)) * 100}%` }} /></div>
                  <span className="progress-value">{Number(n)}</span>
                </div>
              ))}
            </div>
            <div className="card">
              <div className="card-title"><h2>فشار شناختی</h2></div>
              {overview.cognitive_load.status === 'OK' ? (
                <>
                  <div className="kv"><span>شاخص</span><b>{overview.cognitive_load.load_index}/100 ({overview.cognitive_load.band === 'LOW' ? 'کم' : overview.cognitive_load.band === 'MEDIUM' ? 'بهینه' : 'بالا'})</b></div>
                  <p className="muted">{overview.cognitive_load.recommendation}</p>
                </>
              ) : <p className="muted">{overview.cognitive_load.note}</p>}
            </div>
            <div className="card">
              <div className="card-title"><h2>سبک یادگیری</h2></div>
              {overview.learning_style.status === 'OK' ? (
                <>
                  <p><b>{overview.learning_style.label}</b></p>
                  <p className="muted">{overview.learning_style.recommendation}</p>
                </>
              ) : <p className="muted">{overview.learning_style.note}</p>}
            </div>
          </div>
          <div className="card">
            <div className="card-title"><h2>اقدامات پیشنهادی الآن</h2></div>
            {overview.next_actions.map((a, i) => (
              <div className="activity-row" key={i}>
                <span>{a.label}</span>
                <span className="btn-row">
                  {a.type === 'REMEDIAL' && <button className="btn btn-sm" onClick={() => setTab('remedial')}>تمرین جبرانی</button>}
                  {(a.type === 'REVIEW' && a.ref === 'forget') && <button className="btn btn-sm" onClick={() => setTab('forget')}>منحنی فراموشی</button>}
                  {(a.type === 'REVIEW' && a.ref === 'plan') && <Link className="btn btn-sm" to={`/course/${courseId}/plan`}>برنامه مطالعه</Link>}
                  {a.type === 'DIAGNOSTIC' && <button className="btn btn-sm btn-primary" disabled={busy} onClick={startSmartQuiz}>کوییز تشخیصی</button>}
                  {(a.type === 'MICRO') && <button className="btn btn-sm" onClick={() => setTab('micro')}>قطعه‌های کوتاه</button>}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && tab === 'weak' && weak && roots && (
        <>
          <div className="card">
            <div className="card-title"><h2>نقاط ضعف مفهومی</h2></div>
            <div className="inline-alert">{weak.summary}</div>
            {weak.weaknesses.length === 0 ? (
              <div className="empty-box"><strong>مفهوم ضعیفی ثبت نشده</strong>وضعیت همه مفاهیم مسلط/جزئی یا نامشخص است.</div>
            ) : weak.weaknesses.map((w) => (
              <div className="mastery-row" key={w.concept_id}>
                <span className="mastery-name">{w.concept_name}</span>
                <div className="progress" style={{ maxWidth: 200 }}>
                  <div className="progress-fill danger" style={{ width: `${w.estimated_mastery * 100}%` }} />
                </div>
                <span className="badge badge-danger">شدت {pct(w.severity)}</span>
                {w.impact_downstream > 0 && <span className="chip">{w.impact_downstream} مفهوم وابسته</span>}
              </div>
            ))}
          </div>
          <div className="card">
            <div className="card-title"><h2>ریشه‌یابی مشکلات یادگیری</h2></div>
            {roots.length === 0 ? (
              <div className="empty-box"><strong>فرضیه ریشه‌ای نیست</strong>ضعف فعال فعلاً شناسایی نشده است.</div>
            ) : roots.map((r) => (
              <div className="diag-card" key={r.concept_id}>
                <div className="kv"><span>مفهوم ضعیف</span><b>{r.concept_name}</b></div>
                {r.chains.map((c, i) => (
                  <div className="step-arrow" key={i}>{c.path.join(' ← ')}</div>
                ))}
                <p className="muted">{r.interpretation}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && tab === 'resources' && resources && (
        <div className="card">
          <div className="card-title"><h2>منابع پیشنهادی برای ضعف‌های شما</h2></div>
          {resources.length === 0 ? (
            <div className="empty-box"><strong>موردی برای پیشنهاد نیست</strong>پس از شناسایی ضعف، منابع مرتبط اینجا ظاهر می‌شود.</div>
          ) : resources.map((r, i) => (
            <div className="export-row" key={i}>
              <span className="badge badge-info">{r.kind}</span>
              <span><b>{r.title}</b> <span className="muted">— {r.reason}</span></span>
              {r.url && <Link className="link-btn" to={r.url.startsWith('/course/') ? r.url : r.url}>مشاهده →</Link>}
            </div>
          ))}
        </div>
      )}

      {!loading && tab === 'remedial' && remedial && (
        <div className="card">
          <div className="card-title"><h2>بسته تمرین جبرانی</h2></div>
          {remedial.status !== 'OK' ? (
            <div className="empty-box"><strong>تمرین جبرانی لازم نیست</strong>{remedial.note}</div>
          ) : (
            <>
              <div className="inline-alert">{remedial.note} (تخمین: {remedial.estimated_minutes} دقیقه)</div>
              {remedial.concepts?.map((c) => (
                <div className="diag-card" key={c.concept_id}>
                  <div className="kv"><span>{c.concept_name}</span><span className="badge badge-danger">شدت {pct(c.severity)}</span></div>
                  <div className="hint">{c.review_hint}</div>
                  {c.questions.length === 0 ? (
                    <p className="muted">برای این مفهوم سؤال تمرینی مصوب موجود نیست — از استاد درخواست کنید.</p>
                  ) : c.questions.map((q) => (
                    <div className="review-row" key={q.question_version_id}>
                      <span className="badge badge-neutral">{q.type} · {q.difficulty}</span>
                      <span>{q.body}</span>
                    </div>
                  ))}
                  <button className="btn btn-sm btn-primary" disabled={busy} onClick={startSmartQuiz}>تمرین هدایت‌شده با کوییز هوشمند</button>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {!loading && tab === 'analysis' && analysis && (
        <div className="card">
          <div className="card-title"><h2>تحلیل پاسخ‌های من</h2></div>
          {analysis.status !== 'OK' ? (
            <div className="empty-box"><strong>داده کافی نیست</strong>{analysis.note}</div>
          ) : (
            <>
              <div className="kv-grid">
                <div className="kv"><span>پاسخ نمره‌دار</span><b>{analysis.total}</b></div>
                <div className="kv"><span>دقت کل</span><b>{pct(analysis.accuracy)}</b></div>
                <div className="kv"><span>میانگین زمان</span><b>{analysis.avg_time_ms ? `${Math.round(analysis.avg_time_ms / 1000)} ثانیه` : '—'}</b></div>
              </div>
              {analysis.by_difficulty && Object.entries(analysis.by_difficulty).map(([k, v]) => (
                <div className="progress-row" key={k}>
                  <span className="progress-label">{k}</span>
                  <div className="progress"><div className="progress-fill" style={{ width: `${v.accuracy * 100}%` }} /></div>
                  <span className="progress-value">{pct(v.accuracy)} ({v.total})</span>
                </div>
              ))}
              <div className="chip-list">
                {Object.entries(analysis.patterns || {}).map(([k, v]) => (
                  v > 0 ? <span key={k} className="chip">{PATTERN_FA[k] || k}: {v}</span> : null
                ))}
              </div>
              {analysis.per_concept?.map((c) => (
                <div className="per-concept-row" key={c.concept_id}>
                  <span>{c.concept_name || 'مفهوم'}</span>
                  <div className="progress" style={{ maxWidth: 200 }}>
                    <div className={`progress-fill ${c.accuracy >= 0.75 ? 'success' : c.accuracy >= 0.4 ? 'warn' : 'danger'}`} style={{ width: `${c.accuracy * 100}%` }} />
                  </div>
                  <span className="progress-value">{pct(c.accuracy)}</span>
                </div>
              ))}
              <div className="details-box">
                {analysis.insights?.map((s, i) => <div key={i}>• {s}</div>)}
              </div>
            </>
          )}
        </div>
      )}

      {!loading && tab === 'style' && style && (
        <div className="card">
          <div className="card-title"><h2>سبک یادگیری من</h2></div>
          {style.status !== 'OK' ? (
            <div className="empty-box"><strong>شواهد تعامل ناکافی</strong>{style.note}</div>
          ) : (
            <>
              <p><b>{style.label}</b></p>
              {Object.entries(style.distribution || {}).map(([k, v]) => (
                <div className="progress-row" key={k}>
                  <span className="progress-label">{STYLE_FA[k] || k}</span>
                  <div className="progress"><div className="progress-fill info" style={{ width: `${v * 100}%` }} /></div>
                  <span className="progress-value">{pct(v)}</span>
                </div>
              ))}
              <div className="inline-alert">{style.recommendation}</div>
              <p className="muted">{style.note}</p>
            </>
          )}
        </div>
      )}

      {!loading && tab === 'forget' && forget && (
        <div className="card">
          <div className="card-title"><h2>منحنی فراموشی و زمان مرور بهینه</h2></div>
          <div className="inline-alert">{forget.summary} (آستانه مرور: {pct(forget.concepts[0]?.retention_target ?? 0.7)})</div>
          {forget.concepts.map((c) => (
            <div className="mastery-row" key={c.concept_id}>
              <span className="mastery-name">{c.concept_name}</span>
              <div className="progress" style={{ maxWidth: 200 }}>
                <div
                  className={`progress-fill ${c.retention_now === null ? '' : c.retention_now >= 0.7 ? 'success' : c.retention_now >= 0.5 ? 'warn' : 'danger'}`}
                  style={{ width: `${(c.retention_now ?? 0) * 100}%` }}
                />
              </div>
              <span className="progress-value">ماندگاری {pct(c.retention_now)}</span>
              {c.overdue_for_review && <span className="badge badge-danger">مرور فوری</span>}
              <span className="muted">مرور پیشنهادی:</span> <JDate iso={c.predicted_review_at} withTime variant="text" />
            </div>
          ))}
        </div>
      )}

      {!loading && tab === 'load' && load && (
        <div className="card">
          <div className="card-title"><h2>تحلیل فشار شناختی</h2></div>
          {load.status !== 'OK' ? (
            <div className="empty-box"><strong>داده کافی نیست</strong>{load.note}</div>
          ) : (
            <>
              <div className="kv-grid">
                <div className="kv"><span>شاخص فشار</span><b>{load.load_index}/100</b></div>
                <div className="kv"><span>سطح</span><b>{load.band === 'LOW' ? 'کم' : load.band === 'MEDIUM' ? 'بهینه' : 'بالا'}</b></div>
                <div className="kv"><span>دشواری پیشنهادی</span><b>{load.suggested_difficulty}</b></div>
              </div>
              {Object.entries(load.components || {}).map(([k, v]) => (
                <div className="progress-row" key={k}>
                  <span className="progress-label">{LOAD_FA[k] || k}</span>
                  <div className="progress"><div className="progress-fill warn" style={{ width: `${v * 100}%` }} /></div>
                  <span className="progress-value">{pct(v)}</span>
                </div>
              ))}
              <div className="inline-alert">{load.recommendation}</div>
              <p className="muted">{load.note}</p>
            </>
          )}
        </div>
      )}

      {!loading && tab === 'micro' && micro && (
        <div className="card">
          <div className="card-title"><h2>آموزش‌های کوتاه و مرحله‌ای</h2></div>
          {micro.length === 0 ? (
            <div className="empty-box"><strong>محتوای منتشرشده‌ای برای قطعه‌بندی نیست</strong>پس از انتشار محتوا در استودیو، قطعه‌های کوتاه اینجا ساخته می‌شود.</div>
          ) : micro.map((l, i) => (
            <div className="diag-card" key={i}>
              <div className="kv">
                <span><b>{l.title}</b> <span className="muted">({l.section})</span></span>
                <span className="badge badge-info">{l.estimated_minutes} دقیقه · {l.step_count} گام</span>
              </div>
              <ol className="micro-steps">
                {l.steps.map((s, j) => <li key={j}>{s}</li>)}
              </ol>
              <div className="block-self">{l.self_check}</div>
              <Link className="link-btn" to={`/course/${courseId}/content/${l.version_id}`}>مطالعه کامل →</Link>
            </div>
          ))}
        </div>
      )}

      {!loading && tab === 'gen' && isStaff && vq && (
        <>
          <div className="card">
            <div className="card-title"><h2>شبیه‌سازی امتحان (Generative Assessment)</h2></div>
            <p className="muted">
              Blueprint خودکار از گراف مفاهیم مصوب + نقشه ضعف کلاس؛ دشواری هر بخش بر اساس وضعیت دانشجویان
              تنظیم می‌شود. سؤال‌ها فقط از بانک مصوب انتخاب می‌شوند (دروازه انسانی حفظ است).
            </p>
            <button className="btn btn-primary" disabled={busy} onClick={runSimulation}>ساخت شبیه‌سازی امتحان</button>
            {simResult && (
              <div className="result-banner">
                «{simResult.assessment.title}» با {simResult.sections} بخش و {simResult.total_questions} سؤال ساخته شد —{' '}
                <Link to={`/course/${courseId}/quizzes`}>مدیریت آزمون‌ها →</Link>
              </div>
            )}
          </div>
          <div className="card">
            <div className="card-title">
              <h2>صف اعتبارسنجی سؤال‌های تولیدی (Human-in-the-loop)</h2>
              <span className="badge badge-warn">{vq.pending_count} در انتظار · {vq.duplicate_risk_count} مشابهت بالا</span>
            </div>
            <div className="inline-alert">{vq.note}</div>
            {vq.items.length === 0 ? (
              <div className="empty-box"><strong>صف خالی است</strong>سؤال تولیدی جدید اینجا برای تأیید شما ظاهر می‌شود.</div>
            ) : vq.items.map((it) => (
              <div className="diag-card" key={it.question_version_id}>
                <div className="kv">
                  <span className="badge-row">
                    <span className="badge badge-neutral">{it.type}</span>
                    <span className="badge badge-info">{it.cognitive_level}</span>
                    <span className={`badge ${(it.similarity_score ?? 0) >= 0.8 ? 'badge-danger' : 'badge-success'}`}>
                      مشابهت {pct(it.similarity_score)}
                    </span>
                    {it.warnings && <span className="badge badge-warn">⚠ {it.warnings}</span>}
                  </span>
                  <span className="badge badge-warn">{it.status === 'AI_GENERATED' ? 'تولید AI — نیازمند بررسی' : 'در انتظار تأیید'}</span>
                </div>
                <p>{it.body}</p>
                {it.concepts.length > 0 && <div className="chip-list">{it.concepts.map((c) => <span key={c} className="chip">{c}</span>)}</div>}
                <Link className="link-btn" to={`/course/${courseId}/quizzes`}>تأیید/رد در مدیریت سؤال →</Link>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const PATTERN_FA: Record<string, string> = {
  fast_wrong: 'سریع‌ونادرست', slow_correct: 'صحیحِ‌کند',
  slow_wrong: 'کند‌ونادرست', hint_used: 'با راهنما', near_miss: 'نزدیک‌به‌صحیح',
}
const STYLE_FA: Record<string, string> = {
  VISUAL: 'دیداری/خوانشی', PRACTICAL: 'تمرینی', CONVERSATIONAL: 'گفتگومحور',
}
const LOAD_FA: Record<string, string> = {
  time_pressure: 'فشار زمان', error_rate: 'نرخ خطا', hint_rate: 'نرخ راهنما',
}
