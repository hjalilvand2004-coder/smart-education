/* تزریق ویجت دستیار هوشمند «دانشگاه هوشمند من» (v3.11.0 — پرزنت مقطع v3.12.0)
 * ویجت وندرشده در public/msu-agent-widget.js (widget.js نسخهٔ 1.2.0 رسمی).
 * پیکربندی از مسیر /integration/msu-agent/widget-config می‌آید (دیتابیس > env >
 * پیش‌فرض) و یک‌بار در Layout فراخوانی می‌شود تا در همهٔ صفحات در دسترس باشد.
 * پس از ذخیرهٔ تنظیمات در پنل مدیریت، رخداد msu-agent-config-changed تزریق را
 * تازه می‌کند (حذف DOM قدیمی + بارگذاری مجدد اسکریپت).
 * مقطع تحصیلی دانشجو (v3.12.0) سلام اول و زیرعنوان ویجت را متناسب می‌سازد.
 */
import { api } from '../api'

export interface MsuWidgetConfig {
  enabled: boolean
  base_url: string
  origin: string
  accent: string
  accent2: string
  position: 'br' | 'bl'
  token_key: string
  token: string
  degree_level?: string
  degree_level_fa?: string
}

const SCRIPT_ID = 'msu-agent-widget-script'
const CHANGE_EVENT = 'msu-agent-config-changed'

/** سلام اول ویجت متناسب با مقطع تحصیلی دانشجو (v3.12.0) */
function greetingForDegree(fa: string | undefined): string {
  switch (fa) {
    case 'کاردانی':
      return 'سلام! دستیار هوشمند «دانشگاه هوشمند من» هستم؛ برای دورهٔ کاردانی همراه شما هستم — از درس‌ها، مهارت‌های کاربردی، کارآموزی صناعی و وضعیت مالی می‌پرسید و در هماهنگی با دانشجو۳۶۰ اقدام می‌کنم.'
    case 'کارشناسی ارشد':
      return 'سلام! دستیار هوشمند «دانشگاه هوشمند من» هستم؛ برای دورهٔ کارشناسی ارشد همراه شما هستم — از وضعیت درسی، دروس تخصصی، پروپوزال و پایان‌نامه، مقالات و کارآموزی می‌پرسید و در هماهنگی با دانشجو۳۶۰ اقدام می‌کنم.'
    case 'دکترا':
      return 'سلام! دستیار هوشمند «دانشگاه هوشمند من» هستم؛ برای دورهٔ دکترا همراه شما هستم — از وضعیت درسی، رساله، مقالات و داوری، آزمون جامع و کنفرانس‌ها می‌پرسید و در هماهنگی با دانشجو۳۶۰ اقدام می‌کنم.'
    default: // کارشناسی و پیش‌فرض
      return 'سلام! دستیار هوشمند «دانشگاه هوشمند من» هستم؛ آخرین وضعیت شما (درس‌ها، مهارت‌ها، کارآموزی، درخواست‌ها و مالی) را از هستهٔ عامل می‌پرسم و در هماهنگی با دانشجو۳۶۰ اقدام می‌کنم.'
  }
}

/** گوش‌دادن به تغییر تنظیمات — unsubscribe برمی‌گرداند */
export function onMsuAgentChange(cb: () => void): () => void {
  const h = () => cb()
  window.addEventListener(CHANGE_EVENT, h)
  return () => window.removeEventListener(CHANGE_EVENT, h)
}

/** رویداد تازه‌سازی — پس از ذخیرهٔ تنظیمات در پنل مدیریت صادر می‌شود */
export function notifyMsuAgentChanged(): void {
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

/** حذف کامل DOM و استایل ویجت پیش از بارگذاری مجدد */
function cleanupWidget(): void {
  document.getElementById(SCRIPT_ID)?.remove()
  document.getElementById(FIX_STYLE_ID)?.remove()
  document.querySelectorAll('.msu-fab, .msu-panel').forEach((n) => n.remove())
  document.querySelectorAll('style').forEach((st) => {
    if ((st.textContent || '').includes('.msu-fab')) st.remove()
  })
  try { delete (window as { MSUAgent?: unknown }).MSUAgent } catch { /* noop */ }
}

const FIX_STYLE_ID = 'msu-agent-position-fix'

/**
 * استایل مکمل جانمایی — v3.13.0: ویجت کمی بالاتر از دکمهٔ راهنمای صفحه می‌نشیند
 * تا با آن هم‌پوشانی نکند (راهنما پایین-چپ ۱۸px است؛ FAB به ۷۶px و پنل به ۱۴۶px
 * می‌رود و فقط در حالت پایین‌چپ اعمال می‌شود). با !important بر CSS وندرشدهٔ
 * widget.js غلبه می‌کند و در cleanupWidget پاک می‌شود.
 */
function appendPositionFix(): void {
  if (document.getElementById(FIX_STYLE_ID)) return
  const st = document.createElement('style')
  st.id = FIX_STYLE_ID
  st.textContent = [
    '.msu-fab.msu-bl{bottom:76px!important}',
    '.msu-panel.msu-bl{bottom:146px!important}',
  ].join('\n')
  document.head.appendChild(st)
}

/**
 * واکشی پیکربندی و تزریق ویجت — idempotent؛ خطا خاموش (ویجت اختیاری است و
 * نباید بقیهٔ سامانه را مختل کند). اگر enabled=false باشد حذف می‌کند.
 */
export async function injectMsuWidget(): Promise<void> {
  cleanupWidget()
  try {
    const cfg = await api.get<MsuWidgetConfig>('/integration/msu-agent/widget-config')
    if (!cfg?.enabled || !cfg.base_url) return
    if (cfg.token) {
      try { localStorage.setItem(cfg.token_key || 'msu_agent_token', cfg.token) } catch { /* noop */ }
    }
    appendPositionFix() // v3.13.0: بالاتر از دکمهٔ راهنمای صفحه
    const s = document.createElement('script')
    s.id = SCRIPT_ID
    s.src = '/msu-agent-widget.js' // وندرشده — هم‌مبدأ با خود سامانه
    s.async = true
    s.setAttribute('data-agent-url', cfg.base_url)
    s.setAttribute('data-origin', cfg.origin || 'student360')
    s.setAttribute('data-accent', cfg.accent || '#7c3aed')
    s.setAttribute('data-accent2', cfg.accent2 || '#5b21b6')
    s.setAttribute('data-position', cfg.position || 'bl') // v3.12.0: پایین‌چپ
    s.setAttribute('data-token-key', cfg.token_key || 'msu_agent_token')
    s.setAttribute('data-title', 'دانشگاه هوشمند من')
    s.setAttribute('data-subtitle', cfg.degree_level_fa
      ? `دستیار هوشمند دانشجو — مقطع ${cfg.degree_level_fa}`
      : 'دستیار هوشمند دانشجو — متصل به هستهٔ عامل')
    s.setAttribute('data-greeting', greetingForDegree(cfg.degree_level_fa))
    document.body.appendChild(s)
  } catch {
    /* پیکربندی در دسترس نیست — ویجت این نشست نمایش داده نمی‌شود */
  }
}
