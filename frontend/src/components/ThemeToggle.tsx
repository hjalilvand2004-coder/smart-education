import { useEffect, useState } from 'react'
import { applyTheme, getStoredTheme, toggleTheme, type Theme } from '../theme'

const LABEL: Record<Theme, string> = {
  dark: 'تم شب',
  light: 'تم روز',
}

const TITLE: Record<Theme, string> = {
  dark: 'تغییر به تم روز',
  light: 'تغییر به تم شب',
}

/** دکمه تغییر تم شب/روز در بالای صفحه (سایدبار دسکتاپ و نوار بالای موبایل). */
export default function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme())

  // همگام‌سازی با تغییرهای بیرونی (مثلاً اسکریپت پیش از رندر)
  useEffect(() => {
    applyTheme(getStoredTheme())
  }, [])

  const onClick = () => {
    const next = toggleTheme()
    setThemeState(next)
  }

  return (
    <button
      type="button"
      className={`theme-toggle${theme === 'dark' ? ' theme-toggle-dark' : ' theme-toggle-light'}`}
      onClick={onClick}
      title={TITLE[theme]}
      aria-label={TITLE[theme]}
    >
      {theme === 'dark' ? (
        // ماه — در تم شب، کلیک به تم روز می‌رود
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      ) : (
        // خورشید — در تم روز، کلیک به تم شب می‌رود
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      )}
      <span>{LABEL[theme]}</span>
    </button>
  )
}
