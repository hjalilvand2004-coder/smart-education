"""تنظیمات اتصال یکپارچه‌سازی‌های خارجی — ذخیره در دیتابیس محلی (پرتیبل‌پسند).

ایدهٔ اصلی v3.4.2: کاربر از «داخل» خود اپ کلید و آدرس سرویس را ذخیره می‌کند و
به ویرایش فایل .env یا متغیر محیطی نیازی نیست؛ متغیر محیطی همچنان کار می‌کند
(اولویت: دیتابیس > متغیر محیطی > پیش‌فرض کد).
"""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class PayehyarConnection(TimestampMixin, Base):
    """اتصال به پایه‌یار۳۶۰ — ردیف یکتا (id=1) از صفحهٔ همگام‌سازی ذخیره می‌شود."""

    __tablename__ = "payehyar_connection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_url: Mapped[str] = mapped_column(String(255), default="")
    api_key: Mapped[str] = mapped_column(String(255), default="")
