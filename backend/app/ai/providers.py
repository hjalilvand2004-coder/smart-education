"""ارائه‌دهندگان مدل زیر AI Gateway — تعویض مدل بدون تغییر منطق اصلی."""
import json

import httpx

from app.core.config import get_settings


class LLMResult:
    def __init__(self, text: str, tokens_in: int = 0, tokens_out: int = 0):
        self.text = text
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out


class BaseProvider:
    name = "base"

    def complete(self, system: str, user: str) -> LLMResult:  # pragma: no cover
        raise NotImplementedError

    def stream(self, system: str, user: str):  # pragma: no cover
        """تولید تدریجی متن؛ پیش‌فرض: کل پاسخ را یک‌جا می‌گیرد و تکه می‌کند."""
        result = self.complete(system, user)
        yield from _chunk_text(result.text)


def _chunk_text(text: str, size: int = 24):
    """تکه‌کردن متن برای SSE نمایش تدریجی."""
    words = text.split(" ")
    buf = []
    for w in words:
        buf.append(w)
        if len(" ".join(buf)) >= size:
            yield " ".join(buf) + " "
            buf = []
    if buf:
        yield " ".join(buf)


class MockProvider(BaseProvider):
    """مولد قطعی برای توسعه و دمو — خروجی JSON ساختاریافته معتبر."""

    name = "mock"

    def complete(self, system: str, user: str) -> LLMResult:
        from app.ai import mock_content

        try:
            payload = json.loads(user)
            purpose = payload.get("purpose", "")
            inputs = payload.get("inputs", {})
        except json.JSONDecodeError:
            purpose, inputs = "", {}
        dispatch = {
            "content_plan": mock_content.mock_content_plan,
            "content_generation": mock_content.mock_content_generation,
            "block_regeneration": mock_content.mock_block_regeneration,
            "question_generation": mock_content.mock_question_generation,
            "syllabus_extraction": mock_content.mock_syllabus_extraction,
            "essay_grading": mock_content.mock_essay_grading,
            "short_answer_check": mock_content.mock_short_answer_check,
            "tutor_answer": mock_content.mock_tutor_answer,
            "creation_feedback": mock_content.mock_creation_feedback,
        }
        fn = dispatch.get(purpose)
        out = fn(inputs) if fn else {"error": "unknown purpose"}
        text = json.dumps(out, ensure_ascii=False)
        return LLMResult(text, tokens_in=max(1, len(user) // 6), tokens_out=max(1, len(text) // 6))


class OpenAICompatProvider(BaseProvider):
    """ارائه‌دهنده سازگار با API متداول چت‌کمپلشن (GLM و مشابه)."""

    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, user: str) -> LLMResult:
        settings = get_settings()
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model or "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": settings and 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
        usage = data.get("usage", {})
        text = data["choices"][0]["message"]["content"]
        return LLMResult(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

    def stream(self, system: str, user: str):
        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta


def get_provider() -> BaseProvider:
    settings = get_settings()
    if settings.ai_provider == "openai_compat" and settings.ai_base_url:
        return OpenAICompatProvider(settings.ai_base_url, settings.ai_api_key, settings.ai_model)
    return MockProvider()
