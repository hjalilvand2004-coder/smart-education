# یادداشت انتشار v3.4.0 — یکپارچگی کامل پایه‌یار۳۶۰ طبق سند فنی اتصال

## خلاصه

این نسخه کلاینت پایه‌یار۳۶۰ را با **قرارداد کامل «سند فنی اتصال»** هم‌تراز می‌کند: احراز
OAuth2 client_credentials، هدرهای `X-Correlation-ID` / `Idempotency-Key` / `If-Match`، کش
ETag با پاسخ 304، retry نمایی روی 502/503/504، **دامنه‌های گسترش‌یافته** (اساتید، کلاس‌ها،
گروه‌های آموزشی، مجموعه‌های مرجع)، **زمان‌بند خودکار هر ۳۰ دقیقه** (معادل cron سند) و
**مصرف‌کننده رویدادهای RabbitMQ** با صف اختصاصی، DLQ و پردازش idempotent با جدول inbox.

## قرارداد سند فنی — پوشش مورد‌به‌مورد

| الزام سند | پیاده‌سازی |
|---|---|
| OAuth2 client_credentials روی `:8086/oauth/token` (client_id `smart-learning`، scope `masterdata.read`) | `_get_token` با کش توکن تا ۶۰ ثانیه پیش از انقضا؛ secret فقط از env (`S360_PAYEHYAR_CLIENT_SECRET` یا نام سند `PAYEHYAR_CLIENT_SECRET`)؛ بدون secret، مسیر کلید API/کاربر توسعه برقرار است |
| `X-Correlation-ID` یکتا در هر درخواست | UUID4 در `_request` — همه درخواست‌ها |
| `Idempotency-Key` برای هر POST | UUID4 خودکار روی هر POST (checkpoint و …) |
| `If-None-Match` → 304 (etag_cache) | کش ETag در کلاینت (کلید = مسیر + پارامترها)؛ 304 یعنی «بدون تغییر» و بدون انتقال داده |
| `If-Match` برای PATCH/PUT/DELETE | پارامتر `if_match` در `_request` با ETag دریافتی از GET |
| retry: max 5، نمایی، فقط 502/503/504 | حلقه retry با backoff نمایی + خطاهای شبکه؛ timeout پیش‌فرض ۳۰ ثانیه |
| دامنه‌ها: unique-courses، split-courses، syllabi، professors، classrooms، academic-groups، reference-sets | سه دامنه درس/سرفصل مسیر بومی قبلی؛ چهار دامنه گسترش‌یافته با مسیر رسمی services و fallback مدیریتی (X-Dev-User) |
| `initial_mode: full` + `delta_mode: since` | کاتالوگ کامل + `fetch_domain(since=…)`؛ cursor فید تغییرات عددی طبق OpenAPI |
| `schedule_cron: "0 */30 * * * *"` | حلقه async با `S360_PAYEHYAR_SYNC_INTERVAL_SECONDS=1800` و اجرای همگام‌سازی در executor (کلاینت/DB همگام‌اند) |
| events: exchange `payehyar.events` (topic durable)، صف `smart-learning.masterdata.q`، routing `payehyar.masterdata.#`، DLQ، inbox idempotent | ماژول `payehyar_events` با aio-pika؛ `msg.process(requeue=False)` → خطا به DLQ؛ جدول `smart_learning_event_inbox` با کلید event_id |
| monitoring: `/api/v1/health` و `/api/v1/ready` | در probe گزارش می‌شوند (در استقرار فعلی 404 هستند — شفاف در UI، مانع اتصال نیست) |

## تغییرات فنی

### بک‌اند (FastAPI)
- `app/services/payehyar_client.py`: بازنویسی لایه HTTP با قرارداد کامل سند؛ `auth_mode` جدید
  `OAUTH2`؛ probe با گزارش health/ready؛ `fetch_extended_domain` با fallback دو‌مرحله‌ای؛
  کرسر عددی فید تغییرات؛ حفظ کامل سازگاری با تست‌ها و کلاینت قبلی.
- `app/services/payehyar_records.py` (جدید): مخزن عمومی رکوردهای masterdata — upsert «یکتا و
  تفکیکی» با `UNIQUE(domain, external_id)` و تشخیص تغییر واقعی با content_hash؛ تورنگاشت حذف؛
  همگام‌سازی دامنه‌محور با تاب‌آوری (شکست هر دامنه = هشدار در لاگ EXTENDED).
- `app/services/payehyar_scheduler.py` (جدید): حلقه همگام‌سازی خودکار هر ۳۰ دقیقه + کاربر
  اجرای خودکار (اولین کاربر فعال آموزشی) + وضعیت برای UI.
- `app/services/payehyar_events.py` (جدید): مصرف‌کننده RabbitMQ با اتصال مقاوم، alias دامنه‌ها
  و عملیات‌ها از routing key (`payehyar.masterdata.<domain>.<op>.v1`)، اعمال upsert/delete به
  مدل بومی (درس) یا مخزن عمومی، ثبت idempotent در inbox.
- `app/models/journey.py`: دو مدل جدید `PayehyarRecord` + `PayehyarEventInbox`؛ مهاجرت
  `0003_payehyar_events`.
- `app/main.py`: lifespan با استارت/توقف امن زمان‌بند و مصرف‌کننده (فقط با تنظیم فعال).
- `app/api/v1/integration.py`: سه endpoint جدید (فقط کارکنان آموزشی):
  `POST /integration/payehyar/sync-extended`، `GET /integration/payehyar/records/{domain}`
  (صفحه‌بندی limit/offset)، `GET /integration/payehyar/system-status`.

### فرانت‌اند (React)
- صفحه «همگام‌سازی پایه‌یار»: کارت «زیرساخت خودکار یکپارچگی» — وضعیت زمان‌بند (فعال/غیرفعال،
  آخرین اجرا)، وضعیت رویدادهای RabbitMQ (اتصال، آمار پردازش/تکراری/ناموفق)، شمارنده رکوردهای
  دامنه‌های گسترش‌یافته و دکمه اجرای دستی؛ نشان نسخه ۳.۴.۰.

## ارتقا

1. `pip install -r backend/requirements.txt` (وابستگی جدید: `aio-pika`).
2. PostgreSQL: `alembic upgrade head` (مهاجرت 0003)؛ SQLite پرتیبل خودکار است.
3. کلید/secret را در `.env` تنظیم کنید (`S360_PAYEHYAR_API_KEY` یا `S360_PAYEHYAR_CLIENT_SECRET`)؛
   برای همگام‌سازی خودکار `S360_PAYEHYAR_AUTO_SYNC=true`؛ برای رویدادها، کاربر/رمز RabbitMQ را
   از مدیر پایه‌یار بگیرید و `S360_PAYEHYAR_EVENTS_ENABLED=true` کنید.
4. سرویس را بازراه‌اندازی کنید؛ وضعیت زیرساخت در صفحه «همگام‌سازی پایه‌یار» دیده می‌شود.

## تست

۱۷۰ تست سبز (۱۵۶ قبلی + ۱۴ جدید): قرارداد هدرها، OAuth2 و کش توکن، retry نمایی، ETag/304،
fallback دامنه‌های گسترش‌یافته، idempotency مخزن عمومی و inbox رویدادها (upsert/duplicate/
delete)، تورنگاشت، نگاشت routing key و RBAC سه endpoint جدید.
