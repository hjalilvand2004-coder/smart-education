# سامانه هوشمند آموزش و آزمون — Smart Education

سامانه تولید محتوای آموزشی هوشمند، آزمون چهارگزینه‌ای و تشریحی — با
**احراز هویت و مدیریت نقش‌ها**، **گزارش‌سازی چهارفرمتی گرافیکی**،
**یکپارچگی سرویس با سامانه برنامه‌ریزی درسی** و **سرویس‌دهی سرفصل‌ها به سایر سامانه‌ها**.

## 🔐 حساب‌های کاربری و نقش‌ها

| نقش | ثبت‌نام | دسترسی |
|-----|---------|--------|
| مدیر سامانه (admin) | بوت‌استرپ اولیه: `admin / admin123` | همهٔ بخش‌ها + مدیریت کاربران |
| مدیرگروه | نیازمند تایید مدیر سامانه | تایید/رد استاد و دانشجو + مدیریت کاربران محدود |
| استاد | نیازمند تایید مدیر سامانه یا مدیرگروه | تولید محتوا و آزمون |
| دانشجو | فعال‌سازی خودکار | شرکت در آزمون و مشاهده محتوا |

نقاط اتصال احراز هویت:
- `POST /api/auth/register` — ثبت‌نام (دانشجو فعال می‌شود؛ استاد/مدیرگروه در انتظار تایید)
- `POST /api/auth/login` — ورود و دریافت توکن (Bearer)
- `GET  /api/auth/me` — اطلاعات کاربر جاری
- `POST /api/auth/change-password` — تغییر رمز عبور
- `GET/POST/PUT/DELETE /api/users/...` — مدیریت کاربران (فقط مدیر سامانه و مدیرگروه)
- تولید محتوا و آزمون با هوش مصنوعی نیازمند ورود است.

> ⚠️ پس از اولین ورود، رمز حساب مدیر را از منوی داشبورد تغییر دهید.

## 🌐 آدرس‌های رسمی سرویس‌ها

| سرویس | آدرس |
|-------|------|
| این سامانه (آموزش) | `http://188.212.96.235:8084` |
| سرویس برنامه‌ریزی درسی (لیست درس‌ها) | `http://188.212.96.235:8083` |

## ✨ امکانات

- 🎓 **محتوای آموزشی هوشمند** — تولید محتوا با هوش مصنوعی برای هر سرفصل درس
- 📝 **آزمون‌ساز** — آزمون چهارگزینه‌ای و تشریحی به‌همراه تصحیح و کارنامه
- 📊 **استودیو گزارش‌ها (جدید)** — خروجی گرافیکی از کل داده‌های سامانه در ۴ فرمت:
  | فرمت | ویژگی‌ها |
  |------|----------|
  | 🌐 HTML | تک‌فایلی، نمودار SVG، کارت‌های KPI، قابل چاپ |
  | 📽 PowerPoint | ارائه ۱۶:۹، جلد گرادیانی، نمودار بومی قابل ویرایش |
  | 📄 PDF | فونت وزیرمتن، جلد رنگی، نمودار و جدول‌های راه‌راه، آماده چاپ |
  | 📝 Word | سند راست‌به‌چپ قابل ویرایش با قالب سازمانی |
