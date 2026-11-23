"""اسکریپت دمو — فراخوانی سرویس درون‌برنامه‌ای (app/services/demo_seed.py).

اجرا:  python scripts/seed_demo.py   (پس از scripts/init_db.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.demo_seed import seed_demo_data  # noqa: E402

if __name__ == "__main__":
    seed_demo_data()
