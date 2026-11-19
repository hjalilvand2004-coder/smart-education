"""ساخت جداول برای توسعه/آزمون (create_all).

در استقرار Production از Alembic استفاده شود:
    alembic revision --autogenerate -m init && alembic upgrade head
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401


def main() -> None:
    Path("data").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)
    tables = sorted(Base.metadata.tables.keys())
    print(f"Created {len(tables)} tables in {engine.url}")


if __name__ == "__main__":
    main()
