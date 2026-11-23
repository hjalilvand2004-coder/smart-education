"""AI Gateway — نقطه کنترل واحد همه فراخوانی‌های مدل (بخش ۱۴.۲).

- نسخه Prompt و مدل برای هر اجرا ثبت می‌شود (ai_runs).
- خروجی ساختاریافته با Schema بررسی و در صورت خطا یک بار تلاش دوباره می‌شود.
- سقف هزینه/مصرف روزانه کنترل می‌شود.
- مدل هیچ دسترسی مستقیمی به داده ندارد؛ فقط ورودی آماده‌شده را می‌بیند.
"""
import hashlib
import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app.ai.prompts import get_prompt
from app.ai.providers import get_provider
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.errors import ai_unavailable


def extract_json(text: str) -> dict:
    """استخراج JSON از متن مدل (تحمل code fence و متن اضافه)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no json object")
    return json.loads(text[start : end + 1])


class AIGateway:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.provider = get_provider()

    def _check_budget(self, purpose: str | None = None, created_by=None) -> None:
        """سقف مصرف سه‌لایه: کل سامانه، هر سرویس (purpose)، هر کاربر —
        تا مصرف یک بخش کل سامانه را متوقف نکند (بازخورد ۳.۱)."""
        from app.models.ops import AIRun

        since = utcnow() - timedelta(days=1)
        base_q = self.db.query(AIRun).filter(AIRun.created_at >= since)
        s = self.settings
        total = sum((t[0] or 0) for t in base_q.with_entities(AIRun.tokens_out).all())
        if total >= s.ai_daily_token_budget:
            raise ai_unavailable("سقف مصرف روزانه هوش مصنوعی پر شده است؛ حالت جایگزین (بدون AI) در دسترس است.")
        if purpose is not None:
            purpose_used = sum((t[0] or 0) for t in
                               base_q.filter(AIRun.purpose == purpose)
                               .with_entities(AIRun.tokens_out).all())
            if purpose_used >= s.ai_purpose_daily_budget:
                raise ai_unavailable("سقف مصرف روزانه این سرویس هوشمند پر شده است؛ فردا یا با پیکربندی ادمین ادامه می‌دهیم.")
        if created_by is not None:
            user_used = sum((t[0] or 0) for t in
                            base_q.filter(AIRun.created_by == created_by)
                            .with_entities(AIRun.tokens_out).all())
            if user_used >= s.ai_user_daily_token_budget:
                raise ai_unavailable("سقف مصرف روزانه شما از سرویس‌های هوشمند پر شده است؛ فردا دوباره در دسترس است.")

    def run(self, purpose: str, inputs: dict, schema=None, created_by=None, job_id=None):
        """اجرای یک purpose با اعتبارسنجی Schema؛ خروجی: نمونه Schema یا dict."""
        import inspect

        from app.models.ops import AIRun

        self._check_budget(purpose=purpose, created_by=created_by)
        prompt = get_prompt(purpose)
        user_msg = json.dumps({"purpose": purpose, "inputs": inputs}, ensure_ascii=False, default=str)
        input_hash = hashlib.sha256(user_msg.encode("utf-8")).hexdigest()

        last_error = None
        for attempt in range(2):
            import time

            t0 = time.monotonic()
            try:
                result = self.provider.complete(prompt["system"], user_msg)
                latency_ms = int((time.monotonic() - t0) * 1000)
            except Exception as exc:  # noqa: BLE001
                self._record_run(purpose, prompt["version"], "FAILED", 0, 0, 0, input_hash,
                                 str(exc), job_id, created_by)
                raise ai_unavailable(f"ارتباط با مدل برقرار نشد: {exc}") from exc
            try:
                data = extract_json(result.text)
                if schema is not None:
                    data = schema(**data)
                self._record_run(purpose, prompt["version"], "SUCCEEDED", latency_ms,
                                 result.tokens_in, result.tokens_out, input_hash, None, job_id, created_by)
                return data
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)[:300]
                # تلاش دوم: پیام اکیدتر — فقط JSON معتبر
                user_msg = user_msg + "\n\n⚠️ خروجی قبلی JSON معتبر نبود. فقط و فقط JSON معتبر مطابق شکل خواسته‌شده بازگردان."
        self._record_run(purpose, prompt["version"], "FAILED", 0, 0, 0, input_hash, last_error, job_id, created_by)
        raise ai_unavailable(f"خروجی مدل با Schema سازگار نشد: {last_error}")

    def stream(self, purpose: str, inputs: dict, schema=None, created_by=None):
        """پاسخ تدریجی: تکه‌های متن + در پایان متن کامل اعتبارسنجی‌شده و فراداده."""
        prompt = get_prompt(purpose)
        user_msg = json.dumps({"purpose": purpose, "inputs": inputs}, ensure_ascii=False, default=str)
        buffer: list[str] = []
        for chunk in self.provider.stream(prompt["system"], user_msg):
            buffer.append(chunk)
            yield {"type": "token", "text": chunk}
        full = "".join(buffer)
        if schema is not None:
            try:
                data = schema(**extract_json(full))
                yield {"type": "done", "data": data.model_dump()}
            except Exception:  # noqa: BLE001
                yield {"type": "done", "data": {"answer": full, "citations": [],
                                                "insufficient_evidence": False, "needs_teacher": False}}
        else:
            yield {"type": "done", "data": {"answer": full}}

    def _record_run(self, purpose, prompt_version, status, latency_ms, tokens_in, tokens_out,
                    input_hash, error, job_id, created_by) -> None:
        from app.models.ops import AIRun

        self.db.add(AIRun(
            purpose=purpose,
            provider=self.provider.name,
            model=getattr(self.provider, "model", None) or self.provider.name,
            prompt_version=prompt_version,
            status=status,
            latency_ms=latency_ms or None,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            input_hash=input_hash,
            error=error,
            related_job_id=job_id,
            created_by=created_by,
        ))
        try:
            self.db.flush()
        except Exception:  # noqa: BLE001
            pass
