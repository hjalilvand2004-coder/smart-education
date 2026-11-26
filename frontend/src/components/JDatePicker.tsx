import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { faDigits, JMONTHS, jalaliToGregorian, toJalali } from '../utils/jalali'

/** تعداد روزهای هر ماه شمسی (اسفند در سال کبیسه ۳۰ روز — leapVal=0) */
function jalaliMonthLength(jy: number, jm: number): number {
  if (jm <= 6) return 31
  if (jm <= 11) return 30
  // محاسبهٔ کبیسه با همان الگوریتم jalCal (موتور utils/jalali از آن استفاده می‌کند)
  const div = (a: number, b: number) => Math.trunc(a / b)
  const mod = (a: number, b: number) => a - Math.trunc(a / b) * b
  const breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178]
  let jp = breaks[0]
  let jm0 = 0
  let jump = 0
  for (let i = 1; i < breaks.length; i += 1) {
    jm0 = breaks[i]
    jump = jm0 - jp
    if (jy < jm0) break
    jp = jm0
  }
  let n = jy - jp
  // توجه: خط «leapJ += 1» در الگوریتم کامل فقط بر مُهر سال (leapJ) اثر دارد،
  // نه بر n؛ محاسبهٔ leap فقط به n نهایی وابسته است.
  if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33
  let leap = mod(mod(n + 1, 33) - 1, 4)
  if (leap === -1) leap = 4
  return leap === 0 ? 30 : 29
}

