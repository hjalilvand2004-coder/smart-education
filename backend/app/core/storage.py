"""ذخیره‌سازی فایل.

MVP: ذخیره محلی در پوشه data/storage با ثبت مشخصات (هش، حجم) در دیتابیس.
استقرار نهایی: فضای سازگار با S3 (مانند MinIO) با همین رابط.
"""
import hashlib
import re
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import validation_error

_SAFE_NAME = re.compile(r"[^\w.\-آ-ی]")


class LocalStorage:
    def __init__(self, base_dir: str | None = None):
        self.base = Path(base_dir or get_settings().storage_dir).resolve()

    def _resolve(self, rel_path: str) -> Path:
        """جلوگیری از خروج از ریشه ذخیره‌سازی (کنترل همه مسیرهای فایل)."""
        p = (self.base / rel_path).resolve()
        if not str(p).startswith(str(self.base)):
            raise validation_error("مسیر فایل نامعتبر است")
        return p

    def save(self, rel_path: str, data: bytes) -> dict:
        p = self._resolve(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {
            "path": rel_path,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }

    def open_path(self, rel_path: str) -> Path:
        p = self._resolve(rel_path)
        if not p.exists():
            from app.core.errors import not_found

            raise not_found("فایل یافت نشد")
        return p

    def delete(self, rel_path: str) -> None:
        p = self._resolve(rel_path)
        if p.exists():
            p.unlink()


def safe_filename(name: str) -> str:
    name = _SAFE_NAME.sub("_", Path(name).name)[:120]
    return name or "file"


def save_upload(content: bytes, filename: str, subdir: str = "uploads") -> dict:
    """ذخیره فایل بارگذاری‌شده با نام یکتا."""
    storage = LocalStorage()
    rel = f"{subdir}/{uuid.uuid4().hex[:8]}-{safe_filename(filename)}"
    info = storage.save(rel, content)
    info["filename"] = filename
    return info
