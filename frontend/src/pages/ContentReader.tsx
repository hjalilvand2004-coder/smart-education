import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { ContentVersion, PublishedContent } from '../api'
import Blocks from '../components/Blocks'
import StatusBadge from '../components/StatusBadge'
import { fmtJalali } from '../utils/jalali'

/** ثبت رویداد مشاهده محتوا (خطاها نادیده گرفته می‌شوند؛ تحلیلی است). */
function reportView(courseId: string, versionId: string): void {
  api
    .post('/learning-events', {
      course_id: courseId,
      type: 'CONTENT_VIEWED',
      payload: { content_version_id: versionId },
    })
    .catch(() => undefined)
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  try {
    return fmtJalali(iso, { withTime: true })
  } catch {
    return iso
  }
}

/** خواننده محتوای منتشرشده؛ بدون versionId فهرست محتواهای منتشرشده را نشان می‌دهد. */
export default function ContentReader({ courseId, versionId }: { courseId: string; versionId?: string }) {
  const navigate = useNavigate()
  const [contents, setContents] = useState<PublishedContent[] | null>(versionId ? [] : null)
  const [version, setVersion] = useState<ContentVersion | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reportOpen, setReportOpen] = useState(false)
  const [reportNote, setReportNote] = useState('')
  const [reportSent, setReportSent] = useState(false)

  useEffect(() => {
    if (!versionId) return
    let alive = true
    setVersion(null)
    setError(null)
    api
      .get<ContentVersion>(`/content-versions/${versionId}`)
      .then((v) => {
        if (!alive) return
        setVersion(v)
        if (courseId) reportView(courseId, versionId)
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'خطا در دریافت محتوا')
      })
    return () => {
      alive = false
    }
  }, [versionId, courseId])

  useEffect(() => {
    if (versionId || !courseId) return
    let alive = true
    api
      .get<PublishedContent[]>(`/courses/${courseId}/contents`)
      .then((rows) => {
        if (alive) setContents(rows || [])
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'خطا در دریافت فهرست محتوا')
      })
    return () => {
      alive = false
    }
  }, [courseId, versionId])

  const submitReport = useCallback(
    async (e: FormEvent) => {
      e.preventDefault()
      if (!versionId) return
      try {
        await api.post('/learning-events', {
          course_id: courseId,
          type: 'CONTENT_ISSUE_REPORTED',
          payload: { content_version_id: versionId, note: reportNote },
        })
        setReportSent(true)
        setReportOpen(false)
        setReportNote('')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'ثبت گزارش ناموفق بود')
      }
    },
    [courseId, versionId, reportNote],
  )

  // حالت فهرست محتوا (وقتی نسخه مشخص نشده)
  if (!versionId) {
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
          پس از انتشار محتوا توسط استاد، از همین‌جا قابل مطالعه خواهد بود.
        </div>
      )
    }
    return (
      <>
        <h2>محتواهای منتشرشده درس</h2>
        <div className="muted" style={{ marginBottom: 12 }}>
          یک محتوا را برای مطالعه انتخاب کنید.
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
              مطالعه
            </button>
          </div>
        ))}
      </>
    )
  }

  // حالت خواندن نسخه
  if (error) return <div className="error-box">{error}</div>
  if (version === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال بارگذاری محتوا…
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>{version.document_title || 'محتوای آموزشی'}</h1>
          <div className="subtitle badge-row">
            <span className="badge badge-info">نسخه {version.version_number}</span>
            <StatusBadge status={version.status} />
            <span className="badge badge-neutral">بازبینی شماره {version.revision}</span>
          </div>
        </div>
        <div className="btn-row">
          <Link className="btn btn-sm" to={`/course/${courseId}`}>بازگشت به درس</Link>
          <button type="button" className="btn btn-sm" onClick={() => setReportOpen(!reportOpen)}>
            گزارش خطا
          </button>
        </div>
      </div>

      {reportSent && <div className="success-box">گزارش شما ثبت شد. سپاس از همکاری شما.</div>}

      {reportOpen && (
        <form className="edit-form" onSubmit={submitReport}>
          <label className="label" htmlFor="report-note">مشکل این بخش را توضیح دهید</label>
          <textarea
            id="report-note"
            className="textarea"
            value={reportNote}
            onChange={(e) => setReportNote(e.target.value)}
            placeholder="مثلاً: فرمول این بخش ناقص است / مثال با سرفصل هم‌خوانی ندارد…"
            required
          />
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button type="submit" className="btn btn-primary btn-sm">ارسال گزارش</button>
            <button type="button" className="btn btn-sm" onClick={() => setReportOpen(false)}>انصراف</button>
          </div>
        </form>
      )}

      <Blocks blocks={version.blocks || []} />
    </>
  )
}