/** Date محلی → رشتهٔ YYYY-MM-DD (بدون انحراف منطقهٔ زمانی) */
function isoOfDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** رشتهٔ YYYY-MM-DD → Date محلی؛ نامعتبر → null */
function dateOfIso(iso: string | undefined | null): Date | null {
  if (!iso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return Number.isNaN(d.getTime()) ? null : d
}

export interface JDatePickerProps {
  /** تاریخ به شکل میلادی ISO «YYYY-MM-DD» (هم‌قرارداد input type=date) — "" یعنی خالی */
  value: string
  onChange: (isoDate: string) => void
  id?: string
  placeholder?: string
  ariaLabel?: string
  /** بازهٔ مجاز سال شمسی */
  minYear?: number
  maxYear?: number
}

const WEEK_COLS = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'] // ستون اول = شنبه (RTL)

/**
 * JDatePicker — تقویم شمسی زیبا برای فرم‌ها (v3.10.0).
 * جایگزین input type=date بومی که تقویم میلادی نشان می‌داد؛ قرارداد مقدار
 * (YYYY-MM-DD میلادی) بدون تغییر می‌ماند تا بک‌اند دست‌نخورده بماند.
 * آفلاین و قطعی بر پایهٔ موتور جلالی؛ تم‌آگاه و RTL.
 */
export default function JDatePicker({
  value, onChange, id, placeholder = 'انتخاب تاریخ شمسی…',
  ariaLabel = 'انتخاب تاریخ شمسی', minYear = 1370, maxYear = 1450,
}: JDatePickerProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const popRef = useRef<HTMLDivElement | null>(null)
  /** موقعیت پاپ‌آپ (fixed در body تا از overflow کانتینرها مثل .card متاثر نشود) */
  const [pos, setPos] = useState<{ top: number; right: number; width: number } | null>(null)
  const today = useMemo(() => toJalali(new Date()), [])
  const selected = useMemo(() => dateOfIso(value), [value])
  const selJ = useMemo(() => (selected ? toJalali(selected) : null), [selected])
  const viewJ = selected ? toJalali(selected) : today

  // نمای باز تقویم (ماه/سال مستقل از انتخاب)
  const [view, setView] = useState({ jy: viewJ.jy, jm: viewJ.jm })
  useEffect(() => {
    if (open) setView({ jy: viewJ.jy, jm: viewJ.jm })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const placePop = () => {
    const rect = rootRef.current?.getBoundingClientRect()
    if (!rect) return
    const width = Math.min(320, Math.max(280, window.innerWidth - 16))
    const popH = popRef.current?.offsetHeight ?? 380
    let top = rect.bottom + 6
    if (top + popH > window.innerHeight - 8) {
      top = Math.max(8, rect.top - popH - 6) // اگر جا نبود، رو به بالا
    }
    setPos({ top, right: window.innerWidth - rect.right, width })
  }

  useLayoutEffect(() => {
    if (!open) { setPos(null); return }
    placePop()
    // جابه‌جایی اسکرول/تغییر اندازه: بازموقعیت‌سازی (capture تا اسکرول والدین هم بگیرد)
    window.addEventListener('scroll', placePop, true)
    window.addEventListener('resize', placePop)
    return () => {
      window.removeEventListener('scroll', placePop, true)
      window.removeEventListener('resize', placePop)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // بستن با کلیک بیرون یا Esc
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (rootRef.current && !rootRef.current.contains(t)
          && popRef.current && !popRef.current.contains(t)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const monthLen = jalaliMonthLength(view.jy, view.jm)
  // اولین روز ماه: ستون شنبه‌محور (Date.getDay(): یکشنبه=۰ … شنبه=۶)
  const firstCol = useMemo(() => {
    const g = jalaliToGregorian(view.jy, view.jm, 1)
    return (g.getDay() + 1) % 7
  }, [view])

  const shiftMonth = (delta: number) => {
    setView((v) => {
      let jm = v.jm + delta
      let jy = v.jy
      if (jm > 12) { jm = 1; jy += 1 }
      if (jm < 1) { jm = 12; jy -= 1 }
      return { jy: Math.min(maxYear, Math.max(minYear, jy)), jm }
    })
  }
  const shiftYear = (delta: number) => {
    setView((v) => ({ ...v, jy: Math.min(maxYear, Math.max(minYear, v.jy + delta)) }))
  }

  const pickDay = (jd: number) => {
    const g = jalaliToGregorian(view.jy, view.jm, jd)
    onChange(isoOfDate(g))
    setOpen(false)
  }

  const pickToday = () => {
    const now = new Date()
    onChange(isoOfDate(now))
    const t = toJalali(now)
    setView({ jy: t.jy, jm: t.jm })
    setOpen(false)
  }

  const isToday = (jd: number) => today.jy === view.jy && today.jm === view.jm && today.jd === jd
  const isSelected = (jd: number) => (
    !!selJ && selJ.jy === view.jy && selJ.jm === view.jm && selJ.jd === jd
  )

  const display = selected
    ? `${faDigits(selJ!.jd)} ${JMONTHS[selJ!.jm - 1]} ${faDigits(selJ!.jy)}`
    : ''

  const cells = Array.from({ length: firstCol + monthLen }, (_, i) =>
    i < firstCol ? null : i - firstCol + 1)

  return (
    <div className="jdp-root" ref={rootRef}>
      <button
        type="button"
        id={id}
        className="input jdp-input"
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {display ? (
          <span className="jdp-value">{display}</span>
        ) : (
          <span className="jdp-placeholder">{placeholder}</span>
        )}
        <span className="jdp-actions">
          {display && (
            <span
              role="button"
              tabIndex={-1}
              className="jdp-clear"
              aria-label="پاک‌کردن تاریخ"
              onClick={(e) => { e.stopPropagation(); onChange(''); setOpen(false) }}
            >✕</span>
          )}
          <svg className="jdp-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </span>
      </button>

      {open && pos && createPortal(
        <div
          ref={popRef}
          className="jdp-pop"
          role="dialog"
          aria-label="تقویم شمسی"
          style={{ position: 'fixed', top: pos.top, right: pos.right, width: pos.width }}
        >
          <div className="jdp-head">
            <div className="jdp-nav">
              <button type="button" className="jdp-nav-btn" aria-label="سال قبل"
                      onClick={() => shiftYear(-1)}>⟪</button>
              <button type="button" className="jdp-nav-btn" aria-label="ماه قبل"
                      onClick={() => shiftMonth(-1)}>‹</button>
            </div>
            <div className="jdp-title">
              {JMONTHS[view.jm - 1]} {faDigits(view.jy)}
            </div>
            <div className="jdp-nav">
              <button type="button" className="jdp-nav-btn" aria-label="ماه بعد"
                      onClick={() => shiftMonth(1)}>›</button>
              <button type="button" className="jdp-nav-btn" aria-label="سال بعد"
                      onClick={() => shiftYear(1)}>⟫</button>
            </div>
          </div>
          <div className="jdp-grid" dir="rtl">
            {WEEK_COLS.map((w, i) => <div key={`w${i}`} className="jdp-week">{w}</div>)}
            {cells.map((jd, i) => (
              <div key={`c${i}`} className="jdp-cell">
                {jd !== null && (
                  <button
                    type="button"
                    className={`jdp-day${isToday(jd) ? ' today' : ''}${isSelected(jd) ? ' selected' : ''}`}
                    onClick={() => pickDay(jd)}
                    aria-pressed={isSelected(jd)}
                    aria-label={`${faDigits(jd)} ${JMONTHS[view.jm - 1]} ${faDigits(view.jy)}`}
                  >{faDigits(jd)}</button>
                )}
              </div>
            ))}
          </div>
          <div className="jdp-foot">
            <button type="button" className="jdp-foot-btn" onClick={pickToday}>امروز</button>
            <button type="button" className="jdp-foot-btn muted" onClick={() => { onChange(''); setOpen(false) }}>
              پاک‌کردن
            </button>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
