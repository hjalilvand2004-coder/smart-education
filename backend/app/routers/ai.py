from fastapi import APIRouter

from ..config import get_public_ai_settings


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


@router.get("/models")
def get_ai_models():
    return get_public_ai_settings()