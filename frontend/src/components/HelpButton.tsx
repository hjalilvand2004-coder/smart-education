import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { helpForPath } from '../help/helpContent'
import type { HelpEntry } from '../help/helpContent'

/**
 * HelpButton — دکمهٔ راهنمای شناور در همهٔ صفحات.
 * محتوای راهنما به‌صورت خودکار از مسیر فعلی انتخاب می‌شود؛
 * روی هر صفحه توضیح همان صفحه و کارکرد فرم‌هایش را باز می‌کند.
 */
export default function HelpButton() {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [entry, setEntry] = useState<HelpEntry | null>(null)

  useEffect(() => {
    setEntry(helpForPath(pathname))
    setOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  if (!entry) return null

  return (
    <>
      <button
        type="button"
        className={`help-fab${open ? ' on' : ''}`}
        onClick={() => setOpen(true)}
        aria-label="راهنمای این صفحه"
        aria-haspopup="dialog"
        title="راهنمای این صفحه — چه کار می‌کند و چطور؟"
      >
        <span className="help-fab-q">؟</span>
        <span className="help-fab-label">راهنمای این صفحه</span>
      </button>

      {open && (
        <div className="help-overlay" onClick={() => setOpen(false)}>
          <div
            className="help-modal"
            role="dialog"
            aria-modal="true"
            aria-label={`راهنما — ${entry.title}`}
            onClick={(e) => e.stopPropagation()}
          >
            <header className="help-head">
              <span className="help-ico" aria-hidden="true">{entry.icon}</span>
              <div>
                <h3>راهنما — {entry.title}</h3>
                <p>کارکرد این صفحه و فرم‌هایش</p>
              </div>
              <button type="button" className="help-close" onClick={() => setOpen(false)} aria-label="بستن راهنما">✕</button>
            </header>

            <div className="help-body">
              <p className="help-intro">{entry.intro}</p>
              {entry.sections.map((s) => (
                <section key={s.heading} className="help-section">
                  <h4>{s.heading}</h4>
                  <ul>
                    {s.items.map((it, i) => (
                      <li key={i}>{it}</li>
                    ))}
                  </ul>
                </section>
              ))}
              {entry.tip && <div className="help-tip">💡 {entry.tip}</div>}
            </div>

            <footer className="help-foot">
              <span>پرسش دیگری دارید؟ از «استاد هوشمند» درس بپرسید یا با مدیر آموزشی تماس بگیرید.</span>
            </footer>
          </div>
        </div>
      )}
    </>
  )
}
