import { fmtJalali, gregorianTooltip } from '../utils/jalali'

const IconCal = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
)

export interface JDateProps {
  /** تاریخ/ساعت ISO از بک‌اند */
  iso?: string | null
  /** pill: نشان شیشه‌ای با آیکن — text: متن سادهٔ رنگی */
  variant?: 'pill' | 'text'
  withTime?: boolean
  weekday?: boolean
  /** قالب بلند «۴ آذر ۱۴۰۴» (پیش‌فرض) یا عددی «۱۴۰۴/۰۹/۰۴» */
  long?: boolean
  /** متن جایگزین وقتی تاریخ وجود ندارد */
  fallback?: string
  /** تولتیپ میلادی خام */
  gregorianTip?: boolean
}

/**
 * JDate — نمایش تاریخ شمسی با ارقام فارسی و تولتیپ میلادی.
 * قطعی و آفلاین (موتور جلالی داخلی، بدون وابستگی به ICU مرورگر).
 */
export function JDate({
  iso,
  variant = 'pill',
  withTime = false,
  weekday = false,
  long = true,
  fallback = '—',
  gregorianTip = true,
}: JDateProps) {
  const text = fmtJalali(iso, { withTime, weekday, long })
  const cls = variant === 'pill' ? 'jdate-pill' : 'jdate-text'
  if (!iso || text === '—') {
    return <span className={`${cls} jdate-empty`}>{fallback}</span>
  }
  return (
    <span className={cls} title={gregorianTip ? `میلادی: ${gregorianTooltip(iso)}` : undefined}>
      {variant === 'pill' && <IconCal />}
      {text}
    </span>
  )
}

export default JDate
