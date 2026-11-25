/**
 * موتور تقویم شمسی (جلالی) — الگوریتم استاندارد jalaali (عمومی و قطعی)
 * مستقل از ICU مرورگر؛ آفلاین و یکسان در همه محیط‌ها.
 * خروجی همهٔ توابع رشتهٔ فارسی با ارقام فارسی است.
 */

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

/** تبدیل ارقام لاتین به فارسی */
export function faDigits(v: string | number): string {
  return String(v).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)])
}

const div = (a: number, b: number) => Math.trunc(a / b)
const mod = (a: number, b: number) => a - Math.trunc(a / b) * b

/** ماه‌های شمسی */
export const JMONTHS = [
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
] as const

/** روزهای هفته (getDay(): ۰=یکشنبه … ۶=شنبه) */
const WEEKDAYS = ['یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه'] as const

interface JalCalResult { leap: number; gy: number; march: number }

function jalCal(jy: number): JalCalResult {
  const breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178]
  const bl = breaks.length
  const gy = jy + 621
  let leapJ = -14
  let jp = breaks[0]
  let jm = 0
  let jump = 0
  if (jy < jp || jy >= breaks[bl - 1]) throw new Error('سال شمسی خارج از بازه پشتیبانی: ' + jy)
  for (let i = 1; i < bl; i += 1) {
    jm = breaks[i]
    jump = jm - jp
    if (jy < jm) break
    leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4)
    jp = jm
  }
  let n = jy - jp
  leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4)
  if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1
  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150
  const march = 20 + leapJ - leapG
  if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33
  let leap = mod(mod(n + 1, 33) - 1, 4)
  if (leap === -1) leap = 4
  return { leap, gy, march }
}

function g2d(gy: number, gm: number, gd: number): number {
  let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4) + div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752
  return d
}

function d2g(jdn: number): { gy: number; gm: number; gd: number } {
  let j = 4 * jdn + 139361631
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
  const i = div(mod(j, 1461), 4) * 5 + 308
  const gd = div(mod(i, 153), 5) + 1
  const gm = mod(div(i, 153), 12) + 1
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6)
  return { gy, gm, gd }
}

function d2j(jdn: number): { jy: number; jm: number; jd: number } {
  const gy = d2g(jdn).gy
  let jy = gy - 621
  const r = jalCal(jy)
  const jdn1f = g2d(gy, 3, r.march)
  let k = jdn - jdn1f
  if (k >= 0) {
    if (k <= 185) return { jy, jm: 1 + div(k, 31), jd: mod(k, 31) + 1 }
    k -= 186
  } else {
    jy -= 1
    k += 179
    if (r.leap === 1) k += 1
  }
  return { jy, jm: 7 + div(k, 30), jd: mod(k, 30) + 1 }
}

export interface JDateParts { jy: number; jm: number; jd: number }

/** تبدیل شیء Date به اجزای شمسی */
export function toJalali(date: Date): JDateParts {
  return d2j(g2d(date.getFullYear(), date.getMonth() + 1, date.getDate()))
}

/** تبدیل اجزای شمسی به Date میلادی */
export function jalaliToGregorian(jy: number, jm: number, jd: number): Date {
  const g = d2g(j2d_(jy, jm, jd))
  return new Date(g.gy, g.gm - 1, g.gd)
}

function j2d_(jy: number, jm: number, jd: number): number {
  const r = jalCal(jy)
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1
}

export interface FmtOpts {
  /** ساعت را هم نشان بده */
  withTime?: boolean
  /** نام روز هفته را هم نشان بده */
  weekday?: boolean
  /** قالب بلند «۴ آذر ۱۴۰۴» (پیش‌فرض) یا عددی «۱۴۰۴/۰۹/۰۴» */
  long?: boolean
}

/** تاریخ/ساعت ISO را به رشتهٔ شمسی فارسی تبدیل می‌کند؛ ورودی نامعتبر → «—» */
export function fmtJalali(iso?: string | null, opts: FmtOpts = {}): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  try {
    const { jy, jm, jd } = toJalali(d)
    const body = opts.long === false
      ? faDigits(`${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`)
      : `${faDigits(jd)} ${JMONTHS[jm - 1]} ${faDigits(jy)}`
    const wd = opts.weekday ? `${WEEKDAYS[d.getDay()]}، ` : ''
    const hm = opts.withTime
      ? ` — ${faDigits(String(d.getHours()).padStart(2, '0'))}:${faDigits(String(d.getMinutes()).padStart(2, '0'))}`
      : ''
    return `${wd}${body}${hm}`
  } catch {
    return '—'
  }
}

/** ساعت ISO به قالب HH:MM فارسی */
export function fmtJalaliTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return faDigits(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`)
}

/** رشتهٔ میلادی خام برای تولتیپ */
export function gregorianTooltip(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** تاریخ امروز به شمسی (برای سرصفحه‌ها) */
export function todayJalali(weekday = true): string {
  return fmtJalali(new Date().toISOString(), { weekday, long: true })
}
