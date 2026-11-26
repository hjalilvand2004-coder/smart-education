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


class DarsyarConnection(TimestampMixin, Base):
    """اتصال به درس‌یار۳۶۰ (darsyar360.ir — مطلوبیات درسی/زمانی اساتید).

    الگوی PayehyarConnection: ردیف یکتا (id=1) از صفحهٔ تنظیمات درس‌یار ذخیره
    می‌شود؛ اولویت دیتابیس > متغیر محیطی S360_DARSYAR_* > پیش‌فرض کد.
    """

    __tablename__ = "darsyar_connection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_url: Mapped[str] = mapped_column(String(255), default="")
    api_key: Mapped[str] = mapped_column(String(255), default="")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=0)  # 0 = بدون مقدار DB


class MsuAgentConnection(TimestampMixin, Base):
    """اتصال به هستهٔ عامل «دانشگاه هوشمند من» (v3.11.0) — دستیار هوشمند دانشجو.

    ردیف یکتا (id=1) از کارت تنظیمات پنل مدیریت ذخیره می‌شود؛ ویجت شناور از
    مسیر widget-config همین تنظیمات را می‌خورد و در همهٔ صفحات در دسترس است.
    توکن، JWT صادرشده از هستهٔ عامل است (اختیاری؛ وقتی هسته REQUIRE_AUTH=true).
    """

    __tablename__ = "msu_agent_connection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_url: Mapped[str] = mapped_column(String(255), default="")
    origin: Mapped[str] = mapped_column(String(64), default="")       # شناسهٔ سامانهٔ میزبان
    accent: Mapped[str] = mapped_column(String(16), default="")       # رنگ اصلی ویجت
    accent2: Mapped[str] = mapped_column(String(16), default="")      # رنگ دوم گرادیان
    position: Mapped[str] = mapped_column(String(4), default="")      # br | bl
    token: Mapped[str] = mapped_column(String(1024), default="")      # JWT هستهٔ عامل
    enabled: Mapped[int] = mapped_column(Integer, default=1)          # 0 = ویجت خاموش
