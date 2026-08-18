import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# مسیر ریشه پروژه Backend
BASE_DIR = Path(__file__).resolve().parent.parent

# خواندن فایل .env از ریشه Backend
ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)


def _clean_env_value(value: str | None) -> str:
    """
    مقدار متغیر محیطی را خوانده و فاصله‌های اضافی را حذف می‌کند.
    """
    if value is None:
        return ""

    return value.strip().strip('"').strip("'")


# تنظیمات عمومی برنامه
DATABASE_URL = _clean_env_value(
    os.getenv(
        "DATABASE_URL",
        "sqlite:///./education.db",
    )
)


# تنظیمات سرویس هوش مصنوعی
AI_PROVIDER = _clean_env_value(
    os.getenv(
        "AI_PROVIDER",
        "openai_compatible",
    )
).lower()

OPENAI_API_KEY = _clean_env_value(
    os.getenv("OPENAI_API_KEY")
)

OPENAI_BASE_URL = _clean_env_value(
    os.getenv(
        "OPENAI_BASE_URL",
        "https://api.avalai.ir/v1",
    )
)

OPENAI_MODEL = _clean_env_value(
    os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6",
    )
)


# مدل‌هایی که در Frontend به کاربر نمایش داده می‌شوند.
# فقط مدل‌هایی را قرار دهید که در AvalAI برای API Key شما فعال هستند.
AI_MODELS: list[dict[str, str]] = [
    {
        "id": "gpt-5.6",
        "name": "GPT-5.6",
        "description": "مناسب برای تولید محتوای دقیق و پیشرفته",
    },
    {
        "id": "gpt-5.6-mini",
        "name": "GPT-5.6 Mini",
        "description": "سریع‌تر و کم‌هزینه‌تر",
    },
    {
        "id": "gpt-4o",
        "name": "GPT-4o",
        "description": "مدل چندمنظوره",
    },
]


def get_available_models() -> list[dict[str, str]]:
    """
    فهرست مدل‌های قابل انتخاب را برمی‌گرداند.
    """
    return AI_MODELS


def get_model_by_id(model_id: str | None) -> dict[str, str] | None:
    """
    یک مدل را بر اساس شناسه پیدا می‌کند.
    """
    if not model_id:
        return None

    for model in AI_MODELS:
        if model["id"] == model_id:
            return model

    return None


def get_selected_model(model_id: str | None = None) -> str:
    """
    مدل انتخاب‌شده را اعتبارسنجی می‌کند.

    اگر مدل ارسال نشود، مدل موجود در OPENAI_MODEL استفاده می‌شود.
    اگر مدل ارسال‌شده در فهرست مجاز نباشد، خطا ایجاد می‌شود.
    """
    requested_model = _clean_env_value(model_id)

    if not requested_model:
        return OPENAI_MODEL

    if get_model_by_id(requested_model) is None:
        raise ValueError(
            f"مدل انتخاب‌شده مجاز نیست: {requested_model}"
        )

    return requested_model


def validate_ai_settings() -> None:
    """
    بررسی تنظیمات لازم برای سرویس هوش مصنوعی.
    این تابع بهتر است هنگام شروع برنامه فراخوانی شود.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY در فایل .env تنظیم نشده است."
        )

    if not OPENAI_BASE_URL:
        raise RuntimeError(
            "OPENAI_BASE_URL در فایل .env تنظیم نشده است."
        )

    if not OPENAI_MODEL:
        raise RuntimeError(
            "OPENAI_MODEL در فایل .env تنظیم نشده است."
        )

    if not get_model_by_id(OPENAI_MODEL):
        raise RuntimeError(
            f"مدل پیش‌فرض در فهرست AI_MODELS وجود ندارد: "
            f"{OPENAI_MODEL}"
        )


def get_public_ai_settings() -> dict[str, Any]:
    """
    تنظیماتی که می‌توان با خیال راحت به Frontend ارسال کرد.
    کلید API هرگز در خروجی این تابع قرار نمی‌گیرد.
    """
    return {
        "provider": AI_PROVIDER,
        "default_model": OPENAI_MODEL,
        "models": get_available_models(),
    }