"""تنظیمات سامانه — همه مقادیر از متغیرهای محیطی با پیشوند S360_ خوانده می‌شود."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="S360_", extra="ignore")

    app_name: str = "دانشجو۳۶۰ — سرویس‌های یادگیری هوشمند"
    app_version: str = "3.13.0"

    # پایگاه داده؛ در محیط توسعه SQLite و در استقرار PostgreSQL:
    # postgresql+psycopg://user:pass@db:5432/student360
    database_url: str = "sqlite:///./data/student360.db"

    jwt_secret: str = "dev-only-secret-change-me-rotate-this-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    # بازنگری نشست (بازخورد ۳.۱): عمر کوتاه‌تر توکن + تمدید با /auth/refresh؛
    # مقدار قبلی (۷۲۰ دقیقه) برای محیط پرریسک طولانی بود.
    access_token_expire_minutes: int = 120

    storage_dir: str = "./data/storage"

    # لایه AI Gateway: تعویض مدل بدون تغییر منطق اصلی
    ai_provider: str = "mock"  # mock | openai_compat | ollama
    ai_base_url: str = ""      # مثل https://api.example.com/v1 (برای ollama: http://localhost:11434/v1)
    ai_api_key: str = ""
    ai_model: str = ""
    ai_daily_token_budget: int = 2_000_000
    # سهم‌بندی بودجه (بازخورد ۳.۱): مصرف یک سرویس/کاربر نباید کل سامانه را ببندد
    ai_purpose_daily_budget: int = 800_000     # سقف توکن روزانه هر purpose
    ai_user_daily_token_budget: int = 200_000  # سقف توکن روزانه هر کاربر

    # سیاست‌های آموزشی قابل تنظیم توسط دانشگاه
    ta_can_publish: bool = False          # انتشار محتوا فقط توسط استاد (پیش‌فرض)
    mastery_min_evidence: int = 3         # حداقل شواهد برای اعلام وضعیت تسلط
    mastery_recommend_evidence: int = 6   # حداقل شواهد برای اطمینان بیشتر
    similarity_warn_threshold: float = 0.85

    max_upload_mb: int = 20
    cors_origins: str = "*"  # جدا شده با کاما در استقرار واقعی

    # یکپارچه‌سازی با سامانه برنامه‌یار۳۶۰
    programyar_base_url: str = "http://188.212.96.235:8083"
    programyar_username: str = ""
    programyar_password: str = ""

    # ورود یکگانه (SSO/OIDC) با پرتال مرکزی — مثال: پرتال ورود یکپارچه روی :8086
    sso_base_url: str = "http://188.212.96.235:8086"
    sso_client_id: str = ""        # Client ID ثبت‌شده در پرتال SSO (مثل tahsilyar360)
    sso_client_secret: str = ""    # Client Secret همان ثبت
    sso_redirect_uri: str = "http://localhost:8000/api/v1/auth/sso/callback"
    sso_frontend_base: str = "http://localhost:8000"  # مقصد ریدایرکت پس از callback
    sso_scope: str = "openid profile email"
    # حاکمیت ورود (بازخورد ۳.۱): در استقرار تولیدی S360_SSO_REQUIRED=true
    # ورود محلی با کاربران نمونه را می‌بندد؛ فقط TECH_ADMIN برای مدیریت می‌ماند.
    sso_required: bool = False

    # یکپارچه‌سازی با پایه‌یار۳۶۰ (مرجع درس/سرفصل) — خالی = حالت نمونه توسعه
    baseyar_base_url: str = ""
    baseyar_api_key: str = ""
    baseyar_timeout_seconds: int = 8

    # همگام‌سازی کاتالوگ از استقرار واقعی پایه‌یار۳۶۰ (دروس + سرفصل‌ها) —
    # سرویس «PayehYar360 — Shared Core & Master Data» (پروب ۲۰۲۶-۱۱-۲۳، نسخه ۱.۰.۸):
    # endpoint مصرف‌کنندگان اکوسیستم /api/v1/services/masterdata/{domain} با هدر X-API-Key؛
    # در حالت توسعه سرویس مرجع، هدر X-Dev-User با کاربر دارای نقش steward/tenant_admin
    # و اتصال tenant نیز پذیرفته می‌شود. بدون کلید، واکشی با خطای قابل‌اقدام شکست می‌خورد.
    payehyar_base_url: str = "http://188.212.96.235:8094"
    payehyar_api_key: str = ""
    payehyar_dev_user: str = ""

    # یکپارچگی با درس‌یار۳۶۰ (darsyar360.ir) — مطلوبیات درسی/زمانی اساتید (v3.7.0).
    # کلید/مسیر رسمی سرویس هنوز مستند نشده؛ چند مسیر مرسوم امتحان می‌شود و در
    # نبود دسترسی، حالت نمونهٔ قطعی توسعه با source="demo" برمی‌گردد.
    darsyar_base_url: str = "https://darsyar360.ir"
    darsyar_api_key: str = ""
    darsyar_timeout_seconds: int = 8
    payehyar_timeout_seconds: int = 8

    # دستیار هوشمند «دانشگاه هوشمند من» (v3.11.0) — هستهٔ عامل + ویجت شناور.
    # تنظیمات مؤثر: دیتابیس (پنل مدیریت) > متغیر محیطی S360_MSU_AGENT_* > پیش‌فرض.
    msu_agent_base_url: str = "http://localhost:8000"
    msu_agent_origin: str = "student360"
    msu_agent_accent: str = "#7c3aed"
    msu_agent_accent2: str = "#5b21b6"
    msu_agent_position: str = "bl"  # v3.12.0: پیش‌فرض پایین‌چپ به درخواست کاربر
    msu_agent_token: str = ""
    msu_agent_enabled: bool = True

    # سند فنی اتصال v3.4.0 — احراز OAuth2 client_credentials (جایگزین/مکمل کلید API).
    # secret فقط از env می‌آید (S360_PAYEHYAR_CLIENT_SECRET یا PAYEHYAR_CLIENT_SECRET
    # مطابق سند) و هرگز در مخزن قرار نمی‌گیرد؛ تا وقتی خالی است، کلید API / کاربر
    # توسعه مسیر اصلی احراز هویت می‌مانند.
    payehyar_client_id: str = "smart-learning"
    payehyar_client_secret: str = ""
    payehyar_token_endpoint: str = "http://188.212.96.235:8086/oauth/token"
    payehyar_oauth_scope: str = "masterdata.read"

    # سند فنی — HTTP: timeout 30 و retry نمایی (حداکثر ۵ تلاش) روی 502/503/504
    payehyar_retry_max_attempts: int = 5
    payehyar_retry_backoff_seconds: float = 1.0
    payehyar_http_timeout_seconds: int = 30

    # سند فنی — همگام‌سازی زمان‌بندی‌شده (cron: 0 */30 * * * * → هر ۳۰ دقیقه)
    payehyar_auto_sync: bool = False          # در استقرار واقعی true شود
    payehyar_sync_interval_seconds: int = 1800
    payehyar_etag_cache: bool = True          # If-None-Match → 304 بدون انتقال داده
    payehyar_extended_domains: str = "professors,classrooms,academic-groups,reference-sets"

    # سند فنی — رویدادهای RabbitMQ (صف اختصاصی + DLQ + پردازش idempotent با inbox)
    payehyar_events_enabled: bool = False     # پس از دریافت اعتبار از مدیر پایه‌یار true شود
    payehyar_rabbitmq_host: str = "188.212.96.235"
    payehyar_rabbitmq_port: int = 5672
    payehyar_rabbitmq_user: str = ""
    payehyar_rabbitmq_password: str = ""
    payehyar_rabbitmq_exchange: str = "payehyar.events"
    payehyar_rabbitmq_queue: str = "smart-learning.masterdata.q"
    payehyar_rabbitmq_routing_key: str = "payehyar.masterdata.#"
    payehyar_rabbitmq_dlq: str = "smart-learning.masterdata.q.dlq"

    # توکن سرویس‌دهی به سایر سامانه‌ها (خالی = سرویس بدون توکن)
    service_token: str = ""

    # مسیر build فرانت‌اند برای نسخه پرتیبل (اختیاری؛ خالی = فقط API)
    frontend_dist: str = ""

    # بوت‌استرپ دیتابیس خالی (نسخهٔ پرتیبل): ساخت جدول‌ها + دادهٔ نمونهٔ دمو.
    # در تست‌ها با S360_BOOTSTRAP_DEMO_SEED=false خاموش می‌شود.
    bootstrap_demo_seed: bool = True

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
