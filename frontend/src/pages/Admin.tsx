import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { AIRunList, AggregateMastery, AuditLogEntry, Course } from '../api'
import StatusBadge from '../components/StatusBadge'

const ROLE_FA: Record<string, string> = {
  STUDENT: 'دانشجو', PROFESSOR: 'استاد', ASSISTANT: 'دستیار آموزشی',
  GROUP_ADMIN: 'مدیرگروه', EDUCATION_ADMIN: 'مدیر آموزشی',
  QUALITY_REVIEWER: 'کارشناس کیفیت', TECH_ADMIN: 'مدیر فنی',
}

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : `${Math.round(v * 100)}٪`
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

interface AdminUser {
  id: string
  username: string
  full_name: string
  email?: string | null
  role: string
  is_active: boolean
  approval_status: string
  sso_linked: boolean
}

const APPROVAL_BADGE: Record<string, string> = {
  ACTIVE: 'badge-success', PENDING: 'badge-warn', REJECTED: 'badge-danger',
}
const APPROVAL_LABEL: Record<string, string> = {
  ACTIVE: 'فعال', PENDING: 'در انتظار تایید', REJECTED: 'رد‌شده',
}

/** پنل مدیریت: مدیریت کاربران و تایید، نقشه ضعف کلاس، حسابرسی و مصرف AI. */
export default function Admin() {
  const [courses, setCourses] = useState<Course[]>([])
  const [courseId, setCourseId] = useState('')
  const [aggregate, setAggregate] = useState<AggregateMastery[] | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[] | null>(null)
  const [aiRuns, setAiRuns] = useState<AIRunList | null>(null)
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [pendingOnly, setPendingOnly] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'پنل مدیریت | دانشجو۳۶۰'
  }, [])

  useEffect(() => {
    let alive = true
    api
      .get<Course[]>('/courses')
      .then((rows) => {
        if (!alive) return
        setCourses(rows || [])
        if (rows.length > 0) setCourseId(rows[0].id)
      })
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : 'خطا در دریافت درس‌ها'))
    api
      .get<AuditLogEntry[]>('/audit-logs?limit=100')
      .then((rows) => alive && setAuditLogs(rows || []))
      .catch(() => alive && setAuditLogs([]))
    api
      .get<AIRunList>('/ai-runs')
      .then((rows) => alive && setAiRuns(rows))
      .catch(() => alive && setAiRuns({ items: [], total_tokens_out: 0 }))
    return () => {
      alive = false
    }
  }, [])

  const loadAggregate = useCallback(async (cid: string) => {
    if (!cid) return
    setAggregate(null)
    try {
      const rows = await api.get<AggregateMastery[]>(`/courses/${cid}/mastery/aggregate`)
      setAggregate(rows || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت نقشه ضعف کلاس')
    }
  }, [])

  useEffect(() => {
    loadAggregate(courseId)
  }, [courseId, loadAggregate])

  const loadUsers = useCallback(async () => {
    setUsers(null)
    try {
      const res = await api.get<{ items: AdminUser[] }>(
        `/users${pendingOnly ? '?approval=PENDING' : ''}`)
      setUsers(res.items || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطا در دریافت کاربران')
      setUsers([])
    }
  }, [pendingOnly])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const userAction = async (id: string, action: 'approve' | 'reject') => {
    try {
      await api.post(`/users/${id}/${action}`, {})
      await loadUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'عملیات ناموفق بود')
    }
  }

  const resetPassword = async (id: string) => {
    const pwd = window.prompt('رمز عبور جدید را وارد کنید (حداقل ۸ نویسه):')
    if (!pwd || pwd.length < 8) return
    try {
      await api.post(`/users/${id}/reset-password`, { new_password: pwd })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'بازنشانی رمز ناموفق بود')
    }
  }

  const currentCourse = courses.find((c) => c.id === courseId)

  return (
    <>
      <div className="page-header">
        <div>
          <h1>پنل مدیریت آموزشی</h1>
          <div className="subtitle">نقشه ضعف کلاس، ردپای حسابرسی و مصرف مدل‌های هوش مصنوعی</div>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <div className="card-title">
          <h2>مدیریت کاربران و گردش‌کار تایید</h2>
          <label className="check-row">
            <input type="checkbox" checked={pendingOnly}
                   onChange={(e) => setPendingOnly(e.target.checked)} />
            فقط در انتظار تایید
          </label>
        </div>
        {users === null ? (
          <div className="center-note"><div className="spinner" />در حال دریافت کاربران…</div>
        ) : users.length === 0 ? (
          <div className="empty-box">
            <strong>{pendingOnly ? 'درخواست تاییدی وجود ندارد' : 'کاربری یافت نشد'}</strong>
            ثبت‌نام‌های جدید (استاد/مدیرگروه) پس از بررسی از همین بخش تایید می‌شوند.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>کاربر</th>
                  <th>نقش</th>
                  <th>وضعیت</th>
                  <th>SSO</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <strong>{u.full_name}</strong>
                      <div dir="ltr" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{u.username}</div>
                    </td>
                    <td><span className="badge badge-info">{ROLE_FA[u.role] || u.role}</span></td>
                    <td>
                      <span className={`badge ${APPROVAL_BADGE[u.approval_status] || 'badge-neutral'}`}>
                        {APPROVAL_LABEL[u.approval_status] || u.approval_status}
                      </span>
                    </td>
                    <td>{u.sso_linked ? <span className="badge badge-ai">متصل</span> : <span className="muted">—</span>}</td>
                    <td>
                      <div className="btn-row">
                        {u.approval_status === 'PENDING' && (
                          <>
                            <button type="button" className="btn btn-sm btn-success"
                                    onClick={() => userAction(u.id, 'approve')}>تایید</button>
                            <button type="button" className="btn btn-sm btn-danger"
                                    onClick={() => userAction(u.id, 'reject')}>رد</button>
                          </>
                        )}
                        <button type="button" className="btn btn-sm"
                                onClick={() => resetPassword(u.id)}>بازنشانی رمز</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">
          <h2>نقشه ضعف کلاس</h2>
          {currentCourse ? <span className="badge badge-info">{currentCourse.title}</span> : null}
        </div>
        <div className="form-item" style={{ maxWidth: 360, marginBottom: 12 }}>
          <label className="label" htmlFor="admin-course">انتخاب درس</label>
          <select id="admin-course" className="select" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.code})
              </option>
            ))}
          </select>
        </div>
        {aggregate === null ? (
          <div className="center-note">
            <div className="spinner" />
            در حال دریافت نقشه ضعف…
          </div>
        ) : aggregate.length === 0 ? (
          <div className="empty-box">داده تسلط تجمیعی برای این درس ثبت نشده است.</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>مفهوم</th>
                  <th>میانگین تسلط</th>
                  <th>نسبت ضعیف</th>
                  <th>نامشخص</th>
                  <th>تعداد دانشجو</th>
                  <th>نیاز به بازآموزی</th>
                </tr>
              </thead>
              <tbody>
                {aggregate.map((a) => (
                  <tr key={a.concept_id} className={a.needs_reteach ? 'highlight-danger' : ''}>
                    <td>{a.concept_name}</td>
                    <td>
                      <div className="progress-row" style={{ margin: 0 }}>
                        <div className="progress" style={{ maxWidth: 120 }}>
                          <div
                            className={`progress-fill ${(a.avg_mastery ?? 0) >= 0.7 ? 'success' : (a.avg_mastery ?? 0) >= 0.4 ? 'warn' : 'danger'}`}
                            style={{ width: `${Math.round((a.avg_mastery ?? 0) * 100)}%` }}
                          />
                        </div>
                        <span className="progress-value">{pct(a.avg_mastery)}</span>
                      </div>
                    </td>
                    <td>{pct(a.weak_ratio)}</td>
                    <td>{pct(a.unknown_ratio)}</td>
                    <td>{a.students_count}</td>
                    <td>
                      {a.needs_reteach ? (
                        <span className="badge badge-danger">نیاز به بازآموزی</span>
                      ) : (
                        <span className="badge badge-success">وضعیت قابل قبول</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h2>ردپای حسابرسی (Audit)</h2>
        {auditLogs === null ? (
          <div className="center-note">
            <div className="spinner" />
            در حال دریافت…
          </div>
        ) : auditLogs.length === 0 ? (
          <div className="empty-box">رکورد حسابرسی ثبت نشده است.</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>عامل</th>
                  <th>عملیات</th>
                  <th>موجودیت</th>
                  <th>شناسه</th>
                  <th>زمان</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((r) => (
                  <tr key={r.id}>
                    <td>{r.actor || '—'}</td>
                    <td><span className="badge badge-neutral">{r.action}</span></td>
                    <td>{r.entity_type}</td>
                    <td dir="ltr" style={{ fontSize: '0.75rem' }}>{r.entity_id?.slice(0, 8) || '—'}</td>
                    <td>{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">
          <h2>مصرف مدل‌های هوش مصنوعی</h2>
          {aiRuns ? <span className="badge badge-ai">مجموع توکن خروجی: {aiRuns.total_tokens_out.toLocaleString('fa-IR')}</span> : null}
        </div>
        {aiRuns === null ? (
          <div className="center-note">
            <div className="spinner" />
            در حال دریافت…
          </div>
        ) : aiRuns.items.length === 0 ? (
          <div className="empty-box">اجرای مدلی ثبت نشده است.</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>هدف</th>
                  <th>مدل</th>
                  <th>وضعیت</th>
                  <th>تأخیر</th>
                  <th>توکن ورودی</th>
                  <th>توکن خروجی</th>
                  <th>زمان</th>
                </tr>
              </thead>
              <tbody>
                {aiRuns.items.map((r) => (
                  <tr key={r.id}>
                    <td>{r.purpose}</td>
                    <td dir="ltr" style={{ fontSize: '0.78rem' }}>{r.provider}/{r.model}</td>
                    <td><StatusBadge status={r.status} /></td>
                    <td>{r.latency_ms != null ? `${r.latency_ms.toLocaleString('fa-IR')} ms` : '—'}</td>
                    <td>{r.tokens_in ?? '—'}</td>
                    <td>{r.tokens_out ?? '—'}</td>
                    <td>{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
