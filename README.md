# Smart Learning 360 — سامانه یکپارچه یادگیری هوشمند

ادغام کامل «سامانه هوشمند آموزش و آزمون» و «سرویس‌های یادگیری هوشمند دانشجو۳۶۰» در **یک سامانه یکپارچه**:
تولید محتوای آموزشی با AI متناسب با هر سرفصل، آزمون‌ساز چندنوعی، استاد هوشمند، نقشه مفاهیم و تسلط،
برنامه مطالعه، **ورود یکگانه SSO/OIDC**، گردش‌کار ثبت‌نام و تایید، گزارش جامع چهارفرمتی گرافیکی،
سرویس‌دهی سرفصل‌ها به سایر سامانه‌ها و یکپارچه‌سازی با **برنامه‌یار۳۶۰**.

- بک‌اند: FastAPI + SQLAlchemy + SQLite/PostgreSQL — فرانت‌اند: React 18 + Vite (فارسی، RTL، بدون فریم‌ورک CSS)
- **تم «رویایی» v3 — نسخه ۲.۹.۰**: پس‌زمینه شفق قطبی متحرک، کارت‌های شیشه‌گری با حاشیه گرادیانی، دکمه‌های درخشان با افکت Shine، ستاره‌های چشمک‌زن و پانل قهرمان در صفحه ورود، انیمیشن‌های نرم با احترام به `prefers-reduced-motion`
- **پکیج پرتیبل کاملاً مستقل (v2.9.0)**: پایتون 3.12 embed شده + **تمام وابستگی‌های اجرایی به‌صورت wheels ویندوزی cp312** داخل `Lib\site-packages` (FastAPI، SQLAlchemy، pydantic-settings، Jinja2، گزارش‌سازهای DOCX/PPTX/PDF، matplotlib و…) — روی سیستمی که **نه پایتون دارد نه PyCharm** فقط با دابل‌کلیک `run.bat` اجرا می‌شود؛ `run.bat` فقط از پایتون داخلی پکیج استفاده می‌کند و `PYTHONHOME/PYTHONPATH` سیستم را خنثی می‌کند
- تست‌ها: **۷۷ تست سبز** (احراز هویت، RBAC، محتوا، آزمون، SSO، گزارش، سرویس‌ها، مهاجرت legacy)

## 🚀 اجرای سریع (نسخه پرتیبل — بدون نصب پایتون و بدون PyCharm)

از [Releases](../../releases) فایل `SmartLearning-360-Portable-win64-v2.9.0.zip` را بگیرید:
۱) Extract کامل ZIP ۲) دوبار کلیک روی `run.bat` ۳) مرورگر خودکار روی `http://localhost:8000`.
هیچ نصب پیش‌نیازی لازم نیست؛ جزئیات و عیب‌یابی در `README-PORTABLE.txt` داخل پکیج.

حساب‌های دمو (رمز همه `Pass1234!`): `prof.rezaei` (استاد) · `student.sara` (دانشجو) · `edu.admin` (مدیر آموزشی).

## 🔐 ورود یکگانه (SSO)

پرتال مرکزی «دانشجویار۳۶۰» روی `http://188.212.96.235:8086` یک **OIDC Provider** است (RS256 + PKCE S256).
برای اتصال این سامانه:

1. در پرتال SSO برای این سامانه یک ردیف ثبت کنید (مثل `tahsilyar360`):
   کلید سامانه = `learning360`، نام = «سامانه یکپارچه یادگیری هوشمند»،
   Client ID = مثلا `learning360`، **آدرس ورود (نقطه شروع جریان OIDC)** = `http://<host>:8000/api/v1/auth/sso/login`
2. در `run.bat` (یا env سرور) تنظیم کنید:
   `S360_SSO_CLIENT_ID`, `S360_SSO_CLIENT_SECRET`, `S360_SSO_REDIRECT_URI=http://<host>:8000/api/v1/auth/sso/callback`,
   `S360_SSO_FRONTEND_BASE=http://<host>:8000`
3. صفحه ورود دکمه «ورود یکگانه با پرتال مرکزی SSO» را نشان می‌دهد؛ ورود اول به‌صورت خودکار حساب می‌سازد (نقش دانشجو؛ مدیر می‌تواند نقش را ارتقا دهد).

