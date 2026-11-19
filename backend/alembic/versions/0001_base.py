"""اسکریپت migration خالی الگو (نخستین revision روی PostgreSQL با autogenerate ساخته می‌شود)."""
revision = "0001_base"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # در استقرار Production:
    #   alembic revision --autogenerate -m init  →  alembic upgrade head
    pass


def downgrade() -> None:
    pass
