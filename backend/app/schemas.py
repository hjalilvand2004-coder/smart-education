from __future__ import annotations

from datetime import datetime
from typing import Literal, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================
# مقادیر مجاز
# ============================================================

LanguageType = Literal[
    "fa",
    "en",
    "ar",
]

ContentLevelType = Literal[
    "beginner",
    "intermediate",
    "advanced",
]

ContentType = Literal[
    "lesson",
    "summary",
    "article",
    "lecture",
    "flashcard",
    "study_notes",
]

DifficultyType = Literal[
    "easy",
    "medium",
    "hard",
]

AIProviderType = Literal[
    "openai_compatible",
    "openai",
]


# ============================================================
# توابع کمکی اعتبارسنجی
# ============================================================

def normalize_optional_text(
    value: object,
) -> str | None:
    """
    متن اختیاری را Trim می‌کند.
    مقدار None یا رشته خالی را به None تبدیل می‌کند.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            "مقدار باید از نوع متن باشد."
        )

    value = value.strip()

    return value if value else None


def normalize_required_text(
    value: object,
) -> str:
    """
    متن اجباری را Trim می‌کند و در صورت خالی بودن خطا می‌دهد.
    """

    if not isinstance(value, str):
        raise ValueError(
            "مقدار باید از نوع متن باشد."
        )

    value = value.strip()

    if not value:
        raise ValueError(
            "مقدار متنی نمی‌تواند خالی باشد."
        )

    return value


def validate_model_name(
    value: object,
) -> str | None:
    """
    نام مدل هوش مصنوعی را نرمال می‌کند.
    """

    return normalize_optional_text(value)


# ============================================================
# Course / Topic Schemas
# ============================================================

class TopicResponse(BaseModel):
    """
    پاسخ مربوط به یک سرفصل.
    """

    id: int = Field(
        gt=0,
    )

    course_id: int = Field(
        gt=0,
    )

    title: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
    )

    session_minute: int = Field(
        default=50,
        ge=1,
        le=600,
    )

    sort_order: int = Field(
        default=1,
        ge=1,
    )

    is_active: bool = True

    model_config = ConfigDict(
        from_attributes=True,
    )

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return normalize_required_text(value)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(
        cls,
        value: object,
    ) -> str | None:
        return normalize_optional_text(value)


# ============================================================
# Content Schemas
# ============================================================

class ContentCreate(BaseModel):
    """
    اطلاعات لازم برای تولید محتوای آموزشی.

    کلید API نباید از Frontend دریافت شود.
    کلید API فقط در Backend و فایل .env قرار دارد.
    """

    topic_id: int = Field(
        gt=0,
    )

    custom_text: str | None = Field(
        default=None,
        max_length=20000,
    )

    provider: AIProviderType = Field(
        default="openai_compatible",
    )

    model: str | None = Field(
        default=None,
        max_length=150,
    )

    language: LanguageType = Field(
        default="fa",
    )

    level: ContentLevelType = Field(
        default="intermediate",
    )

    content_type: ContentType = Field(
        default="lesson",
    )

    @field_validator("custom_text", mode="before")
    @classmethod
    def validate_custom_text(
        cls,
        value: object,
    ) -> str | None:
        return normalize_optional_text(value)

    @field_validator("model", mode="before")
    @classmethod
    def validate_model(
        cls,
        value: object,
    ) -> str | None:
        value = validate_model_name(value)

        if value is not None and len(value) > 150:
            raise ValueError(
                "نام مدل نمی‌تواند بیشتر از ۱۵۰ کاراکتر باشد."
            )

        return value


class ContentResponse(BaseModel):
    """
    پاسخ محتوای آموزشی.

    این Schema با مدل فعلی EducationalContent هماهنگ است.
    مدل فعلی دارای این فیلدها است:

    - id
    - topic_id
    - title
    - body
    - source
    - created_at

    اگر بعداً فیلدهای تنظیمات هوش مصنوعی را به مدل دیتابیس
    اضافه کردید، می‌توانید آن‌ها را به این Schema نیز اضافه کنید.
    """

    id: int = Field(
        gt=0,
    )

    topic_id: int = Field(
        gt=0,
    )

    title: str = Field(
        min_length=1,
        max_length=255,
    )

    body: str = Field(
        min_length=1,
    )

    source: str = Field(
        min_length=1,
        max_length=50,
    )

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return normalize_required_text(value)

    @field_validator("body", mode="before")
    @classmethod
    def validate_body(cls, value: object) -> str:
        return normalize_required_text(value)

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, value: object) -> str:
        return normalize_required_text(value)


class ContentUpdate(BaseModel):
    """
    اطلاعات لازم برای به‌روزرسانی محتوای موجود.
    همه فیلدها اختیاری هستند و فقط فیلدهای ارسال‌شده به‌روز می‌شوند.
    """

    body: str | None = Field(
        default=None,
        min_length=1,
        max_length=100000,
        description="متن جدید محتوا",
    )

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="عنوان جدید محتوا",
    )

    summary: str | None = Field(
        default=None,
        max_length=1000,
        description="خلاصه جدید محتوا",
    )

    content_type: ContentType | None = Field(
        default=None,
        description="نوع جدید محتوا",
    )

    @field_validator("body", mode="before")
    @classmethod
    def validate_body(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("body باید متنی باشد.")
        value = value.strip()
        return value if value else None

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str | None:
        return normalize_optional_text(value)


# ============================================================
# Manual Content Schemas
# ============================================================

class ManualContentCreate(BaseModel):
    """
    اطلاعات لازم برای ذخیره محتوای دستی (آفلاین).
    """

    manual_content: str = Field(
        min_length=1,
        max_length=100000,
        description="متن محتوای دستی",
    )

    title: str | None = Field(
        default=None,
        max_length=255,
        description="عنوان اختیاری محتوا",
    )

    content_type: ContentType = Field(
        default="lesson",
        description="نوع محتوا",
    )

    @field_validator("manual_content", mode="before")
    @classmethod
    def validate_manual_content(
        cls,
        value: object,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError("manual_content باید متنی باشد.")
        value = value.strip()
        if not value:
            raise ValueError("manual_content نمی‌تواند خالی باشد.")
        return value

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(
        cls,
        value: object,
    ) -> str | None:
        return normalize_optional_text(value)


# ============================================================
# Quiz Schemas
# ============================================================

class QuizGenerateRequest(BaseModel):
    """
    اطلاعات لازم برای تولید آزمون.
    """

    course_id: int = Field(
        gt=0,
    )

    topic_id: int | None = Field(
        default=None,
        gt=0,
    )

    content_id: int | None = Field(
        default=None,
        gt=0,
    )

    number_of_questions: int = Field(
        default=5,
        ge=1,
        le=30,
    )

    question_type: str = Field(
        default="multiple_choice",
        pattern="^(multiple_choice|essay)$",
    )

    difficulty: DifficultyType = Field(
        default="medium",
    )

    language: LanguageType = Field(
        default="fa",
    )

    provider: AIProviderType = Field(
        default="openai_compatible",
    )

    model: str | None = Field(
        default=None,
        max_length=150,
    )

    @field_validator("model", mode="before")
    @classmethod
    def validate_model(
        cls,
        value: object,
    ) -> str | None:
        value = validate_model_name(value)

        if value is not None and len(value) > 150:
            raise ValueError(
                "نام مدل نمی‌تواند بیشتر از ۱۵۰ کاراکتر باشد."
            )

        return value

    @model_validator(mode="after")
    def validate_topic_or_content(self) -> QuizGenerateRequest:
        """
        حداقل یکی از topic_id یا content_id باید ارسال شود.
        """

        if (
            self.topic_id is None
            and self.content_id is None
        ):
            raise ValueError(
                "حداقل یکی از topic_id یا content_id "
                "باید ارسال شود."
            )

        return self


class QuestionResponse(BaseModel):
    """
    Schema نمایش سؤال به دانشجو.

    correct_option عمداً در این پاسخ وجود ندارد.
    """

    id: int = Field(
        gt=0,
    )

    question_text: str = Field(
        min_length=1,
    )

    question_type: str = Field(
        default="multiple_choice",
        pattern="^(multiple_choice|essay)$",
    )

    option_a: str | None = Field(
        default=None,
        max_length=500,
    )

    option_b: str | None = Field(
        default=None,
        max_length=500,
    )

    option_c: str | None = Field(
        default=None,
        max_length=500,
    )

    option_d: str | None = Field(
        default=None,
        max_length=500,
    )

    model_config = ConfigDict(
        from_attributes=True,
    )

    @field_validator(
        "question_text",
        mode="before",
    )
    @classmethod
    def validate_question_text(
        cls,
        value: object,
    ) -> str:
        return normalize_required_text(value)


class QuestionAdminResponse(QuestionResponse):
    """
    Schema نمایش سؤال برای استاد یا مدیر سیستم.
    """

    correct_option: str | None = Field(
        default=None,
        min_length=1,
        max_length=1,
    )

    explanation: str | None = None

    @field_validator("correct_option", mode="before")
    @classmethod
    def validate_correct_option(
        cls,
        value: object,
    ) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                "correct_option باید متنی باشد."
            )

        value = value.strip().upper()

        if value not in {"A", "B", "C", "D"}:
            raise ValueError(
                "correct_option باید یکی از گزینه‌های "
                "A، B، C یا D باشد."
            )

        return value

    @field_validator("explanation", mode="before")
    @classmethod
    def validate_explanation(
        cls,
        value: object,
    ) -> str | None:
        return normalize_optional_text(value)


class QuizResponse(BaseModel):
    """
    پاسخ آزمون برای دانشجو.
    """

    id: int = Field(
        gt=0,
    )

    title: str = Field(
        min_length=1,
        max_length=255,
    )

    course_id: int = Field(
        gt=0,
    )

    topic_id: int | None = Field(
        default=None,
        gt=0,
    )

    questions: list[QuestionResponse] = Field(
        default_factory=list,
    )

    created_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return normalize_required_text(value)


class QuizAdminResponse(BaseModel):
    """
    پاسخ کامل آزمون برای استاد یا مدیر.
    """

    id: int = Field(
        gt=0,
    )

    title: str = Field(
        min_length=1,
        max_length=255,
    )

    course_id: int = Field(
        gt=0,
    )

    topic_id: int | None = Field(
        default=None,
        gt=0,
    )

    questions: list[QuestionAdminResponse] = Field(
        default_factory=list,
    )

    created_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return normalize_required_text(value)


# ============================================================
# Answer Schemas
# ============================================================

class AnswerItem(BaseModel):
    """
    پاسخ یک سؤال.
    """

    question_id: int = Field(
        gt=0,
    )

    selected_option: str | None = Field(
        default=None,
        min_length=1,
        max_length=1,
    )

    essay_answer: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("selected_option", mode="before")
    @classmethod
    def validate_selected_option(
        cls,
        value: object,
    ) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                "selected_option باید متنی باشد."
            )

        value = value.strip().upper()

        if value not in {"A", "B", "C", "D"}:
            raise ValueError(
                "selected_option باید یکی از گزینه‌های "
                "A، B، C یا D باشد."
            )

        return value

    @field_validator("essay_answer", mode="before")
    @classmethod
    def validate_essay_answer(
        cls,
        value: object,
    ) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                "essay_answer باید متنی باشد."
            )
        value = value.strip()
        return value if value else None

    @model_validator(mode="after")
    def validate_answer_type(self) -> AnswerItem:
        if self.selected_option is None and self.essay_answer is None:
            raise ValueError("حداقل یکی از selected_option یا essay_answer باید پر شود.")
        return self


class QuizSubmitRequest(BaseModel):
    """
    اطلاعات ارسال پاسخ‌های آزمون.
    """

    student_name: str = Field(
        min_length=2,
        max_length=255,
    )

    answers: list[AnswerItem] = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("student_name", mode="before")
    @classmethod
    def validate_student_name(
        cls,
        value: object,
    ) -> str:
        value = normalize_required_text(value)

        if len(value) < 2:
            raise ValueError(
                "نام دانشجو باید حداقل دو کاراکتر داشته باشد."
            )

        if len(value) > 255:
            raise ValueError(
                "نام دانشجو نمی‌تواند بیشتر از ۲۵۵ کاراکتر باشد."
            )

        return value

    @model_validator(mode="after")
    def validate_unique_questions(
        self,
    ) -> QuizSubmitRequest:
        """
        یک سؤال نباید چند بار در پاسخ‌ها ارسال شود.
        """

        question_ids = [
            answer.question_id
            for answer in self.answers
        ]

        if len(question_ids) != len(set(question_ids)):
            raise ValueError(
                "برای یک سؤال نمی‌توان بیش از یک پاسخ ارسال کرد."
            )

        return self


# ============================================================
# Quiz Result Schemas
# ============================================================

class QuizResultResponse(BaseModel):
    """
    نتیجه آزمون.
    """

    student_name: str = Field(
        min_length=1,
        max_length=255,
    )

    score: int = Field(
        ge=0,
        le=100,
    )

    correct_answers: int = Field(
        ge=0,
    )

    total_questions: int = Field(
        ge=0,
    )

    pending_essay_review: bool = False

    model_config = ConfigDict(
        from_attributes=True,
    )


class AttemptResponse(BaseModel):
    """
    پاسخ مربوط به یک تلاش ثبت‌شده در آزمون.
    """

    id: int = Field(
        gt=0,
    )

    quiz_id: int = Field(
        gt=0,
    )

    student_name: str = Field(
        min_length=1,
        max_length=255,
    )

    score: int = Field(
        ge=0,
        le=100,
    )

    correct_answers: int = Field(
        ge=0,
    )

    total_questions: int = Field(
        ge=0,
    )

    pending_essay_review: bool = False

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class AttemptDetailResponse(AttemptResponse):
    """
    پاسخ کامل یک تلاش شامل پاسخ‌های ذخیره‌شده.
    """

    answers_data: dict[str, Any] | None = None


class QuizSubmitResponse(BaseModel):
    """
    پاسخ نهایی بعد از شرکت دانشجو در آزمون.
    """

    attempt_id: int = Field(
        gt=0,
    )

    quiz_id: int = Field(
        gt=0,
    )

    student_name: str = Field(
        min_length=1,
        max_length=255,
    )

    score: int = Field(
        ge=0,
        le=100,
    )

    correct_answers: int = Field(
        ge=0,
    )

    total_questions: int = Field(
        ge=0,
    )

    pending_essay_review: bool = False

    message: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# Course Schemas
# ============================================================

class CourseCreate(BaseModel):
    """داده‌های مورد نیاز برای ایجاد یک درس جدید."""

    id: int = Field(gt=0, description="شناسه عددی درس")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = Field(default=True)

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return normalize_required_text(value)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> str | None:
        return normalize_optional_text(value)


class CourseResponse(BaseModel):
    """پاسخ یک درس."""

    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return normalize_required_text(value)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> str | None:
        return normalize_optional_text(value)