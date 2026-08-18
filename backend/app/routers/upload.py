from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
import os
import shutil
import uuid
from datetime import datetime

router = APIRouter(prefix="/upload", tags=["Upload"])

# پوشه ذخیره تصاویر
UPLOAD_DIR = "uploads/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# حداکثر حجم مجاز (به بایت) – پیش‌فرض ۵ مگابایت
MAX_FILE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", 5 * 1024 * 1024))

# پسوندهای مجاز
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}

@router.post("/image")
async def upload_image(request: Request, image: UploadFile = File(...)):
    """
    آپلود تصویر و برگرداندن آدرس کامل برای درج در ویرایشگر.
    """
    # اعتبارسنجی نوع فایل (MIME type)
    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="فایل ارسالی باید از نوع تصویر باشد (MIME type معتبر)."
        )

    # بررسی پسوند فایل
    file_extension = os.path.splitext(image.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"پسوند فایل مجاز نیست. پسوندهای مجاز: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # بررسی حجم فایل (با خواندن محتوای واقعی)
    # برای جلوگیری از بارگذاری کامل در حافظه، ابتدا چند بایت می‌خوانیم، اما روش مطمئن‌تر:
    # در FastAPI می‌توانیم از `image.size` استفاده کنیم (اگر تنظیم شده باشد) اما بهتر است خودمان حساب کنیم.
    # در اینجا به‌صورت ساده حجم را با خواندن کل فایل محاسبه می‌کنیم (برای فایل‌های کوچک مشکلی ندارد).
    # اما برای فایل‌های بزرگ بهتر است از روش streaming استفاده شود.
    # برای سادگی، حجم را با خواندن محتوا محاسبه می‌کنیم.
    content = await image.read()
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,  # Payload Too Large
            detail=f"حجم فایل بیش از حد مجاز است. حداکثر {MAX_FILE_SIZE // (1024*1024)} مگابایت مجاز است."
        )

    # تولید نام یکتا
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        # ذخیره فایل (با استفاده از محتوای خوانده شده)
        with open(file_path, "wb") as buffer:
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطا در ذخیره فایل روی سرور: {str(e)}")

    # ساخت آدرس کامل تصویر
    base_url = str(request.base_url).rstrip("/")
    image_url = f"{base_url}/uploads/images/{unique_name}"

    # برگرداندن پاسخ موفق
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "url": image_url,
            "filename": unique_name,
            "message": "تصویر با موفقیت آپلود شد."
        }
    )