- 🔗 **یکپارچگی سرویس‌ها** — خواندن فهرست درس‌ها از
  [سامانه هوشمند برنامه‌ریزی درسی](https://github.com/hjalilvand2004-coder/university-scheduler):
  - `GET  /api/integration/scheduler/status` — بررسی سلامت سرویس بیرونی
  - `GET  /api/integration/scheduler/courses` — مشاهده زنده دروس سرویس
  - `POST /api/integration/scheduler/sync` — همگام‌سازی دروس در دیتابیس محلی
  - آدرس سرویس با متغیر محیطی `SCHEDULER_BASE_URL` (پیش‌فرض `http://188.212.96.235:8083`)
- ⇪ **سرویس‌دهی به سایر سامانه‌ها (جدید)** — سرفصل‌های دروس و محتوای آن‌ها
  به‌صورت سرویس در اختیار سامانه برنامه‌ریزی درسی و سایر سامانه‌ها قرار می‌گیرد:

  | سرویس | نقطهٔ اتصال | توضیح |
  |-------|-------------|-------|
  | شناسنامهٔ سرویس | `GET /api/services/health` | کشف سرویس و قابلیت‌ها |
  | فهرست درس‌ها | `GET /api/services/courses` | درس‌ها + تعداد سرفصل/محتوا |
  | فهرست سرفصل‌ها | `GET /api/services/topics?course_id=` | سبک، با صفحه‌بندی |
  | جزئیات سرفصل | `GET /api/services/topics/{id}` | سرفصل + محتوا |
  | محتوای کامل سرفصل | `GET /api/services/topics/{id}/content` | متن کامل محتوا |
  | بستهٔ کامل | `GET /api/services/export/topics` | همهٔ سرفصل‌ها + محتوا در یک JSON |
  | ارسال به سامانهٔ دیگر | `POST /api/services/push/topics` | Push به `{target}/api/ingest/topics` |

  **قرارداد دریافت (Ingest Contract)** — سامانهٔ گیرنده باید این مسیر را پیاده‌سازی کند:

  ```
  POST {target}/api/ingest/topics
  Content-Type: application/json
  X-Source-System: smart-education

  {
    "source": "smart-education",
    "generated_at": "2026-11-01T10:00:00Z",
    "total_topics": 12,
    "topics": [
      {
        "course_id": 1,
        "course_title": "پایگاه داده پیشرفته",
        "topic_id": 5,
        "topic_title": "طراحی و نرمال‌سازی",
        "description": "...",
        "session_minute": 50,
        "sort_order": 1,
        "contents": [
          {"content_id": 9, "title": "...", "body": "...", "source": "ai"}
        ]
      }
    ]
  }
  ```

## 🚀 اجرای سریع (نسخهٔ قابل حمل — بدون نیاز به نصب)

بدون نیاز به Python، PyCharm یا Node.js:

1. از بخش [Releases](../../releases) فایل `SmartEducation-Portable-win64.zip` را دانلود کنید
2. استخراج کنید و `SmartEducation.exe` را اجرا کنید
3. مرورگر به‌صورت خودکار باز می‌شود (`http://127.0.0.1:8084`)
4. استودیو گزارش‌ها: `http://127.0.0.1:8084/reports-page`

> 💡 سامانه روی همهٔ کارت‌های شبکه گوش می‌دهد؛ از طریق IP سرور هم در دسترس است:
> `http://188.212.96.235:8084` (پورت 8084 باید در فایروال ویندوز باز باشد).

> 💡 لیست درس‌ها به‌صورت زنده از سرویس رسمی `http://188.212.96.235:8083`
> خوانده می‌شود — سرویس‌دهی سرفصل‌ها به سایر سامانه‌ها هم فعال است.

## 🛠 اجرای توسعه (Development)

```bash
# بک‌اند
cd backend
pip install -r requirements.txt
python run.py          # http://127.0.0.1:8000

# فرانت‌اند
cd frontend
npm install
npm run dev            # http://127.0.0.1:5173
```

سرویس بیرونی (اختیاری، برای لیست درس‌ها):

```bash
git clone https://github.com/hjalilvand2004-coder/university-scheduler.git
cd university-scheduler && python main.py   # http://127.0.0.1:8000
```

## 📦 ساخت نسخهٔ قابل حمل

به‌صورت خودکار با GitHub Actions:

```bash
git tag v1.0.1 && git push origin v1.0.1
```

Workflow ‏`.github/workflows/build-portable.yml` خروجی
`SmartEducation-Portable-win64.zip` را ساخته و در Releases منتشر می‌کند.

## 🧾 API گزارش‌ها

```
GET /api/reports/preview            → دادهٔ خام گزارش
GET /api/reports/export/html        → گزارش HTML
GET /api/reports/export/pptx        → گزارش PowerPoint
GET /api/reports/export/pdf         → گزارش PDF
GET /api/reports/export/docx        → گزارش Word
```

## 🔌 سرویس‌دهی سرفصل‌ها به سایر سامانه‌ها

مستندات تعاملی و قابل آزمایش: `http://188.212.96.235:8084/docs`
(گروه `services`) و صفحهٔ استودیو گزارش‌ها (`/reports-page`).

مثال — خواندن سرفصل‌های یک درس توسط سامانهٔ دیگر:

```bash
curl "http://188.212.96.235:8084/api/services/topics?course_id=1"
```

مثال — ارسال سرفصل‌ها به یک سامانهٔ گیرنده:

```bash
curl -X POST "http://188.212.96.235:8084/api/services/push/topics" \
  -H "Content-Type: application/json" \
  -d '{"target_base_url": "http://188.212.96.235:8083", "include_content": true}'
```
