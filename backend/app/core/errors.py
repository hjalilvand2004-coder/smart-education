"""خطاهای استاندارد سامانه — شکل پاسخ خطای یکسان با request_id برای ردیابی."""
import contextvars

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class AppError(Exception):
    """خطای دامنه‌ای با کد و پیام قابل نمایش به کاربر."""

    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def validation_error(message: str, details: dict | None = None) -> AppError:
    return AppError("VALIDATION_ERROR", message, 422, details)


def unauthorized(message: str = "احراز هویت لازم است") -> AppError:
    return AppError("UNAUTHORIZED", message, 401)


def forbidden(message: str = "دسترسی به این عملیات مجاز نیست") -> AppError:
    return AppError("FORBIDDEN", message, 403)


def not_found(message: str = "مورد موردنظر یافت نشد") -> AppError:
    return AppError("NOT_FOUND", message, 404)


def conflict(message: str, details: dict | None = None) -> AppError:
    return AppError("CONFLICT", message, 409, details)


def rate_limited(message: str = "تعداد درخواست‌ها بیش از حد مجاز است") -> AppError:
    return AppError("RATE_LIMITED", message, 429)


def ai_unavailable(message: str = "سرویس هوش مصنوعی در دسترس نیست") -> AppError:
    return AppError("AI_UNAVAILABLE", message, 503)
