# دانشجو۳۶۰ — سامانه سرویس‌های یادگیری هوشمند

پیاده‌سازی مرجع (فاز یک MVP + اسکلت فاز دو) بر اساس سند تشریح نیازمندی‌ها:
**FastAPI ماژولار + React + PostgreSQL** با هستهٔ «سرفصل مصوب، گراف مفاهیم،
محتوای ساختاریافته تأییدشده و شواهد یادگیری» — نه صرفاً یک چت‌بات.

```
هستهٔ تصمیم:  AI پیش‌نویس می‌سازد ← استاد تأیید می‌کند ← شواهد معتبر مبنای شخصی‌سازی است
```

## ساختار مخزن

```
student360/
├── backend/            FastAPI ماژولار (app/core, app/models, app/services, app/api, app/ai, app/workers)
│   ├── tests/          ۵۵ تست pytest — نگاشت مستقیم به معیارهای پذیرش AC-01..AC-14
│   ├── scripts/        init_db.py و seed_demo.py (دموی کامل با خط تولید واقعی)
│   └── alembic/        مهاجرت‌ها (برای PostgreSQL)
├── frontend/           React 18 + TypeScript + Vite، فارسی RTL، فونت Vazirmatn
├── docs/               api_contract.md و openapi.json (قرارداد API)
├── sample-outputs/     خروجی‌های نمونه فارسی: PDF / PPTX / HTML / DOCX
├── docker/             Dockerfile بک‌اند/فرانت‌اند و nginx
└── docker-compose.yml  PostgreSQL + Redis + بک‌اند + فرانت‌اند
```

## اجرای سریع (توسعه بدون Docker)

```bash
# بک‌اند (Python 3.12)
cd backend
pip install -r requirements.txt
python scripts/init_db.py          # ساخت جداول (SQLite توسعه)
python scripts/seed_demo.py        # دموی کامل: تولید محتوا، سؤال، آزمون، تسلط، گفتگو
uvicorn app.main:app --reload      # مستندات: http://localhost:8000/api/docs

# فرانت‌اند (Node 20+)
cd ../frontend
npm install
npm run dev                        # http://localhost:5173 (پروکسی /api به 8000)
```

## اجرا با Docker

```bash
cp .env.example .env   # مقدارها را تنظیم کنید
docker compose up -d --build
# فرانت‌اند: http://localhost:8080   |   API: http://localhost:8000/api/docs
```

## حساب‌های دمو (رمز همه: `Pass1234!`)

| کاربر | نقش |
|---|---|
| `prof.rezaei` | استاد (استودیوی محتوا، تأیید، انتشار) |
| `ta.karimi` | دستیار آموزشی (پیش‌نویس بدون انتشار) |
| `student.sara` | دانشجو (مطالعه، آزمون، استاد هوشمند، برنامه مطالعه) |
| `student.amir` | دانشجو |
| `edu.admin` | مدیر آموزشی (نسخه‌های مصوب، حسابرسی) |
| `quality.expert` | کارشناس کیفیت محتوا |
| `tech.admin` | مدیر فنی (پایش AI) |

داده دمو با **همان سرویس‌های واقعی سامانه** ساخته می‌شود: سرفصل وارد و تأیید
می‌شود، مفاهیم گراف ساخته می‌شوند، محتوا با AI تولید و کنترل کیفیت و **منتشر**
می‌شود، ۱۲ سؤال تأیید می‌شوند، دانشجو آزمون و تمرین تطبیقی می‌دهد، تخمین تسلط و
فرضیه‌های تشخیصی ساخته می‌شوند، برنامه مطالعه و مرور فاصله‌دار فعال می‌شود و
گفتگو با استاد هوشمند (با ارجاع به منابع مجاز) انجام می‌شود.

## وصل‌کردن مدل واقعی

تولیدها پشت **AI Gateway** (`app/ai/gateway.py`) هستند؛ با این تنظیم مدل خارجی
جایگزین مولد قطعی توسعه (mock) می‌شود **بدون تغییر هیچ سرویسی**:

