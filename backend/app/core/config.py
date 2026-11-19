"""تنظیمات سامانه — همه مقادیر از متغیرهای محیطی با پیشوند S360_ خوانده می‌شود."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="S360_", extra="ignore")

    app_name: str = "دانشجو۳۶۰ — سرویس‌های یادگیری هوشمند"
    app_version: str = "1.0.0-mvp"

    # پایگاه داده؛ در محیط توسعه SQLite و در استقرار PostgreSQL:
    # postgresql+psycopg://user:pass@db:5432/student360
    database_url: str = "sqlite:///./data/student360.db"

    jwt_secret: str = "dev-only-secret-change-me-rotate-this-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    storage_dir: str = "./data/storage"

    # لایه AI Gateway: تعویض مدل بدون تغییر منطق اصلی
    ai_provider: str = "mock"  # mock | openai_compat
    ai_base_url: str = ""      # مثل https://api.example.com/v1
    ai_api_key: str = ""
    ai_model: str = ""
    ai_daily_token_budget: int = 2_000_000

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

    # توکن سرویس‌دهی به سایر سامانه‌ها (خالی = سرویس بدون توکن)
    service_token: str = ""

    # مسیر build فرانت‌اند برای نسخه پرتیبل (اختیاری؛ خالی = فقط API)
    frontend_dist: str = ""

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