جریان: `GET /api/v1/auth/sso/login` → پرتال → `GET /api/v1/auth/sso/callback` → تبادل code + اعتبارسنجی id_token با JWKS → بلیت یک‌بارمصرف → `POST /api/v1/auth/sso/exchange` → توکن سامانه (توکن هرگز در URL نمی‌ماند).

## 📝 ثبت‌نام و گردش‌کار تایید

- `POST /api/v1/auth/register` — دانشجو فعال می‌شود؛ استاد/مدیرگروه «در انتظار تایید».
- پنل مدیریت (`/admin`): تایید/رد، فهرست و جستجوی کاربران، تغییر نقش، بازنشانی رمز، فعال/غیرفعال‌سازی (`/api/v1/users/...`).

## 📊 گزارش جامع چهارفرمتی

`GET /api/v1/reports/summary` (JSON) · `GET /api/v1/reports/preview` (HTML) · `GET /api/v1/reports/export/{pdf|docx|html|pptx}`
— نمودارهای فارسی matplotlib (فونت وزیرمتن)، اعداد فارسی؛ صفحه «گزارش‌ها» در UI با دانلود مستقیم.

## 🌐 سرویس‌دهی به سایر سامانه‌ها

با توکن اختیاری (`S360_SERVICE_TOKEN`، هدر `X-Service-Token`):
`GET /services/health` · `/services/courses` · `/services/topics?course_code=` · `/services/topics/{id}` · `/services/topics/{id}/content` · `/services/export/topics`

## 🔗 یکپارچه‌سازی با برنامه‌یار۳۶۰

واکشی «درس‌های یکتا» از `http://188.212.96.235:8083` (در صورت نیاز با نام‌کاربری/رمز آن سامانه)،
فرم اطلاعات درس پیش‌پرشده، ثبت سرفصل‌ها و ورود به سامانه — صفحه «برنامه‌یار۳۶۰».

## 🧠 قابلیت‌های یادگیری

استودیوی محتوا با بلوک‌های ساختاریافته + کنترل کیفیت (پوشش اهداف) + بررسی + انتشار (متناسب با سرفصل انتخابی) ·
بانک سوال با ۱۰ نوع سوال و بازبینی · آزمون‌ساز و جزوه‌نامه · استاد هوشمند با ارجاع به منابع ·
نقشه مفاهیم با پررنگ‌شدن پیش‌نیازها · تسلط مفهومی و برنامه مطالعه روزانه · ردپای حسابرسی و آمار مصرف AI.

## 🗂 مهاجرت از سامانه قبلی «آموزش هوشمند» (فایل پیوست)

داده‌های واقعی فایل پیوست — **۲ درس (مهندسی نرم‌افزار و ابزارهای توسعه: ۵۲ جلسه/۶ فصل، داده‌کاوی: ۴۴ جلسه/۱۰ فصل)،
۹۶ سرفصل جلسه‌ای، ۸ محتوای تولیدشده به ازای سرفصل و لاگ مصرف AI** — با یک دستور وارد سامانه یکپارچه می‌شود:

```bash
cd backend
python scripts/import_legacy_education.py --db legacy/education.db
```

نگاشت: فصل‌ها → `CHAPTER`، نکته‌های جلسه‌ای → `TOPIC` با `suggested_hours` از مدت جلسه؛
محتواها → سند و نسخه منتشرشده با بلوک‌های ساختاریافته؛ لاگ AI → `AIRun` با provider/model/latency.
اسکریپت idempotent است و در بسته پرتیبل هم (کنار `run.bat`) پشتیبانی می‌شود.

## 🛠 توسعه

```bash
cd backend && pip install -r requirements.txt
python scripts/init_db.py && python scripts/seed_demo.py
python scripts/import_legacy_education.py --db legacy/education.db   # اختیاری: داده‌های سامانه قبلی
uvicorn app.main:app --reload          # http://localhost:8000
cd ../frontend && npm install && npm run dev
cd backend && pytest -q                # 77 tests
```

استقرار با PostgreSQL: `docker-compose up` (سرویس‌های api + db + web).