```env
S360_AI_PROVIDER=openai_compat
S360_AI_BASE_URL=https://<مدل-سازگار-OpenAI>/v1
S360_AI_API_KEY=...
S360_AI_MODEL=...
```

هر فراخوانی مدل در جدول `ai_runs` با نسخه Prompt/مدل و مصرف ثبت می‌شود و خروجی
قبل از استفاده با Pydantic اعتبارسنجی می‌شود.

## نگاشت معیارهای پذیرش به تست‌ها

| AC | معیار | تست |
|---|---|---|
| AC-01 | تولید فقط با نسخه مشخص سرفصل | `test_content_pipeline.py::test_generation_requires_approved_syllabus` |
| AC-02 | تأیید انسانی ساختار استخراج‌شده | `test_syllabus.py::test_import_creates_draft_needing_approval` |
| AC-03 | بازتولید یک بخش بدون ازبین‌رفتن سایر ویرایش‌ها | `test_content_pipeline.py::test_block_edit_and_selective_regeneration` |
| AC-04 | PDF/PPTX فارسی، فرمول و جدول صحیح | `test_exports.py::test_pdf_export_persian`, `test_pptx_export_editable` (+ بررسی بصری در sample-outputs) |
| AC-05 | انتشار فقط پس از تأیید مجاز | `test_auth_rbac.py::test_student_cannot_publish_content`, `test_content_pipeline.py::test_publish_gate_and_student_visibility` |
| AC-06 | تغییر سرفصل پنهان تغییر ایجاد نکند + گزارش اثر | `test_syllabus.py::test_syllabus_diff_reports_changes`، نسخه‌بندی محتوا |
| AC-07 | ردیابی پاسخ و نسخه سؤال | `test_assessment.py::test_response_version_fixed_and_traceable` |
| AC-08 | نبود شواهد ≠ ضعف قطعی | `test_mastery.py::test_no_evidence_is_unknown_not_weak` |
| AC-09 | کلید امتحان خارج از RAG/گفتگو | `test_tutor.py::test_exam_key_not_retrieved_by_default`, `test_tutor_never_cites_exam_key` |
| AC-10 | نمره تشریحی قابل بررسی/اصلاح/اعتراض | `test_assessment.py::test_essay_ai_suggestion_then_human_final_and_dispute` |
| AC-11 | HTML/فایل خروجی بدون کد ناامن | `test_exports.py::test_html_export_safe_and_rtl` (CSP + escape) |
| AC-12 | خرابی AI مطالعه را متوقف نکند | `test_planning_ops.py::test_ai_failure_fallback_for_syllabus_import` + حالت جایگزین در همه سرویس‌ها |
| AC-13 | اجرای مجدد Job تکراری نسازد | `test_collab_ops.py::test_idempotency_same_key_same_job`, `test_export_idempotency` |
| AC-14 | بازیابی دیتابیس/فایل | پشتیبان‌گیری pgdata + volume در docker-compose؛ بازیابی در محیط آزمون مستند است |

اجرا: `cd backend && python -m pytest tests/ -q`

## نکات معماری

- **مونولیت ماژولار**: هر دامنه سرویس و مسیر مستقل دارد؛ تفکیک به Workerهای
  Celery فقط با جابه‌جایی `app/workers` انجام می‌شود (ساختار آماده).
- **نسخه‌بندی محتوا**: ویرایش نسخه منتشرشده، پیش‌نویس جدید می‌سازد؛ هیچ ویرایشی
  سابقه منتشرشده را عوض نمی‌کند. قفل بهینه با `expected_revision` (پاسخ 409).
- **دسترسی**: نقش سراسری + نقش درسی + ثبت‌نام؛ حسابرسی انتشار/نمره/مجوز در
  `audit_logs`؛ رویدادهای یکپارچه‌سازی در `outbox_events`.
- **RAG**: قطعه‌بندی معنایی + بردار هش‌محور در توسعه؛ در استقرار ستون pgvector
  جایگزین می‌شود (فیلتر مجوز پیش از بازیابی، همیشه).
- **زمان‌ها** در UTC ذخیره و به‌صورت ISO-8601 ارائه می‌شوند؛ نمایش محلی در UI.
