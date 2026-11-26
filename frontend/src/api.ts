/**
 * لایه ارتباط با بک‌اند FastAPI.
 * قرارداد: مسیر پایه /api/v1، خطای استاندارد {"error":{"code","message","details","request_id"}}
 */

// ---------- انواع مشترک ----------

export type Role =
  | 'STUDENT'
  | 'PROFESSOR'
  | 'ASSISTANT'
  | 'GROUP_ADMIN'
  | 'EDUCATION_ADMIN'
  | 'QUALITY_REVIEWER'
  | 'TECH_ADMIN'

export type JobStatus = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'

export type ContentStatus =
  | 'DRAFT'
  | 'GENERATING'
  | 'GENERATED'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'PUBLISHED'
  | 'ARCHIVED'
  | 'FAILED'
  | 'NEEDS_REVISION'
  | 'WITHDRAWN'

export type MasteryStatus = 'KNOWN' | 'PARTIAL' | 'WEAK' | 'UNKNOWN'

export type QuestionType =
  | 'MCQ'
  | 'MULTI_SELECT'
  | 'TRUE_FALSE'
  | 'SHORT_ANSWER'
  | 'ESSAY'
  | 'NUMERIC'
  | 'CASE'
  | 'CODE'
  | 'ORDERING'
  | 'MATCHING'

export interface CourseRoleInfo {
  course_id: string
  course_title: string
  course_code?: string
  role: string
}

export interface User {
  id: string
  username: string
  full_name: string
  role: Role
  course_roles: CourseRoleInfo[]
}

export interface Course {
  id: string
  code: string
  title: string
  department: string
  term?: string
  credits?: number
  my_role: string
  enrolled?: boolean
  syllabus_status?: string | null
}

export interface CourseDetail extends Course {
  degree_level?: string
  field_of_study?: string
  description?: string | null
  professor?: string | null
}

export interface SyllabusTopic {
  id: string
  title: string
  suggested_hours?: number | null
  needs_review?: boolean
  description?: string | null
}

export interface SyllabusChapter {
  id: string
  title: string
  suggested_hours?: number | null
  topics: SyllabusTopic[]
}

export interface LearningObjective {
  id: string
  code: string
  statement: string
  bloom_level?: string | null
  topic_id?: string | null
}

export interface Syllabus {
  id: string
  version_number: number
  title?: string | null
  status: string
  approved_at?: string | null
  chapters: SyllabusChapter[]
  objectives: LearningObjective[]
}

export interface ConceptNode {
  id: string
  key?: string
  name: string
  description?: string | null
  status?: string
  topics?: { id: string; title: string }[]
  mastery?: { status: MasteryStatus; estimated_mastery: number | null }
}

export interface ConceptEdge {
  from: string
  to: string
  type: string
}

export interface ConceptGraph {
  nodes: ConceptNode[]
  edges: ConceptEdge[]
}

// ---------- محتوا ----------

export type BlockType =
  | 'heading'
  | 'text'
  | 'definition'
  | 'note'
  | 'worked_example'
  | 'exercise'
  | 'table'
  | 'formula'
  | 'image'
  | 'code'
  | 'self_check'
  | 'summary'
  | 'reference'

export interface Block {
  id: string
  type: BlockType
  title?: string
  body?: string
  items?: string[]
  steps?: string[]
  columns?: string[]
  rows?: string[][]
  formula?: string
  language?: string
  question?: string
  answer?: string
  explanation?: string
  concept_ids?: string[]
  source_refs?: string[]
}

export interface QCCoverage {
  objective_id: string
  covered: boolean
  evidence_blocks: string[]
}

export interface QCReport {
  coverage: QCCoverage[]
  out_of_scope_concepts: string[]
  missing_sources: string[]
  invalid_refs: string[]
  structure_warnings: string[]
  overall: 'PASS' | 'WARN' | 'FAIL'
}

export interface VersionSummary {
  id: string
  version_number: number
  status: ContentStatus
  revision: number
  qc_overall?: string | null
  published_at?: string | null
}

export interface ContentDocument {
  id: string
  course_id: string
  syllabus_version_id: string
  title: string
  goal: string
  scope: { topic_ids?: string[]; concept_ids?: string[] }
  audience_level?: string | null
  duration_minutes?: number | null
  language: string
  style: string
  components: string[]
  source_resource_ids: string[]
  constraints?: Record<string, unknown> | null
  current_version_id?: string | null
  versions: VersionSummary[]
  plans?: { id: string; status: string; plan: Record<string, unknown> }[]
  created_at?: string
}

