import { useEffect } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../auth'
import HelpButton from '../components/HelpButton'

const FEATURES = [
  {
    icon: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </>
    ),
    title: 'استخراج خودکار سرفصل',
    desc: 'سرفصل درس را می‌دهید؛ سامانه خودش موضوع‌ها، ترتیب و پیش‌نیازها را می‌کشد بیرون و نسخه‌های مصوب را مدیریت می‌کند.',
  },
  {
    icon: (
      <>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
      </>
    ),
    title: 'تولید محتوای هوشمند',
    desc: 'برای هر سرفصل، محتوای آموزشی بر اساس سطح دانشجو و الگوی تعامل دلخواه او ساخته می‌شود — نه متن‌های یکسان برای همه.',
  },
  {
    icon: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
    title: 'استاد هوشمند ۲۴/۷',
    desc: 'هر جا گیر کردی، «اینجا گیر کردم» را بزن؛ استاد هوشمند با نردبان راهنمایی، بدون لو دادن پاسخ، خودت را به جواب می‌رساند.',
  },
  {
    icon: (
      <>
        <circle cx="6" cy="6" r="3" />
        <circle cx="18" cy="8" r="3" />
        <circle cx="11" cy="18" r="3" />
        <path d="M8.5 7.2 15 7.8M7.5 8.6l2.4 6.6M14 10l-1.7 5.2" />
      </>
    ),
    title: 'نقشه مفاهیم دوحالته',
    desc: 'مفاهیم درس را به‌صورت گراف تعاملی ببین؛ حالت تحلیلی برای درک ساختار، حالت رصدی برای دیدن میزان تسلط خودت.',
  },
  {
    icon: (
      <>
        <path d="M18 20V10" />
        <path d="M12 20V4" />
        <path d="M6 20v-6" />
      </>
    ),
    title: 'رصدخانه دانش',
    desc: 'با گرافیک سه‌لایه، وضعیت یادگیری‌ات را در یک نگاه ببین: چه می‌دانی، چه نمی‌دانی، و قدم بعدی چیست.',
  },
  {
    icon: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    title: 'آمادگی آزمون صادقانه',
    desc: 'آزمون کوتاه تشخیصی، تحلیل شکاف دانش، تمرین جبرانی هدفمند و شبیه‌سازی آزمون واقعی با زمان‌سنج.',
  },
  {
    icon: (
      <>
        <circle cx="9" cy="7" r="3" />
        <path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
        <path d="M16 3.5a3 3 0 0 1 0 7M19 21v-2a4 4 0 0 0-2-3.5" />
      </>
    ),
    title: 'یادگیری همیارانه',
    desc: 'از هم‌کلاسی‌ها یاد بگیر: «به من یاد بده» با روبرک هوشمند، و رشد مهارت توضیح‌دادن مثل یک استاد واقعی.',
  },
  {
    icon: (
      <>
        <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1 1 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      </>
    ),
    title: 'امنیت و حاکمیت داده',
    desc: 'توکن کوتاه‌عمر با refresh، بودجه‌گذاری سه‌لایه برای AI، لاگ ممیزی کامل و کنترل دسترسی نقش‌محور.',
  },
]

const STATS = [
  { num: '۱۶+', label: 'سرویس یادگیری هوشمند' },
  { num: '۵/۱۵/۳۰', label: 'جلسه یادگیری دلخواه' },
  { num: '۱۲۸', label: 'تست خودکار سبز' },
  { num: '۲۴/۷', label: 'استاد هوشمند کنارت' },
]

