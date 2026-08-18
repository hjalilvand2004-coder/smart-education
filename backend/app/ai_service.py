import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

# تنظیم لاگر
logger = logging.getLogger(__name__)

load_dotenv()


# =========================================================
# خطاهای اختصاصی
# =========================================================

class AIConfigurationError(Exception):
    """خطاهای مربوط به تنظیمات سرویس هوش مصنوعی."""
    pass


class AIProviderError(Exception):
    """خطاهای مربوط به API یا پاسخ مدل هوش مصنوعی."""
    pass


# =========================================================
# توابع تنظیمات
# =========================================================

def _get_env(
    name: str,
    default: Optional[str] = None,
) -> Optional[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _get_provider(
    provider: Optional[str] = None,
) -> str:
    selected_provider = (
        provider
        or _get_env(
            "AI_PROVIDER",
            "openai_compatible",
        )
        or "openai_compatible"
    )
    return selected_provider.strip().lower()


def _get_model(
    provider: str,
    model: Optional[str] = None,
) -> str:
    if model and model.strip():
        return model.strip()
    if provider == "ollama":
        return (
            _get_env(
                "OLLAMA_MODEL",
                "llama3.1",
            )
            or "llama3.1"
        )
    # تغییر مدل پیش‌فرض به gpt-5.6 یا gpt-4o (موجود در AvalAI)
    return (
        _get_env(
            "OPENAI_MODEL",
            "gpt-5.2",  # تغییر از gpt-5.2 به gpt-5.6
        )
        or "gpt-5.6"
    )


def _get_api_key(
    provider: str,
) -> Optional[str]:
    if provider == "ollama":
        return (
            _get_env("OLLAMA_API_KEY")
            or "ollama"
        )
    return (
        _get_env("AVALAI_API_KEY")
        or _get_env("OPENAI_API_KEY")
        or _get_env("AI_API_KEY")
    )


def _get_base_url(
    provider: str,
) -> str:
    if provider == "ollama":
        return (
            _get_env(
                "OLLAMA_BASE_URL",
                "http://127.0.0.1:11434/v1",
            )
            or "http://127.0.0.1:11434/v1"
        )
    if provider == "openai_compatible":
        return (
            _get_env("AVALAI_BASE_URL")
            or _get_env("OPENAI_BASE_URL")
            or "https://api.avalai.ir/v1"
        )
    return (
        _get_env(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1",
        )
        or "https://api.openai.com/v1"
    )


def _build_client(
    provider: str,
) -> OpenAI:
    provider = provider.strip().lower()
    if provider not in {
        "openai",
        "openai_compatible",
        "ollama",
        "custom",
    }:
        raise AIConfigurationError(
            f"ارائه‌دهنده هوش مصنوعی ناشناخته است: {provider}"
        )
    api_key = _get_api_key(provider)
    if not api_key:
        raise AIConfigurationError(
            "کلید API تنظیم نشده است. "
            "متغیر AVALAI_API_KEY یا OPENAI_API_KEY را "
            "در فایل .env قرار دهید."
        )
    base_url = _get_base_url(provider)
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    )


# =========================================================
# پردازش پاسخ JSON
# =========================================================

