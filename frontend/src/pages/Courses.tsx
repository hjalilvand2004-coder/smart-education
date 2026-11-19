import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, qs } from '../api'
import type { Course } from '../api'
import { useAuth } from '../auth'
import StatusBadge, { roleLabel } from '../components/StatusBadge'

export default function Courses() {
  const { user } = useAuth()
  const [courses, setCourses] = useState<Course[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'درس‌های من | دانشجو۳۶۰'
  }, [])

  useEffect(() => {
    let alive = true
    api
      .get<Course[]>(`/courses${qs({})}`)
      .then((rows) => {
        if (alive) setCourses(rows || [])
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'خطا در دریافت درس‌ها')
      })
    return () => {
      alive = false
    }
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (courses === null) {
    return (
      <div className="center-note">
        <div className="spinner" />
        در حال دریافت درس‌ها…
      </div>
    )
  }
  if (courses.length === 0) {
    return (
      <div className="empty-box">
        <strong>درسی یافت نشد</strong>
        هنوز درسی به شما اختصاص داده نشده یا در درسی ثبت‌نام نکرده‌اید.
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>درس‌های من</h1>
          <div className="subtitle">
            {user ? `${user.full_name} عزیز، خوش آمدید.` : ''} برای ورود به فضای درس، یک درس را انتخاب کنید.
          </div>
        </div>
      </div>
      <div className="grid-cards">
        {courses.map((c) => (
          <Link key={c.id} className="course-card" to={`/course/${c.id}`}>
            <h3>{c.title}</h3>
            <div className="course-meta">
              <span>کد: {c.code}</span>
              {c.term && <span>ترم: {c.term}</span>}
              {c.department && <span>{c.department}</span>}
            </div>
            <div className="badge-row">
              <span className="badge badge-info">نقش شما: {roleLabel(c.my_role)}</span>
              {c.enrolled ? <span className="badge badge-success">ثبت‌نام‌شده</span> : null}
              {c.syllabus_status ? <StatusBadge status={c.syllabus_status} /> : null}
            </div>
          </Link>
        ))}
      </div>
    </>
  )
}
