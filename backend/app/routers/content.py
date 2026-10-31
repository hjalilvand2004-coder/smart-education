import time
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..security import get_current_user
from ..ai_service import (
    AIConfigurationError,
    AIProviderError,
    generate_educational_content,
)
from ..database import get_db
from ..models import CourseTopic, EducationalContent, AIServiceUsage
from ..schemas import ContentCreate, ContentResponse, ContentUpdate


router = APIRouter(
    prefix="/content",
    tags=["content"],
)


# ============================================================
# مدل برای محتوای دستی (آفلاین)
# ============================================================
class ManualContentCreate(BaseModel):
    """مدل دریافت محتوای دستی از استاد."""
    manual_content: str = Field(..., min_length=1, description="متن محتوای دستی")
    title: Optional[str] = Field(None, max_length=255, description="عنوان اختیاری")
    content_type: Optional[str] = Field("lesson", description="نوع محتوا")


# -------------------------------------------------------------------
# توابع کمکی
# -------------------------------------------------------------------

def _clean_text(value: Optional[Any]) -> str:
    """
    تبدیل مقدار به متن و حذف فاصله‌های ابتدا و انتها.
    """
    if value is None:
        return ""
    return str(value).strip()


def _get_topic_or_404(
    db: Session,
    topic_id: int,
) -> CourseTopic:
    """
    دریافت سرفصل بر اساس شناسه اصلی جدول course_topics.
    """
    if topic_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرفصل نامعتبر است.",
        )

    topic = (
        db.query(CourseTopic)
        .filter(CourseTopic.id == topic_id)
        .first()
    )

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"سرفصل با شناسه {topic_id} پیدا نشد.",
        )

    print(
        "[CONTENT] Topic found: "
        f"id={topic.id}, "
        f"course_id={topic.course_id}, "
        f"title={topic.title}"
    )

    return topic


def _get_content_or_404(
    db: Session,
    content_id: int,
) -> EducationalContent:
    """
    دریافت محتوا بر اساس شناسه و در صورت نبودن خطای ۴۰۴.
    """
    if content_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه محتوا نامعتبر است.",
        )

    content = (
        db.query(EducationalContent)
        .filter(EducationalContent.id == content_id)
        .first()
    )

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"محتوای آموزشی با شناسه {content_id} پیدا نشد.",
        )

    return content


def _get_generated_value(
    generated_result: dict[str, Any],
    *keys: str,
) -> str:
    """
    دریافت اولین مقدار متنی معتبر از چند کلید احتمالی.
    """
    for key in keys:
        value = _clean_text(
            generated_result.get(key)
        )
        if value:
            return value
    return ""


def _log_ai_usage(
    db: Session,
    provider: str,
    model: str,
    request_type: str,
    success: bool,
    error_message: str | None = None,
    tokens_used: int = 0,
    request_duration_ms: int = 0,
    topic_id: int | None = None,
) -> None:
    """
    ثبت یک رکورد استفاده از سرویس هوش مصنوعی در دیتابیس.
    """
    usage = AIServiceUsage(
        provider=provider,
        model=model,
        request_type=request_type,
        success=success,
        error_message=error_message,
        tokens_used=tokens_used,
        request_duration_ms=request_duration_ms,
        topic_id=topic_id,
    )
    db.add(usage)
    db.commit()