/** لندینگ رویایی: اول زیبایی سایت، بعد ورود — کاربر احرازشده مستقیم وارد می‌شود. */
export default function Landing() {
  const { user, loading } = useAuth()

  useEffect(() => {
    document.title = 'دانشجو۳۶۰ — سامانه یکپارچه یادگیری هوشمند'
  }, [])

  // کاربر احرازشده (از جمله مسیر SSO) لندینگ را نمی‌بیند — ورود یکپارچه مستقیم
  if (!loading && user) return <Navigate to="/today" replace />

  return (
    <div className="landing-page">
      <div className="aurora" aria-hidden="true">
        <i className="b1" />
        <i className="b2" />
        <i className="b3" />
        <i className="b4" />
      </div>
      <div className="stars" aria-hidden="true">
        {Array.from({ length: 22 }, (_, i) => (
          <span
            key={i}
            className="star"
            style={{
              top: `${(i * 29 + 11) % 96}%`,
              insetInlineStart: `${(i * 47 + 5) % 97}%`,
              animationDelay: `${(i % 8) * 0.45}s`,
            }}
          />
        ))}
      </div>

      <header className="landing-nav">
        <div className="landing-nav-inner">
          <div className="brand">
            <span className="brand-mark">360</span>
            <span>
              دانشجو۳۶۰
              <span className="brand-sub">رصدخانه یادگیری هوشمند</span>
            </span>
          </div>
          <nav className="landing-links" aria-label="لندینگ">
            <a href="#features">امکانات</a>
            <a href="#how">مسیر یادگیری</a>
            <a href="#stats">سامانه در یک نگاه</a>
          </nav>
          <Link to="/login" className="btn btn-primary btn-sm landing-cta">
            ورود به سامانه
          </Link>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <span className="landing-badge">✨ سامانه یکپارچه یادگیری هوشمند دانشگاهی</span>
          <h1 className="landing-title">
            یادگیری، به زیباییِ <span className="grad-text">یک رؤیا</span>
          </h1>
          <p className="landing-lead">
            سرفصل‌ها خودکار استخراج می‌شوند، محتوا برای خودِ تو ساخته می‌شود، استاد هوشمند
            همیشه کنارت است و «رصدخانه دانش» هر روز نشان می‌دهد قدم بعدی یادگیری‌ات کجاست.
          </p>
          <div className="landing-cta-row">
            <Link to="/login" className="btn btn-primary btn-lg">شروع یادگیری</Link>
            <a href="#features" className="btn btn-lg landing-ghost-btn">کشف امکانات</a>
          </div>

          <div className="landing-mock" aria-hidden="true">
            <div className="mock-card mock-1">
              <div className="mock-kicker">امروزِ من</div>
              <div className="mock-line" />
              <div className="mock-line short" />
              <div className="mock-pill">پیشنهاد اصلی: فصل ۳ — شبکه‌های عصبی</div>
            </div>
            <div className="mock-card mock-2">
              <div className="mock-kicker">رصدخانه دانش</div>
              <div className="mock-dots">
                <i /><i /><i /><i /><i /><i />
              </div>
              <div className="mock-pill accent">تسلط فصل ۲: ۷۲٪ ↑</div>
            </div>
            <div className="mock-card mock-3">
              <div className="mock-kicker">استاد هوشمند</div>
              <div className="mock-line" />
              <div className="mock-line short" />
              <div className="mock-pill">نردبان راهنمایی فعال 🪜</div>
            </div>
          </div>
        </section>

        <section id="features" className="landing-section">
          <h2 className="landing-h2">هر چیزی که یادگیری لازم دارد، یک‌جا</h2>
          <p className="landing-h2-sub">
            از استخراج سرفصل تا رصد تسلط مفهومی — مجموعه‌ای یکپارچه برای دانشجو و استاد.
          </p>
          <div className="landing-features">
            {FEATURES.map((f) => (
              <article key={f.title} className="feature-card">
                <span className="feature-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    {f.icon}
                  </svg>
                </span>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="how" className="landing-section">
          <h2 className="landing-h2">مسیر یادگیری در سه قدم</h2>
          <div className="landing-steps">
            <div className="step-card">
              <span className="step-num">۱</span>
              <h3>درس‌هایت را انتخاب کن</h3>
              <p>درس‌های ترم خودت را ببین، وارد فضای درس شو و سرفصل مصوب را مرور کن.</p>
            </div>
            <div className="step-card">
              <span className="step-num">۲</span>
              <h3>جلسه یادگیری را بساز</h3>
              <p>۵، ۱۵ یا ۳۰ دقیقه وقت داری؟ سامانه همین حالا بهترین ترکیب مطالعه را می‌چیند.</p>
            </div>
            <div className="step-card">
              <span className="step-num">۳</span>
              <h3>رصد کن و جلو برو</h3>
              <p>رصدخانه دانش، تسلط مفهومی و کلینیک خطا نشان می‌دهند کجا هستی و بعدش چی.</p>
            </div>
          </div>
        </section>

        <section id="stats" className="landing-section">
          <div className="landing-stats">
            {STATS.map((s) => (
              <div key={s.label} className="stat-tile">
                <div className="stat-num">{s.num}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="landing-final">
          <h2 className="landing-h2">آماده‌ای سفر یادگیری‌ات را رویایی کنی؟</h2>
          <div className="landing-cta-row center">
            <Link to="/login" className="btn btn-primary btn-lg">ورود به سامانه</Link>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="brand">
          <span className="brand-mark">360</span>
          <span>دانشجو۳۶۰</span>
        </div>
        <div className="landing-footer-note">
          سامانه یکپارچه یادگیری هوشمند — نسخه ۳.۸.۰ · ورود یکگانه با پرتال مرکزی (SSO)
        </div>
      </footer>
      <HelpButton />
    </div>
  )
}
