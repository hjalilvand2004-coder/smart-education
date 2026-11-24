"""بذر دادهٔ پایه‌یار۳۶۰ داخل education.db — گام CI (اختیاری).

فقط وقتی اجرا می‌شود که کلید API پایه‌یار در مخفیانهٔ مخزن (repo secret)
S360_PAYEHYAR_API_KEY تنظیم شده باشد؛ در غیر این‌صورت بیلد بدون دادهٔ
پایه‌یار ادامه می‌یابد. شکست واکشی هرگز بیلد را نمی‌شکند (exit 0):
نسخهٔ منتشرشده نباید به دسترس‌پذیری سرویس مرجع در لحظهٔ build وابسته باشد.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    key = (os.environ.get("S360_PAYEHYAR_API_KEY")
           or os.environ.get("PAYEHYAR_API_KEY") or "")
    if not key:
        print("[i] کلید پایه‌یار (secret) تنظیم نشده — بذر دادهٔ پایه‌یار رد شد.")
        return 0
    os.environ["S360_PAYEHYAR_API_KEY"] = key
    os.environ.setdefault("S360_PAYEHYAR_BASE_URL", "http://188.212.96.235:8094")
    try:
        from app.core.bootstrap import ensure_schema_and_demo
        ensure_schema_and_demo()
        from app.core.database import SessionLocal
        from app.models.identity import User
        from app.services import payehyar_catalog, payehyar_records

        db = SessionLocal()
        user = (db.query(User).filter(User.username == "prof.rezaei").first()
                or db.query(User).first())
        res = payehyar_catalog.sync_catalog(db, user, "FULL")
        print(f"[i] کاتالوگ پایه‌یار: {res.get('message')}")
        for w in (res.get("warnings") or [])[:3]:
            print(f"[w] {w}")
        res2 = payehyar_records.sync_extended_domains(db, user, None)
        print(f"[i] دامنه‌های گسترش‌یافته: {res2.get('message')}")
        db.close()
        print("[i] بذر دادهٔ پایه‌یار انجام شد.")
    except Exception as exc:  # noqa: BLE001 — بیلد نباید به سرویس مرجع وابسته بماند
        print(f"[!] بذر پایه‌یار ناموفق (بیلد ادامه می‌یابد): "
              f"{type(exc).__name__}: {str(exc)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