def _generate_and_save_content(
    *,
    db: Session,
    topic_id: int,
    request: ContentCreate,
) -> EducationalContent:
    """
    تولید محتوا با هوش مصنوعی و ذخیره در دیتابیس.
    """
    topic = _get_topic_or_404(
        db=db,
        topic_id=topic_id,
    )

    custom_text = _clean_text(
        getattr(request, "custom_text", None)
    )

    if len(custom_text) > 20_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="متن اختصاصی استاد نباید بیشتر از ۲۰۰۰۰ کاراکتر باشد.",
        )

    provider = (
        _clean_text(
            getattr(request, "provider", None)
        )
        or "openai_compatible"
    )

    model = (
        _clean_text(
            getattr(request, "model", None)
        )
        or "gpt-5.6"
    )

    language = (
        _clean_text(
            getattr(request, "language", None)
        )
        or "fa"
    )

    level = (
        _clean_text(
            getattr(request, "level", None)
        )
        or "intermediate"
    )

    content_type = (
        _clean_text(
            getattr(request, "content_type", None)
        )
        or "lesson"
    )

    start_time = time.time()
    success = True
    error_message = None
    tokens_used = 0

    try:
        generated_result = (
            generate_educational_content(
                topic_title=_clean_text(topic.title),
                topic_description=_clean_text(topic.description),
                teacher_instructions=custom_text,
                provider=provider,
                model=model,
                language=language,
                level=level,
                content_type=content_type,
            )
        )

        if not isinstance(generated_result, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="ساختار پاسخ هوش مصنوعی معتبر نیست.",
            )

        generated_title = _get_generated_value(
            generated_result,
            "title",
            "heading",
            "name",
        )

        if not generated_title:
            generated_title = (
                _clean_text(topic.title)
                or "محتوای آموزشی"
            )

        generated_body = _get_generated_value(
            generated_result,
            "body",
            "content",
            "html_content",
            "text",
            "description",
        )

        if not generated_body:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="مدل هوش مصنوعی محتوای معتبری تولید نکرد.",
            )

        generated_source = _get_generated_value(
            generated_result,
            "source",
            "provider",
        )

        content = EducationalContent(
            topic_id=topic.id,
            title=generated_title,
            body=generated_body,
            source=(
                generated_source
                or provider
                or "ai"
            ),
        )

        db.add(content)
        db.commit()
        db.refresh(content)

        print(
            "[CONTENT] Content saved: "
            f"content_id={content.id}, "
            f"topic_id={content.topic_id}"
        )

        # ثبت لاگ موفق
        duration_ms = int((time.time() - start_time) * 1000)
        tokens_used = len(generated_body) // 4
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="content_generation",
            success=True,
            tokens_used=tokens_used,
            request_duration_ms=duration_ms,
            topic_id=topic_id,
        )

        return content

    except (AIConfigurationError, AIProviderError) as error:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="content_generation",
            success=False,
            error_message=str(error),
            request_duration_ms=duration_ms,
            topic_id=topic_id,
        )

        if isinstance(error, AIConfigurationError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(error),
            ) from error

    except HTTPException as error:
        db.rollback()
        raise

    except SQLAlchemyError as error:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="content_generation",
            success=False,
            error_message=f"Database error: {str(error)}",
            request_duration_ms=duration_ms,
            topic_id=topic_id,
        )
        print("[CONTENT] Database error:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ذخیره محتوای آموزشی در دیتابیس.",
        ) from error

    except Exception as error:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        _log_ai_usage(
            db=db,
            provider=provider,
            model=model,
            request_type="content_generation",
            success=False,
            error_message=f"Unexpected error: {str(error)}",
            request_duration_ms=duration_ms,
            topic_id=topic_id,
        )
        print("[CONTENT] Unexpected error:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطای غیرمنتظره‌ای در تولید محتوا رخ داد.",
        ) from error


# -------------------------------------------------------------------
# تولید محتوا - مسیر اصلی (AI)
# -------------------------------------------------------------------