export interface HumanChange {
  block_id?: string
  at?: string
  by?: string
  type?: string
}

export interface ContentVersion {
  id: string
  document_id: string
  document_title?: string | null
  version_number: number
  status: ContentStatus
  revision: number
  blocks: Block[]
  qc_report?: QCReport | null
  plan?: Record<string, unknown> | null
  human_changes?: HumanChange[]
  generated_by?: 'AI' | 'HUMAN'
  approved_at?: string | null
  published_at?: string | null
  created_at?: string
}

export interface DocumentSummary {
  id: string
  title: string
  goal: string
  style: string
  current_version_id?: string | null
}

export interface Paged<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ---------- Jobs و خروجی‌ها ----------

export interface JobStep {
  name: string
  status: string
  note?: string | null
}

export interface Job {
  id: string
  kind: string
  status: JobStatus
  progress: number
  steps?: JobStep[]
  error?: string | null
  result?: Record<string, unknown> | null
  created_at?: string
}

export interface JobStart {
  job_id: string
  status: JobStatus
  idempotent_replay?: boolean
  message?: string
  export_job_id?: string
}

export interface ExportArtifact {
  id: string
  file_name: string
  size?: number
  sha256?: string
  mime?: string
  template_version?: string
}

export interface ExportStatus {
  id: string
  format: string
  status: string
  artifacts: ExportArtifact[]
}

export interface PublishedContent {
  document_id: string
  document_title: string
  version_id: string
  version_number: number
  published_at?: string | null
}

// ---------- ارزیابی ----------

export interface Assessment {
  id: string
  course_id: string
  title: string
  kind: 'QUIZ' | 'PRACTICE' | 'EXAM' | string
  mode: 'FIXED' | 'ADAPTIVE_PRACTICE' | string
  blueprint?: Record<string, unknown>
  policy?: { feedback?: string; allow_hint?: boolean; shuffle?: boolean }
  duration_minutes?: number | null
  status?: string
  created_at?: string
}

export interface QuestionOption {
  key: string
  text: string
}

export interface QuestionForStudent {
  question_version_id: string
  number: number
  type: QuestionType
  body: string
  options?: QuestionOption[]
  formula?: string
  policy_help?: string
}

export interface Attempt {
  id: string
  status: string
  assessment?: Assessment
  questions: QuestionForStudent[]
}

export interface ResponseResult {
  response_id: string
  auto_scored: boolean
  grading: string
  correctness?: number | null
  ai_feedback?: string | null
  next_question?: QuestionForStudent
  next_question_id?: string
}

export interface FinishResult {
  score: number
  max_score: number
  per_concept: Record<string, { correct: number; total: number }>
  pending_count?: number
}

// ---------- مدل یادگیری ----------

export interface PrereqInfo {
  concept_id: string
  concept_name?: string
  status: MasteryStatus
}

export interface MasteryEntry {
  concept_id: string
  concept_name: string
  estimated_mastery: number | null
  status: MasteryStatus
  evidence_count: number
  confidence?: number | null
  last_evidence_at?: string | null
  prerequisites: PrereqInfo[]
}

export interface RecommendedAction {
  type: 'REVIEW' | 'PRACTICE' | 'DIAGNOSTIC_QUIZ' | 'ASK_TEACHER' | string
  title: string
  target_id?: string | null
  reason?: string | null
}

export interface Diagnostic {
  id: string
  concept_id: string
  concept_name?: string | null
  hypothesis_type: string
  confidence: number
  rationale: string
  recommended_actions: RecommendedAction[]
}

export interface AggregateMastery {
  concept_id: string
  concept_name: string
  students_count: number
  avg_mastery: number | null
  known_ratio?: number | null
  weak_ratio?: number | null
  unknown_ratio?: number | null
  needs_reteach: boolean
}

// ---------- برنامه مطالعه ----------

export interface StudyActivity {
  id: string
  day_offset: number
  title: string
  type: 'REVIEW' | 'PRACTICE' | 'STUDY' | 'DIAGNOSTIC' | string
  concept_id?: string | null
  concept_name?: string | null
  estimated_minutes: number
  rationale?: string | null
  status: 'PROPOSED' | 'ACCEPTED' | 'DONE' | 'DISMISSED' | string
}

