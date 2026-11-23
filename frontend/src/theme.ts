export type Theme = 'dark' | 'light'

const STORAGE_KEY = 's360-theme'

/** تم پیش‌فرض سامانه: شب (کیهانی). */
export const DEFAULT_THEME: Theme = 'dark'

export function getStoredTheme(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

/** اعمال تم روی ریشه سند (قبل از اولین رندر هم فراخوانی می‌شود). */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
}

export function setTheme(theme: Theme): void {
  applyTheme(theme)
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* حافظه محلی در دسترس نیست — تم فقط برای همین نشست اعمال می‌شود */
  }
}

export function toggleTheme(): Theme {
  const next: Theme = getStoredTheme() === 'dark' ? 'light' : 'dark'
  setTheme(next)
  return next
}

/** اجرای آنی در ابتدای بارگذاری برنامه برای جلوگیری از پرش رنگ. */
export function initTheme(): Theme {
  const theme = getStoredTheme()
  applyTheme(theme)
  return theme
}
