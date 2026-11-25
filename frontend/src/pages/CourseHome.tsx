import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import type { ConceptGraph, CourseDetail, PublishedContent, Syllabus } from '../api'
import { isCourseStaff, useAuth } from '../auth'
import ConceptMap from '../components/ConceptMap'
import { kindLabel, roleLabel } from '../components/StatusBadge'
import Assessments from './Assessments'
import Mastery from './Mastery'
import StudyPlan from './StudyPlan'
import Tutor from './Tutor'
import { fmtJalali } from '../utils/jalali'

const TABS = [
  { key: 'content', label: 'محتوای منتشرشده' },
  { key: 'syllabus', label: 'سرفصل' },
  { key: 'map', label: 'نقشه مفاهیم' },
  { key: 'mastery', label: 'تسلط من' },
  { key: 'quizzes', label: 'آزمون‌ها' },
  { key: 'tutor', label: 'استاد هوشمند' },
  { key: 'plan', label: 'برنامه مطالعه' },
] as const

type TabKey = (typeof TABS)[number]['key']

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  try {
    return fmtJalali(iso, { withTime: true })
  } catch {
    return iso
  }
}

function SyllabusTab({ courseId }: { courseId: string }) {
  const [syllabus, setSyllabus] = useState<Syllabus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .get<Syllabus>(`/courses/${courseId}/syllabus`)
      .then((s) => alive && setSyllabus(s))
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت سرفصل'))
    return () => {
      alive = false
    }
  }, [courseId])

  if (error) return <div className="error-box">{error}</div>
  if (syllabus === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت سرفصل…
      </div>
    )
  }

  return (
    <>
      <div className="card">
        <div className="card-title">
          <h2>{syllabus.title || 'سرفصل مصوب درس'}</h2>
          <div className="badge-row">
            <span className="badge badge-neutral">نسخه {syllabus.version_number}</span>
            <span className="badge badge-info">وضعیت: {kindLabel(syllabus.status)}</span>
          </div>
        </div>
        {syllabus.chapters.length === 0 ? (
          <div className="empty-box">فصلی در سرفصل ثبت نشده است.</div>
        ) : (
          <div className="syllabus-tree">
            {syllabus.chapters.map((ch) => (
              <div key={ch.id} style={{ marginBottom: 12 }}>
                <h3>
                  {ch.title}
                  {ch.suggested_hours ? <span className="muted"> — {ch.suggested_hours} ساعت</span> : null}
                </h3>
                {ch.topics.map((t) => (
                  <div key={t.id} className="topic-row">
                    <span>{t.title}</span>
                    {t.suggested_hours ? <span className="muted">{t.suggested_hours} ساعت</span> : null}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="card">
        <h3>اهداف یادگیری</h3>
        {syllabus.objectives.length === 0 ? (
          <div className="muted">هدفی ثبت نشده است.</div>
        ) : (
          syllabus.objectives.map((o) => (
            <div key={o.id} className="objective-row">
              <span className="badge badge-neutral">{o.code}</span>
              <span>{o.statement}</span>
            </div>
          ))
        )}
      </div>
    </>
  )
}

function MapTab({ courseId }: { courseId: string }) {
  const [graph, setGraph] = useState<ConceptGraph | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .get<ConceptGraph>(`/courses/${courseId}/concept-graph`)
      .then((g) => alive && setGraph(g))
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت نقشه مفاهیم'))
    return () => {
      alive = false
    }
  }, [courseId])

  if (error) return <div className="error-box">{error}</div>
  if (graph === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت نقشه مفاهیم…
      </div>
    )
  }
  return <ConceptMap graph={graph} />
}

function ContentTab({ courseId }: { courseId: string }) {
  const navigate = useNavigate()
  const [contents, setContents] = useState<PublishedContent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .get<PublishedContent[]>(`/courses/${courseId}/contents`)
      .then((rows) => alive && setContents(rows || []))
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت محتوا'))
    return () => {
      alive = false
    }
  }, [courseId])

  if (error) return <div className="error-box">{error}</div>
  if (contents === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت محتواهای منتشرشده…
      </div>
    )
  }
  if (contents.length === 0) {
    return (
      <div className="empty-box">
        <strong>هنوز محتوایی منتشر نشده است</strong>
        پس از انتشار محتوا توسط استاد، از همین بخش قابل مطالعه خواهد بود.
      </div>
    )
  }
  return (
    <div className="card">
      <h2>محتواهای منتشرشده درس</h2>
      <div className="muted" style={{ marginBottom: 12 }}>
        یک محتوا را برای مطالعه انتخاب کنید؛ مشاهده هر محتوا برای تحلیل یادگیری ثبت می‌شود.
      </div>
      {contents.map((c) => (
        <div key={c.version_id} className="activity-row">
          <div>
            <strong>{c.document_title}</strong>
            <div className="muted">
              نسخه {c.version_number} — انتشار: {fmtDate(c.published_at)}
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => navigate(`/course/${courseId}/content/${c.version_id}`)}
          >
            مطالعه محتوا
          </button>
        </div>
      ))}
    </div>
  )
}

export default function CourseHome() {
  const { courseId = '' } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const tab = (searchParams.get('tab') as TabKey) || 'content'

  useEffect(() => {
    let alive = true
    api
      .get<CourseDetail>(`/courses/${courseId}`)
      .then((c) => alive && setCourse(c))
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت درس'))
    return () => {
      alive = false
    }
  }, [courseId])

  const selectTab = (key: TabKey) => {
    setSearchParams({ tab: key }, { replace: true })
  }

  if (error) return <div className="error-box">{error}</div>
  if (course === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال بارگذاری درس…
      </div>
    )
  }

  const staff = isCourseStaff(user, courseId)

  return (
    <>
      <div className="page-header">
        <div>
          <h1>{course.title}</h1>
          <div className="subtitle">
            کد درس: {course.code}
            {course.professor ? ` — استاد: ${course.professor}` : ''}
            {course.term ? ` — ترم: ${course.term}` : ''}
          </div>
          <div className="badge-row" style={{ marginTop: 6 }}>
            <span className="badge badge-info">نقش شما: {roleLabel(course.my_role)}</span>
            {course.enrolled ? <span className="badge badge-success">ثبت‌نام‌شده</span> : null}
          </div>
        </div>
        <div className="btn-row">
          {staff && (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate(`/studio/${courseId}`)}>
              استودیوی محتوا
            </button>
          )}
        </div>
      </div>

      {course.description ? <p className="muted">{course.description}</p> : null}

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            className={`tab${tab === t.key ? ' active' : ''}`}
            onClick={() => selectTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'content' && <ContentTab courseId={courseId} />}
      {tab === 'syllabus' && <SyllabusTab courseId={courseId} />}
      {tab === 'map' && <MapTab courseId={courseId} />}
      {tab === 'mastery' && <Mastery courseId={courseId} />}
      {tab === 'quizzes' && <Assessments courseId={courseId} />}
      {tab === 'tutor' && <Tutor courseId={courseId} />}
      {tab === 'plan' && <StudyPlan courseId={courseId} />}
    </>
  )
}