export interface StudyPlan {
  id: string
  course_id: string
  exam_date?: string | null
  weekly_hours: number
  rationale_summary?: string | null
  status?: string
  activities: StudyActivity[]
}

export interface ReviewItem {
  concept_id: string
  concept_name: string
  due_at: string
  overdue?: boolean
  interval_days: number
  repetitions: number
  ease?: number
}

// ---------- استاد هوشمند ----------

export interface Citation {
  resource_id?: string
  resource_title?: string
  locator?: string
  quote?: string
}

export interface TutorMessage {
  id: string
  role: 'user' | 'assistant' | string
  content: string
  citations?: Citation[] | null
  reported?: boolean
  created_at?: string
}

// ---------- عملیات ----------

export interface AuditLogEntry {
  id: string
  actor?: string | null
  action: string
  entity_type: string
  entity_id?: string | null
  request_id?: string | null
  created_at: string
}

export interface AIRun {
  id: string
  purpose: string
  provider: string
  model: string
  prompt_version?: string | null
  status: string
  latency_ms?: number | null
  tokens_in?: number | null
  tokens_out?: number | null
  created_at: string
}

export interface AIRunList {
  items: AIRun[]
  total_tokens_out: number
}

// ---------- دستیار هوشمند «دانشگاه هوشمند من» (v3.11.0) ----------

/** نمای ماسک‌شدهٔ تنظیمات هستهٔ عامل — برای کارت پنل مدیریت */
export interface MsuAgentConnectionView {
  base_url: string
  origin: string
  accent: string
  accent2: string
  position: 'br' | 'bl'
  token_masked: string | null
  has_token: boolean
  token_source: string
  enabled: boolean
  enabled_source: string
  base_url_source: string
  updated_at: string | null
  data_owner: string
}

/** نتیجهٔ تست گام‌به‌گام اتصال به هستهٔ عامل */
export interface MsuAgentTestResult {
  ok: boolean
  steps: { step: string; ok: boolean; detail: string }[]
  base_url?: string
  engine?: string
}

// ---------- خطا ----------

export class ApiError extends Error {
  code: string
  details: Record<string, unknown>
  requestId: string | null
  status: number

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>, requestId?: string | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code || 'INTERNAL'
    this.details = details || {}
    this.requestId = requestId ?? null
  }
}

// ---------- توکن ----------

const TOKEN_KEY = 'student360_token'
const USER_KEY = 'student360_user'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* حافظه در دسترس نیست */
  }
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export function setStoredUser(user: User | null): void {
  try {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
  } catch {
    /* حافظه در دسترس نیست */
  }
}

/** ساخت query string از پارامترها (مقادیر خالی نادیده گرفته می‌شوند). */
export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const parts: string[] = []
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
  }
  return parts.length ? `?${parts.join('&')}` : ''
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  idempotencyKey?: string
  signal?: AbortSignal
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: string | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey

  const res = await fetch(`/api/v1${path}`, {
    method: options.method || 'GET',
    headers,
    body,
    signal: options.signal,
  })

  if (res.status === 401) {
    setToken(null)
    setStoredUser(null)
    window.dispatchEvent(new Event('s360:unauthorized'))
  }

  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }

  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: Record<string, unknown>; request_id?: string } } | null)?.error
    throw new ApiError(
      res.status,
      err?.code || 'INTERNAL',
      err?.message || `خطای ارتباط با سرور (${res.status})`,
      err?.details,
      err?.request_id,
    )
  }
  return data as T
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { method: 'GET', signal }),
  post: <T>(path: string, body?: unknown, idempotencyKey?: string) =>
    request<T>(path, { method: 'POST', body, idempotencyKey }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),

  /** دریافت فایل باینری با هدر Authorization (برای دانلود خروجی‌ها). */
  async getBlob(path: string): Promise<Blob> {
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    const res = await fetch(`/api/v1${path}`, { headers })
    if (!res.ok) throw new ApiError(res.status, 'DOWNLOAD_FAILED', 'دریافت فایل ناموفق بود')
    return res.blob()
  },
}

/** دانلود یک Blob با نام دلخواه در مرورگر. */
export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 3000)
}

/* ============================================================
   رصدخانه دانش — DTOهای «مسیر یادگیری» (نسخه ۳.۱)
   ============================================================ */

export interface TodaySuggestion {
  type: string
  title: string
  minutes: number
  concept_id: string | null
  reason: string
  url: string
  primary_action: string
}

