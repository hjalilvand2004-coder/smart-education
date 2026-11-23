"""تنظیمات سامانه — همه مقادیر از متغیرهای محیطی با پیشوند S360_ خوانده می‌شود."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="S360_", extra="ignore")

    app_name: str = "دانشجو۳۶۰ — سرویس‌های یادگیری هوشمند"
    app_version: str = "3.2.2"

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