def _extract_json(
    value: Any,
) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        raise AIProviderError(
            "پاسخ مدل هوش مصنوعی قابل پردازش نیست."
        )
    text = value.strip()
    if not text:
        raise AIProviderError(
            "پاسخ مدل هوش مصنوعی خالی است."
        )
    text = (
        text
        .replace("```json", "")
        .replace("```JSON", "")
        .replace("```Json", "")
        .replace("```", "")
        .strip()
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    candidates: List[str] = []
    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start >= 0 and object_end > object_start:
        candidates.append(
            text[object_start: object_end + 1]
        )
    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start >= 0 and array_end > array_start:
        candidates.append(
            text[array_start: array_end + 1]
        )
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise AIProviderError(
        "پاسخ مدل شامل JSON معتبر نیست."
    )


# =========================================================
# ارسال درخواست عمومی به مدل
# =========================================================

def _chat_completion(
    system_prompt: str,
    user_prompt: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.4,
    max_tokens: int = 5000,
    json_mode: bool = False,
) -> str:
    selected_provider = _get_provider(provider)
    selected_model = _get_model(
        selected_provider,
        model,
    )
    client = _build_client(selected_provider)

    request_data: Dict[str, Any] = {
        "model": selected_model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        request_data["response_format"] = {
            "type": "json_object",
        }

    try:
        logger.info(f"Sending request to AI: provider={selected_provider}, model={selected_model}")
        response = client.chat.completions.create(
            **request_data
        )
        logger.info("AI request successful")
    except BadRequestError as error:
        error_text = str(error).lower()
        if json_mode and (
            "response_format" in error_text
            or "json_object" in error_text
            or "unsupported" in error_text
        ):
            request_data.pop("response_format", None)
            try:
                response = client.chat.completions.create(
                    **request_data
                )
            except Exception as retry_error:
                raise AIProviderError(
                    f"درخواست سرویس هوش مصنوعی نامعتبر است: "
                    f"{retry_error}"
                ) from retry_error
        else:
            raise AIProviderError(
                f"درخواست سرویس هوش مصنوعی نامعتبر است: "
                f"{error}"
            ) from error
    except AuthenticationError as error:
        raise AIProviderError(
            "احراز هویت با سرویس هوش مصنوعی ناموفق بود. "
            "کلید API و Base URL را بررسی کنید."
        ) from error
    except RateLimitError as error:
        raise AIProviderError(
            "محدودیت درخواست سرویس هوش مصنوعی اعمال شده است."
        ) from error
    except APIConnectionError as error:
        raise AIProviderError(
            "ارتباط با سرویس هوش مصنوعی برقرار نشد. "
            "اتصال اینترنت و Base URL را بررسی کنید."
        ) from error
    except APIStatusError as error:
        raise AIProviderError(
            "سرویس هوش مصنوعی خطا برگرداند: "
            f"{error.status_code}"
        ) from error
    except Exception as error:
        raise AIProviderError(
            f"خطای ناشناخته در سرویس هوش مصنوعی: {error}"
        ) from error

    if not response.choices:
        raise AIProviderError(
            "مدل هوش مصنوعی پاسخ خالی برگرداند."
        )
    message = response.choices[0].message
    content = message.content or ""
    if not content.strip():
        raise AIProviderError(
            "محتوای پاسخ مدل خالی است."
        )
    return content.strip()


# =========================================================
# محتوای آزمایشی (فقط برای مواقع ضروری)
# =========================================================

def generate_demo_content(
    title: str,
    description: Optional[str] = None,
) -> str:
    return f"""
# {title}

## مقدمه

در این جلسه با موضوع «{title}» آشنا می‌شویم.

## اهداف یادگیری

- شناخت مفاهیم اصلی {title}
- آشنایی با کاربردهای موضوع
- توانایی استفاده از مفاهیم در یک پروژه عملی

## توضیح درس

{description or "برای این سرفصل توضیحی ثبت نشده است."}

موضوع «{title}» یکی از مباحث مهم آموزشی است.
دانشجو باید ابتدا مفاهیم پایه را یاد بگیرد و سپس
آن‌ها را با استفاده از مثال و تمرین عملی به کار بگیرد.

## مثال عملی

یک پروژه کوچک ایجاد کنید و حداقل یک نمونه از مفاهیم
این جلسه را در آن پیاده‌سازی کنید.

## تمرین

یک مثال واقعی از کاربرد «{title}» پیدا کرده و مراحل
اجرای آن را توضیح دهید.

## نکات کلیدی

- مفاهیم پایه را به‌صورت دقیق یاد بگیرید.
- بین نظریه و کاربرد عملی ارتباط برقرار کنید.
- برای تثبیت یادگیری، تمرین عملی انجام دهید.

## جمع‌بندی

در این جلسه با مفهوم، کاربرد و روش استفاده از
«{title}» آشنا شدیم.
""".strip()


def generate_demo_questions(
    title: str,
    number: int,
    question_type: str = "multiple_choice",
) -> List[Dict[str, Any]]:
    """
    این تابع فقط برای مواقع ضروری (مثلاً خطای شدید) استفاده می‌شود.
    در حالت عادی، نباید از آن استفاده شود.
    """
    number = max(1, min(number, 30))
    if question_type == "essay":
        return [
            {
                "question_text": f"مفهوم «{title}» را توضیح دهید و کاربردهای آن را بیان کنید.",
                "model_answer": f"«{title}» یکی از مفاهیم اساسی در این حوزه است که شامل ...",
                "explanation": "پاسخ باید شامل تعریف، ویژگی‌ها و مثال‌های کاربردی باشد."
            }
            for _ in range(number)
        ]

    templates = [
        (
            f"کدام گزینه درباره «{title}» صحیح است؟",
            "یک موضوع مرتبط با درس و توسعه نرم‌افزار است",
            "یک سیستم‌عامل است",
            "یک نوع سخت‌افزار است",
            "هیچ کاربردی ندارد",
        ),
        (
            f"هدف اصلی یادگیری «{title}» چیست؟",
            "شناخت مفاهیم و کاربردهای آن",
            "حذف نیاز به یادگیری",
            "افزایش حجم فایل‌ها",
            "تغییر سیستم‌عامل",
        ),
    ]
    questions: List[Dict[str, Any]] = []
    for index in range(number):
        item = templates[index % len(templates)]
        questions.append(
            {
                "question_text": item[0],
                "option_a": item[1],
                "option_b": item[2],
                "option_c": item[3],
                "option_d": item[4],
                "correct_option": "A",
                "explanation": "گزینه A پاسخ صحیح است.",
            }
        )
    return questions


# =========================================================
# تولید محتوای آموزشی
# =========================================================

def _build_content_system_prompt(
    language: str,
    level: str,
    content_type: str,
) -> str:
    language_name = {
        "fa": "فارسی",
        "en": "English",
        "ar": "العربية",
    }.get(language, language)
    content_type_name = {
        "lesson": "درس آموزشی",
        "summary": "خلاصه آموزشی",
        "article": "مقاله آموزشی",
        "lecture": "جزوه دانشگاهی",
        "flashcard": "فلش‌کارت آموزشی",
        "study_notes": "یادداشت مطالعاتی",
    }.get(content_type, "محتوای آموزشی")
    return f"""
شما یک استاد دانشگاه و طراح محتوای آموزشی حرفه‌ای هستید.

یک {content_type_name} به زبان {language_name} تولید کنید.

سطح مخاطب:
{level}

قواعد تولید:

1. محتوا دقیق، منسجم و قابل تدریس باشد.
2. محتوا برای دانشجوی دانشگاه نوشته شود.
3. از اطلاعات ساختگی و ادعاهای غیرقابل اطمینان خودداری کنید.
4. محتوا شامل مقدمه، مفاهیم اصلی، مثال، کاربرد،
   نکات کلیدی و جمع‌بندی باشد.
5. برای تیترها از Markdown استفاده کنید.
6. برای فهرست‌ها از علامت "-" استفاده کنید.
7. توضیحات استاد را به‌عنوان راهنما در نظر بگیرید.
8. خروجی فقط JSON معتبر باشد.
9. هیچ متنی خارج از JSON تولید نکنید.

ساختار خروجی:

{{
  "title": "عنوان محتوا",
  "body": "متن کامل و ساختاریافته محتوا",
  "summary": "خلاصه کوتاه محتوا",
  "learning_objectives": [
    "هدف یادگیری اول",
    "هدف یادگیری دوم"
  ]
}}
""".strip()


def generate_educational_content(
    topic_title: str,
    topic_description: str = "",
    teacher_instructions: str = "",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "fa",
    level: str = "intermediate",
    content_type: str = "lesson",
) -> Dict[str, Any]:
    system_prompt = _build_content_system_prompt(
        language=language,
        level=level,
        content_type=content_type,
    )
    user_prompt = f"""
عنوان سرفصل:
{topic_title}

توضیحات سرفصل:
{topic_description or "توضیحی برای سرفصل ثبت نشده است."}

دستورها و منابع اختصاصی استاد:
{teacher_instructions or "دستور اختصاصی ارائه نشده است."}

بر اساس اطلاعات بالا، محتوای آموزشی تولید کن.
""".strip()
    raw_response = _chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        provider=provider,
        model=model,
        temperature=0.35,
        max_tokens=6000,
        json_mode=True,
    )
    result = _extract_json(raw_response)
    if not isinstance(result, dict):
        raise AIProviderError(
            "ساختار پاسخ تولید محتوا باید یک شیء JSON باشد."
        )
    title = str(
        result.get("title")
        or topic_title
        or "محتوای آموزشی"
    ).strip()
    body = str(
        result.get("body")
        or ""
    ).strip()
    if not body:
        raise AIProviderError(
            "بدنه محتوای تولیدشده خالی است."
        )
    learning_objectives = result.get(
        "learning_objectives",
        [],
    )
    if not isinstance(learning_objectives, list):
        learning_objectives = []
    return {
        "title": title,
        "body": body,
        "summary": result.get("summary"),
        "learning_objectives": learning_objectives,
        "source": _get_provider(provider),
        "provider": _get_provider(provider),
        "model": _get_model(
            _get_provider(provider),
            model,
        ),
        "language": language,
        "level": level,
        "content_type": content_type,
    }


def generate_content(
    title: str,
    description: Optional[str] = None,
) -> str:
    try:
        result = generate_educational_content(
            topic_title=title,
            topic_description=description or "",
            teacher_instructions="",
            provider=None,
            model=None,
            language="fa",
            level="intermediate",
            content_type="lesson",
        )
        return result["body"]
    except (
        AIConfigurationError,
        AIProviderError,
    ):
        return generate_demo_content(
            title=title,
            description=description,
        )


# =========================================================
# تولید سؤال (چهارگزینه‌ای و تشریحی) با AI
# =========================================================

def generate_questions(
    title: str,
    content: str,
    number: int,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    difficulty: str = "medium",
    language: str = "fa",
    question_type: str = "multiple_choice",
) -> List[Dict[str, Any]]:
    """
    تولید سؤال بر اساس محتوای آموزشی با استفاده از هوش مصنوعی.
    در صورت بروز هرگونه خطا، خطا را propagate می‌کند (بدون fallback به دمو).
    """
    number = max(1, min(number, 30))
    logger.info(f"Generating {number} questions of type '{question_type}' for topic '{title}'")

    # بهبود پرامپت برای تنوع بیشتر
    diversity_note = """
برای افزایش تنوع و جلوگیری از تکرار سوالات:
- از بخش‌های مختلف محتوا (مقدمه، بدنه، مثال‌ها، نتیجه‌گیری) سوال طراحی کن.
- از کلمات و عبارات مترادف استفاده کن تا سوالات یکسان نباشند.
- سوالات را با زوایای مختلف از یک مفهوم طراحی کن.
- از مثال‌های متنوع استفاده کن.
- اگر محتوا طولانی است، از بخش‌های مختلف آن سوال استخراج کن.
- سوالات باید پوشش دهنده مفاهیم کلیدی محتوا باشند.
"""

    if question_type == "essay":
        system_prompt = f"""
شما یک طراح آزمون دانشگاهی حرفه‌ای هستید که سوالات تشریحی عمیق و تحلیلی طراحی می‌کنید.

بر اساس محتوای ارائه‌شده، سؤال‌های تشریحی (توصیفی) به زبان {language} تولید کنید.

قواعد:
1. سؤال‌ها فقط بر اساس محتوای داده‌شده باشند و به بخش‌های کلیدی محتوا اشاره کنند.
2. هر سؤال یک پاسخ مدل (model_answer) داشته باشد که پاسخ کامل و جامع را نشان دهد.
3. برای هر سؤال توضیح مختصری (explanation) درباره پاسخ صحیح بنویسید.
4. سؤال‌ها در سطح دشواری {difficulty} باشند.
5. خروجی فقط JSON معتبر باشد.
6. خروجی یک آرایه JSON باشد.
7. {diversity_note}

ساختار هر سؤال:
{{
  "question_text": "متن سؤال تشریحی",
  "model_answer": "پاسخ کامل و صحیح (حداقل ۳-۴ جمله)",
  "explanation": "توضیح مختصر درباره پاسخ"
}}
""".strip()

        user_prompt = f"""
عنوان سرفصل: {title}

محتوای آموزشی:
{content}

تعداد سؤال مورد نیاز: {number}

دقیقاً {number} سؤال تشریحی متنوع و مرتبط با محتوا تولید کن.
""".strip()

    else:  # multiple_choice
        system_prompt = f"""
شما یک طراح آزمون دانشگاهی حرفه‌ای هستید که سوالات چهارگزینه‌ای استاندارد و چالش‌برانگیز طراحی می‌کنید.

بر اساس محتوای ارائه‌شده، سؤال‌های چهارگزینه‌ای به زبان {language} تولید کنید.

قواعد:
1. سؤال‌ها فقط بر اساس محتوای داده‌شده باشند و به بخش‌های مختلف محتوا بپردازند.
2. هر سؤال دقیقاً چهار گزینه داشته باشد.
3. فقط یک گزینه صحیح باشد.
4. گزینه‌ها با کلیدهای option_a تا option_d باشند.
5. correct_option فقط یکی از A، B، C یا D باشد.
6. برای هر سؤال توضیح پاسخ صحیح بنویسید (explanation).
7. سؤال‌ها در سطح دشواری {difficulty} باشند.
8. خروجی فقط JSON معتبر باشد.
9. خروجی یک آرایه JSON باشد.
10. {diversity_note}

ساختار هر سؤال:
{{
  "question_text": "متن سؤال",
  "option_a": "گزینه اول",
  "option_b": "گزینه دوم",
  "option_c": "گزینه سوم",
  "option_d": "گزینه چهارم",
  "correct_option": "A",
  "explanation": "توضیح پاسخ صحیح"
}}
""".strip()

        user_prompt = f"""
عنوان سرفصل: {title}

محتوای آموزشی:
{content}

تعداد سؤال مورد نیاز: {number}

دقیقاً {number} سؤال چهارگزینه‌ای متنوع و مرتبط با محتوا تولید کن.
""".strip()

    try:
        logger.info(f"Calling AI to generate {number} {question_type} questions")
        raw_response = _chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            provider=provider,
            model=model,
            temperature=0.8,  # افزایش دما برای تنوع بیشتر
            max_tokens=6000,
            json_mode=False,
        )

        result = _extract_json(raw_response)
        logger.info(f"AI response received, type: {type(result)}")

        if not isinstance(result, list):
            raise AIProviderError("خروجی سؤال‌ها باید یک آرایه JSON باشد.")

        normalized_questions: List[Dict[str, Any]] = []
        seen_questions = set()  # برای جلوگیری از تکرار سوالات

        for idx, item in enumerate(result[:number]):
            if not isinstance(item, dict):
                continue

            if question_type == "essay":
                question_text = str(item.get("question_text", "")).strip()
                model_answer = str(item.get("model_answer", "")).strip()
                explanation = str(item.get("explanation", "")).strip() or None

                if question_text and model_answer:
                    # چک کردن تکراری نبودن
                    key = question_text[:50]  # برای مقایسه
                    if key not in seen_questions:
                        seen_questions.add(key)
                        normalized_questions.append({
                            "question_text": question_text,
                            "model_answer": model_answer,
                            "explanation": explanation,
                        })
            else:
                question_text = str(item.get("question_text", "")).strip()
                option_a = str(item.get("option_a", "")).strip()
                option_b = str(item.get("option_b", "")).strip()
                option_c = str(item.get("option_c", "")).strip()
                option_d = str(item.get("option_d", "")).strip()
                correct_option = str(item.get("correct_option", "A")).strip().upper()
                if correct_option not in {"A", "B", "C", "D"}:
                    correct_option = "A"

                required_fields = [question_text, option_a, option_b, option_c, option_d]
                if all(required_fields):
                    key = question_text[:50]  # برای مقایسه
                    if key not in seen_questions:
                        seen_questions.add(key)
                        normalized_questions.append({
                            "question_text": question_text,
                            "option_a": option_a,
                            "option_b": option_b,
                            "option_c": option_c,
                            "option_d": option_d,
                            "correct_option": correct_option,
                            "explanation": str(item.get("explanation", "")).strip() or None,
                        })

        if not normalized_questions:
            raise AIProviderError("مدل هیچ سؤال معتبر و قابل ذخیره‌ای تولید نکرد.")

        logger.info(f"Successfully generated {len(normalized_questions)} unique {question_type} questions")
        return normalized_questions

    except (AIConfigurationError, AIProviderError) as error:
        logger.error(f"AI error in generate_questions: {error}")
        # خطا را propagate می‌کنیم (بدون fallback به دمو)
        raise

    except Exception as error:
        logger.exception(f"Unexpected error in generate_questions: {error}")
        raise AIProviderError(f"خطای غیرمنتظره در تولید سوالات: {error}")

    # =========================================================
    # ثبت آمار استفاده از سرویس AI
    # =========================================================

    def log_ai_usage(
            db: Session,
            provider: str,
            model: str,
            request_type: str,
            success: bool = True,
            error_message: str | None = None,
            tokens_used: int = 0,
            request_duration_ms: int = 0,
            topic_id: int | None = None,
            question_count: int = 0,
    ) -> None:
        """
        ثبت یک رکورد استفاده از سرویس هوش مصنوعی در دیتابیس.
        """
        from ..models import AIServiceUsage  # import inside to avoid circular

        usage = AIServiceUsage(
            provider=provider,
            model=model,
            request_type=request_type,
            success=success,
            error_message=error_message,
            tokens_used=tokens_used,
            request_duration_ms=request_duration_ms,
            topic_id=topic_id,
            question_count=question_count,
        )
        db.add(usage)
        db.commit()