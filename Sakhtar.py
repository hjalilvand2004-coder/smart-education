import os

# لیست نام پوشه‌ها و پیشوندهایی که نمی‌خواهیم نشان داده شوند
IGNORE_DIRS = {
    '.venv', 'venv', 'env', 'virtualenv',  # محیط مجازی
    '__pycache__', '.pytest_cache', '.mypy_cache',  # کش پایتون
    '.idea', '.vscode',  # تنظیمات IDE
    '.git',  # مخزن گیت
    'node_modules', 'dist', 'build',  # ابزارهای جاوااسکریپت/بیلد
    'logs', 'temp', 'tmp',  # لاگ و فایل موقت
    '.ipynb_checkpoints'  # کش ژوپیتر
}

# پسوند فایل‌هایی که نمی‌خواهیم (اختیاری)
IGNORE_EXTENSIONS = {'.pyc', '.pyo', '.so', '.dll', '.dylib', '.exe'}


def print_tree(start_path, prefix="", level=0, max_level=5):
    """چاپ درختواره فقط با فایل‌های پروژه"""
    if level > max_level:  # جلوگیری از رفتن به عمق زیاد
        return

    try:
        items = sorted(os.listdir(start_path))
    except PermissionError:
        return

    # فیلتر کردن آیتم‌های ناخواسته
    filtered_items = []
    for item in items:
        # نادیده گرفتن فایل‌های مخفی (شروع با .) به جز فایل‌های معمولی مثل .gitignore
        if item.startswith('.') and item not in ['.gitignore', '.env']:
            continue

        full_path = os.path.join(start_path, item)

        # اگر پوشه است و در لیست سیاه است، رد کن
        if os.path.isdir(full_path):
            if item in IGNORE_DIRS:
                continue
        # اگر فایل است و پسوندش در لیست سیاه است، رد کن
        else:
            _, ext = os.path.splitext(item)
            if ext in IGNORE_EXTENSIONS:
                continue

        filtered_items.append(item)

    for i, item in enumerate(filtered_items):
        path = os.path.join(start_path, item)
        is_last = (i == len(filtered_items) - 1)
        connector = "└── " if is_last else "├── "
        print(prefix + connector + item)

        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            print_tree(path, prefix + extension, level + 1, max_level)


if __name__ == "__main__":
    print("ساختار پروژه (فقط فایل‌های شما):\n")
    print_tree("backend")