export interface TodayChoice {
  key: string
  label: string
  url: string
  hint?: string
}

export interface ReviewSuggestion {
  concept_id: string
  concept_name: string
  due_at: string | null
  note: string
}

export interface TodayFocus {
  greeting: string
  course: { id: string; title: string; code: string }
  today_suggestion: TodaySuggestion
  choices: TodayChoice[]
  my_progress: { known: number; partial: number; weak: number; unassessed: number; total: number }
  reviews_suggested: ReviewSuggestion[]
  continue_session: SessionPlan | null
  note: string
}

export interface SessionStep {
  index: number
  kind: string
  title: string
  minutes: number
  done: boolean
  ref: string | null
  url: string
}

export interface SessionPlan {
  id: string
  course_id: string
  minutes: number
  state: 'ACTIVE' | 'PAUSED' | 'DONE'
  composition: SessionStep[] | null
  progress: { step_index: number } | null
  started_at: string | null
  completed_at: string | null
}

export interface PrepTier {
  tier: number
  label: string
  concepts: Array<{
    concept_id: string
    concept_name: string
    action: string
    minutes_hint: number
    why: string
    prereq_required?: string[]
  }>
}

export interface ExamPrepPlan {
  exam_date: string | null
  available_minutes: number | null
  priority_order: PrepTier[]
  prereq_required: string[]
  insufficient_evidence: Array<{ concept_id: string; concept_name: string }>
  coverage: { total_concepts: number; with_evidence: number; coverage_ratio: number | null; meaning: string }
  allocated_minutes: { total_needed: number; fits: boolean; covered?: string[]; left_minutes?: number; message: string } | null
  honesty_note: string
  programyar_note: string
  uncertainty_note: string
}

export interface MapNodeCard {
  concept_id: string
  concept_name: string
  status: string
  estimated_mastery: number | null
  card: {
    simple_explanation: string
    real_use: string | null
    prerequisites: string[]
    common_pitfalls: string[]
    evidence: { count: number; state_label?: string }
    practice: { label: string; url: string }
    ask_tutor: { label: string; url: string }
  }
}

export interface ConceptMapData {
  mode: string
  course_id: string
  stages: Array<Array<{ concept_id: string; concept_name: string; status: string; state_label?: string | null; next_step?: { label: string; url: string; ref?: string } | null }>>
  nodes?: MapNodeCard[]
  edges?: Array<{ from: string; to: string; type: string }>
  legend_note?: string
}

export interface StuckResult {
  id: string
  kind: string
  kind_label: string
  tutor_session_id: string | null
  message: string
}

export interface ClinicEntry {
  id: string
  pattern_key: string
  title: string
  concept_id: string | null
  concept_name: string | null
  status: string
  recurrence_count: number
  evidence_count: number
  student_explanation: string | null
  suggested_practice: { label: string; url: string } | null
  last_seen_at: string | null
  question: string
}

export interface ClinicData {
  entries: ClinicEntry[]
  note: string
}

export interface TeachBackResult {
  id: string
  concept_name: string
  rubric_scores: Array<{ criterion: string; score: number; max_score: number; evidence: string }> | null
  follow_up_question: string | null
  gaps: string[]
  encouragement: string
  note: string
}

export interface ProfessorActionsData {
  course_id: string
  cards: Array<{ type: string; title: string; detail: string; action_label: string; action_url: string }>
  note: string
}

export interface CoverageInfo {
  blueprint_concepts: string[]
  covered_concepts: string[]
  missing_concepts: string[]
  coverage_ratio: number | null
}

// ---------- دانلود فایل (خروجی‌های سرفصل — v3.5.0) ----------
export async function downloadFile(path: string): Promise<{ blob: Blob; filename: string }> {
  const token = getToken()
  const res = await fetch(`/api/v1${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (res.status === 401) {
    setToken(null)
    setStoredUser(null)
    window.dispatchEvent(new Event('s360:unauthorized'))
  }
  if (!res.ok) {
    throw new ApiError(res.status, 'EXPORT_FAILED', `دریافت فایل ناموفق بود (${res.status})`)
  }
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  const m = /filename\*=UTF-8''([^;]+)/i.exec(cd) || /filename="?([^";]+)"?/i.exec(cd)
  const filename = m ? decodeURIComponent(m[1]) : 'download'
  return { blob, filename }
}
