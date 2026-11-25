import { useEffect, useState } from 'react'
import { getToken } from '../api'
import { ApiError } from '../api'
import { JDate } from '../components/JDate'

interface ReportSummary {
  generated_at: string
  users: {
    total: number
    by_role: Record<string, number>
    by_approval: Record<string, number>
    pending_approvals: number
  }
  courses: { total: number; enrollments: number }
  syllabus: { versions: Record<string, number> }
  content: { documents: number; versions: Record<string, number>; published: number }
  ai: {
    questions: number
    tutor_sessions: number
    tutor_messages: number
    ai_runs: number
    programyar_imports: number
    jobs_by_kind: Record<string, { total: number; SUCCEEDED: number; FAILED: number }>
  }
}

const ROLE_LABELS: Record<string, string> = {
  STUDENT: 'دانشجو', PROFESSOR: 'استاد', ASSISTANT: 'دستیار آموزشی',
  GROUP_ADMIN: 'مدیرگروه', EDUCATION_ADMIN: 'مدیر آموزشی',
  QUALITY_REVIEWER: 'کارشناس کیفیت', TECH_ADMIN: 'مدیر فنی',
}
const STATUS_LABELS: Record<string, string> = {
  DRAFT: 'پیش‌نویس', PENDING_REVIEW: 'در انتظار بررسی', APPROVED: 'تایید‌شده',
  SUPERSEDED: 'جایگزین‌شده', GENERATED: 'تولید‌شده', UNDER_REVIEW: 'در حال بررسی',
  PUBLISHED: 'منتشر‌شده', NEEDS_REVISION: 'نیازمند اصلاح', ACTIVE: 'فعال',
  PENDING: 'در انتظار تایید', REJECTED: 'رد‌شده', SUCCEEDED: 'موفق', FAILED: 'ناموفق',
}
const FORMATS: { fmt: string; label: string }[] = [
  { fmt: 'pdf', label: 'PDF' },
  { fmt: 'docx', label: 'Word' },
  { fmt: 'html', label: 'HTML' },
  { fmt: 'pptx', label: 'PowerPoint' },
]

function StatCard({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="kv" style={{ textAlign: 'center' }}>
      <div className="kv-label">{label}</div>
      <div className="kv-value" style={{ fontSize: '1.4rem', color: tone || undefined }}>{value}</div>
    </div>
  )
}

function MiniTable({ title, rows }: { title: string; rows: [string, number][] }) {
  return (
    <div className="card" style={{ margin: 0 }}>
      <h3 style={{ color: 'var(--brand-deep)' }}>{title}</h3>
      {rows.length === 0 ? (
        <div className="muted">داده‌ای ثبت نشده است.</div>
      ) : (
        <table className="table" style={{ minWidth: 0 }}>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}>
                <td>{k}</td>
                <td style={{ textAlign: 'left', fontWeight: 700 }}>{v.toLocaleString('fa-IR')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/** گزارش جامع سامانه: آمار زنده + خروجی PDF/Word/HTML/PowerPoint. */
export default function Reports() {
  const [stats, setStats] = useState<ReportSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyFmt, setBusyFmt] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'گزارش‌ها | دانشجو۳۶۰'
    import('../api').then(({ api }) =>
      api.get<ReportSummary>('/reports/summary')
        .then(setStats)
        .catch((err: unknown) => {
          setError(err instanceof ApiError ? err.message : 'خطا در دریافت گزارش')
        }),
    )
  }, [])

  const download = async (fmt: string) => {
    setBusyFmt(fmt)
    try {
      const resp = await fetch(`/api/v1/reports/export/${fmt}`, {
        headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : undefined,
      })
      if (!resp.ok) throw new Error('خطا در تولید خروجی')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `smart-learning-report.${fmt}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('تولید خروجی ناموفق بود')
    } finally {
      setBusyFmt(null)
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>گزارش جامع سامانه</h1>
          <div className="subtitle">
            آمار کاربران، درس‌ها، محتوا و هوش مصنوعی — با خروجی چهارفرمتی گرافیکی
            {stats ? <> · تولید: <JDate iso={stats.generated_at} withTime /> </> : ''}
          </div>
        </div>
      </div>

      {error && <div className="error-box"><span>{error}</span></div>}

      <div className="card">
        <div className="card-title">
          <h2>خروجی گزارش</h2>
          <span className="muted">شامل نمودارهای فارسی کاربران، حساب‌ها، AI و محتوا</span>
        </div>
        <div className="btn-row">
          {FORMATS.map((f) => (
            <button key={f.fmt} type="button" className="btn btn-primary btn-sm"
                    disabled={busyFmt !== null} onClick={() => download(f.fmt)}>
              {busyFmt === f.fmt ? 'در حال ساخت…' : `دانلود ${f.label}`}
            </button>
          ))}
        </div>
      </div>

      {stats === null ? (
        !error && (
          <div className="center-note">
            <div className="spinner" />
            در حال جمع‌آوری آمار…
          </div>
        )
      ) : (
        <>
          <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
            <StatCard label="کاربران" value={stats.users.total.toLocaleString('fa-IR')} tone="var(--brand-deep)" />
            <StatCard label="در انتظار تایید" value={stats.users.pending_approvals.toLocaleString('fa-IR')}
                      tone={stats.users.pending_approvals > 0 ? 'var(--warn-text)' : undefined} />
            <StatCard label="درس‌ها" value={stats.courses.total.toLocaleString('fa-IR')} />
            <StatCard label="اسناد آموزشی" value={stats.content.documents.toLocaleString('fa-IR')} />
            <StatCard label="نسخه منتشر‌شده" value={stats.content.published.toLocaleString('fa-IR')} tone="var(--success-text)" />
            <StatCard label="بانک سوال" value={stats.ai.questions.toLocaleString('fa-IR')} />
            <StatCard label="جلسات استاد هوشمند" value={stats.ai.tutor_sessions.toLocaleString('fa-IR')} />
            <StatCard label="واردات از برنامه‌یار۳۶۰" value={stats.ai.programyar_imports.toLocaleString('fa-IR')} tone="var(--ai-text)" />
          </div>

          <div className="grid-cards section-gap">
            <MiniTable title="کاربران به تفکیک نقش"
                       rows={Object.entries(stats.users.by_role)
                         .map(([k, v]) => [ROLE_LABELS[k] || k, v] as [string, number])
                         .sort((a, b) => b[1] - a[1])} />
            <MiniTable title="وضعیت حساب‌ها"
                       rows={Object.entries(stats.users.by_approval)
                         .map(([k, v]) => [STATUS_LABELS[k] || k, v] as [string, number])} />
            <MiniTable title="نسخه‌های محتوا"
                       rows={Object.entries(stats.content.versions)
                         .map(([k, v]) => [STATUS_LABELS[k] || k, v] as [string, number])} />
            <MiniTable title="فرایندهای هوش مصنوعی"
                       rows={Object.entries(stats.ai.jobs_by_kind)
                         .map(([k, v]) => [k, v.total] as [string, number])
                         .sort((a, b) => b[1] - a[1])} />
          </div>
        </>
      )}
    </>
  )
}