@router.post(
    "/generate/{topic_id}",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_content_for_topic(
    topic_id: int,
    request: ContentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> EducationalContent:
    """
    تولید محتوا برای یک سرفصل با استفاده از هوش مصنوعی.
    """
    return _generate_and_save_content(
        db=db,
        topic_id=topic_id,
        request=request,
    )


# ============================================================
# مسیر جدید: ذخیره محتوای دستی (آفلاین)
# ============================================================

@router.post(
    "/manual/{topic_id}",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_content(
    topic_id: int,
    request: ManualContentCreate,
    db: Session = Depends(get_db),
) -> EducationalContent:
    """
    ذخیره محتوای دستی (آفلاین) که استاد مستقیماً وارد کرده است.
    """
    topic = _get_topic_or_404(
        db=db,
        topic_id=topic_id,
    )

    manual_content = _clean_text(
        getattr(request, "manual_content", None)
    )

    if not manual_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="محتوای دستی نمی‌تواند خالی باشد.",
        )

    if len(manual_content) > 100_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="متن محتوا نباید بیشتر از ۱۰۰۰۰۰ کاراکتر باشد.",
        )

    title = _clean_text(
        getattr(request, "title", None)
    ) or f"محتوای دستی - {topic.title}"

    content_type = _clean_text(
        getattr(request, "content_type", None)
    ) or "lesson"

    try:
        content = EducationalContent(
            topic_id=topic.id,
            title=title,
            body=manual_content,
            source="manual",
        )

        db.add(content)
        db.commit()
        db.refresh(content)

        print(
            "[CONTENT] Manual content saved: "
            f"content_id={content.id}, "
            f"topic_id={content.topic_id}"
        )

        return content

    except SQLAlchemyError as error:
        db.rollback()
        print("[CONTENT] Database error:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در ذخیره محتوای دستی در دیتابیس.",
        ) from error

    except Exception as error:
        db.rollback()
        print("[CONTENT] Unexpected error:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطای غیرمنتظره: {str(error)}",
        ) from error


# ============================================================
# مسیر جدید: به‌روزرسانی محتوای موجود (ویرایش)
# ============================================================

@router.put(
    "/{content_id}",
    response_model=ContentResponse,
    status_code=status.HTTP_200_OK,
)
def update_content(
    content_id: int,
    request: ContentUpdate,
    db: Session = Depends(get_db),
) -> EducationalContent:
    """
    به‌روزرسانی محتوای موجود با شناسه داده شده.
    """
    content = _get_content_or_404(db=db, content_id=content_id)

    # دریافت داده‌های قابل به‌روزرسانی (فقط فیلدهایی که ارسال شده‌اند)
    update_data = request.dict(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حداقل یک فیلد برای به‌روزرسانی باید ارسال شود.",
        )

    # اعمال تغییرات
    try:
        for key, value in update_data.items():
            setattr(content, key, value)

        db.commit()
        db.refresh(content)

        print(
            "[CONTENT] Content updated: "
            f"content_id={content.id}, "
            f"topic_id={content.topic_id}"
        )

        return content

    except SQLAlchemyError as error:
        db.rollback()
        print("[CONTENT] Database error during update:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در به‌روزرسانی محتوا در دیتابیس.",
        ) from error

    except Exception as error:
        db.rollback()
        print("[CONTENT] Unexpected error during update:", repr(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطای غیرمنتظره در به‌روزرسانی: {str(error)}",
        ) from error


# -------------------------------------------------------------------
# مسیر قدیمی برای سازگاری با Frontend قبلی
# -------------------------------------------------------------------

@router.post(
    "/generate",
    response_model=ContentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_content_legacy(
    request: ContentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> EducationalContent:
    """
    مسیر قدیمی: POST /api/content/generate
    """
    topic_id = getattr(
        request,
        "topic_id",
        None,
    )

    if topic_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرفصل الزامی است.",
        )

    try:
        safe_topic_id = int(topic_id)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرفصل باید عددی باشد.",
        ) from error

    return _generate_and_save_content(
        db=db,
        topic_id=safe_topic_id,
        request=request,
    )


# -------------------------------------------------------------------
# دریافت محتواهای یک سرفصل
# -------------------------------------------------------------------

@router.get(
    "/topic/{topic_id}",
    response_model=list[ContentResponse],
    status_code=status.HTTP_200_OK,
)
def get_topic_contents(
    topic_id: int,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="تعداد محتواهای قابل دریافت",
    ),
    db: Session = Depends(get_db),
) -> list[EducationalContent]:
    """
    دریافت محتواهای تولیدشده برای یک سرفصل.
    """
    topic = _get_topic_or_404(
        db=db,
        topic_id=topic_id,
    )

    contents = (
        db.query(EducationalContent)
        .filter(
            EducationalContent.topic_id == topic.id
        )
        .order_by(
            EducationalContent.id.desc()
        )
        .limit(limit)
        .all()
    )

    print(
        "[CONTENT] Contents loaded: "
        f"topic_id={topic.id}, "
        f"count={len(contents)}"
    )

    return contents


# -------------------------------------------------------------------
# دریافت یک محتوای مشخص
# -------------------------------------------------------------------

@router.get(
    "/{content_id}",
    response_model=ContentResponse,
    status_code=status.HTTP_200_OK,
)
def get_content(
    content_id: int,
    db: Session = Depends(get_db),
) -> EducationalContent:
    """
    دریافت یک محتوای مشخص.
    """
    if content_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه محتوا نامعتبر است.",
        )

    content = (
        db.query(EducationalContent)
        .filter(
            EducationalContent.id == content_id
        )
        .first()
    )

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="محتوای آموزشی پیدا نشد.",
        )

    return content