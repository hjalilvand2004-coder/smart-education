import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getStoredUser, getToken, setStoredUser, setToken } from './api'
import type { User } from './api'

interface AuthContextValue {
  user: User | null
  token: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => getStoredUser())
  const [token, setTokenState] = useState<string | null>(() => getToken())
  const [loading, setLoading] = useState<boolean>(() => Boolean(getToken()))

  // بازیابی پروفایل پس از لود اگر توکن موجود است
  useEffect(() => {
    let cancelled = false
    const existing = getToken()
    if (!existing) {
      setLoading(false)
      return () => {
        cancelled = true
      }
    }
    api
      .get<User>('/auth/me')
      .then((me) => {
        if (cancelled) return
        setUser(me)
        setStoredUser(me)
        setTokenState(existing)
      })
      .catch(() => {
        if (cancelled) return
        setToken(null)
        setStoredUser(null)
        setUser(null)
        setTokenState(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // پاسخ ۴۰۱ از لایه API کاربر را خارج می‌کند
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null)
      setTokenState(null)
    }
    window.addEventListener('s360:unauthorized', onUnauthorized)
    return () => window.removeEventListener('s360:unauthorized', onUnauthorized)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.post<{ access_token: string; token_type: string; user: User }>(
      '/auth/login',
      { username, password },
    )
    setToken(res.access_token)
    setStoredUser(res.user)
    setTokenState(res.access_token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setStoredUser(null)
    setTokenState(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, token, loading, login, logout }),
    [user, token, loading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth باید داخل AuthProvider استفاده شود')
  return ctx
}

// ---------- نقش‌ها ----------

export const STAFF_COURSE_ROLES = ['PROFESSOR', 'ASSISTANT', 'GROUP_ADMIN']
export const GLOBAL_ADMIN_ROLES = ['EDUCATION_ADMIN', 'TECH_ADMIN']
const STAFF_GLOBAL_ROLES = ['PROFESSOR', 'EDUCATION_ADMIN', 'TECH_ADMIN', 'QUALITY_REVIEWER']

/** آیا کاربر در یک درس نقش کارکنان دارد؟ */
export function isCourseStaff(user: User | null, courseId?: string | null): boolean {
  if (!user) return false
  if (GLOBAL_ADMIN_ROLES.includes(user.role)) return true
  if (STAFF_GLOBAL_ROLES.includes(user.role) && user.role !== 'STUDENT') return true
  return user.course_roles.some(
    (cr) => STAFF_COURSE_ROLES.includes(cr.role) && (!courseId || cr.course_id === courseId),
  )
}

/** آیا کاربر در هر درسی نقش استاد/دستیار دارد (برای نمایش لینک استودیو)؟ */
export function hasAnyStaffCourse(user: User | null): boolean {
  if (!user) return false
  if (GLOBAL_ADMIN_ROLES.includes(user.role)) return true
  if (STAFF_GLOBAL_ROLES.includes(user.role)) return true
  return user.course_roles.some((cr) => STAFF_COURSE_ROLES.includes(cr.role))
}

export function isGlobalAdmin(user: User | null): boolean {
  return Boolean(user && GLOBAL_ADMIN_ROLES.includes(user.role))
}

/** نقش مؤثر در درس: اولویت با نقش درسی، سپس نقش سراسری. */
export function effectiveCourseRole(user: User | null, courseId: string): string {
  if (!user) return 'STUDENT'
  const cr = user.course_roles.find((c) => c.course_id === courseId)
  if (cr) return cr.role
  return user.role
}
