from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import logging

from ..database import get_db
from ..models import AIServiceUsage


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai-stats",
    tags=["AI Statistics"],
)


@router.get("/test")
def test_endpoint():
    return {"status": "ok", "message": "AI Stats router is working"}


@router.get("/summary")
def get_ai_usage_summary(
    days: int = 30,
    db: Session = Depends(get_db),
):
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تعداد روزها باید بین 1 تا 365 باشد."
        )

    try:
        # ابتدا بررسی می‌کنیم که جدول وجود دارد یا نه
        from sqlalchemy import inspect
        inspector = inspect(db.get_bind())
        if not inspector.has_table("ai_service_usage"):
            return {
                "period_days": days,
                "total": {
                    "total_requests": 0,
                    "total_tokens": 0,
                    "total_questions_generated": 0,
                    "avg_duration_ms": 0,
                },
                "by_provider": [],
                "by_model": [],
                "by_request_type": [],
                "recent_requests": [],
                "message": "هنوز آماری ثبت نشده است. جدول AI Service Usage خالی است."
            }

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # استفاده از case به صورت صحیح
        provider_stats = (
            db.query(
                AIServiceUsage.provider,
                func.count(AIServiceUsage.id).label("total_requests"),
                func.sum(AIServiceUsage.tokens_used).label("total_tokens"),
                func.avg(AIServiceUsage.request_duration_ms).label("avg_duration_ms"),
                func.sum(
                    case(
                        (AIServiceUsage.success == True, 1),
                        else_=0
                    )
                ).label("success_count"),
                func.sum(
                    case(
                        (AIServiceUsage.success == False, 1),
                        else_=0
                    )
                ).label("failure_count"),
            )
            .filter(AIServiceUsage.request_timestamp >= cutoff_date)
            .group_by(AIServiceUsage.provider)
            .all()
        )

        model_stats = (
            db.query(
                AIServiceUsage.model,
                func.count(AIServiceUsage.id).label("total_requests"),
                func.sum(AIServiceUsage.tokens_used).label("total_tokens"),
                func.sum(AIServiceUsage.question_count).label("total_questions_generated"),
            )
            .filter(AIServiceUsage.request_timestamp >= cutoff_date)
            .group_by(AIServiceUsage.model)
            .all()
        )

        type_stats = (
            db.query(
                AIServiceUsage.request_type,
                func.count(AIServiceUsage.id).label("total_requests"),
                func.sum(AIServiceUsage.tokens_used).label("total_tokens"),
            )
            .filter(AIServiceUsage.request_timestamp >= cutoff_date)
            .group_by(AIServiceUsage.request_type)
            .all()
        )

        total_stats = (
            db.query(
                func.count(AIServiceUsage.id).label("total_requests"),
                func.sum(AIServiceUsage.tokens_used).label("total_tokens"),
                func.sum(AIServiceUsage.question_count).label("total_questions_generated"),
                func.avg(AIServiceUsage.request_duration_ms).label("avg_duration_ms"),
            )
            .filter(AIServiceUsage.request_timestamp >= cutoff_date)
            .first()
        )

        recent_requests = (
            db.query(AIServiceUsage)
            .order_by(AIServiceUsage.request_timestamp.desc())
            .limit(10)
            .all()
        )

        return {
            "period_days": days,
            "total": {
                "total_requests": total_stats.total_requests or 0,
                "total_tokens": total_stats.total_tokens or 0,
                "total_questions_generated": total_stats.total_questions_generated or 0,
                "avg_duration_ms": round(total_stats.avg_duration_ms or 0, 2),
            },
            "by_provider": [
                {
                    "provider": row.provider,
                    "total_requests": row.total_requests,
                    "total_tokens": row.total_tokens or 0,
                    "success_count": row.success_count,
                    "failure_count": row.failure_count,
                    "avg_duration_ms": round(row.avg_duration_ms or 0, 2),
                }
                for row in provider_stats
            ],
            "by_model": [
                {
                    "model": row.model,
                    "total_requests": row.total_requests,
                    "total_tokens": row.total_tokens or 0,
                    "total_questions_generated": row.total_questions_generated or 0,
                }
                for row in model_stats
            ],
            "by_request_type": [
                {
                    "request_type": row.request_type,
                    "total_requests": row.total_requests,
                    "total_tokens": row.total_tokens or 0,
                }
                for row in type_stats
            ],
            "recent_requests": [
                {
                    "id": req.id,
                    "provider": req.provider,
                    "model": req.model,
                    "request_type": req.request_type,
                    "tokens_used": req.tokens_used,
                    "success": req.success,
                    "error_message": req.error_message,
                    "timestamp": req.request_timestamp.isoformat(),
                    "duration_ms": req.request_duration_ms,
                }
                for req in recent_requests
            ],
        }

    except OperationalError as e:
        logger.error(f"Database operational error: {e}")
        # اگر جدول وجود نداشته باشد، پیام مناسب برمی‌گردانیم
        return {
            "period_days": days,
            "total": {
                "total_requests": 0,
                "total_tokens": 0,
                "total_questions_generated": 0,
                "avg_duration_ms": 0,
            },
            "by_provider": [],
            "by_model": [],
            "by_request_type": [],
            "recent_requests": [],
            "message": "هنوز آماری ثبت نشده است. برای استفاده از آمار، ابتدا از سرویس هوش مصنوعی استفاده کنید."
        }

    except Exception as e:
        logger.exception(f"Unexpected error in ai_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطای داخلی: {str(e)}"
        )


@router.get("/providers")
def get_available_providers(db: Session = Depends(get_db)):
    try:
        providers = (
            db.query(AIServiceUsage.provider)
            .distinct()
            .order_by(AIServiceUsage.provider)
            .all()
        )
        return {"providers": [p[0] for p in providers]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت ارائه‌دهندگان: {str(e)}"
        )