"""نسخه ۳.۴ — جدول‌های یکپارچگی کامل پایه‌یار۳۶۰: رونوشت عمومی masterdata
(دامنه‌های گسترش‌یافته سند فنی) و صندوق ورودی رویدادهای RabbitMQ
(smart_learning_event_inbox — پردازش idempotent با event_id).

Revision ID: 0003_payehyar_events
Revises: 0002_journey_v310
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_payehyar_events"
down_revision = "0002_journey_v310"
branch_labels = None
depends_on = None


def _uuid_col():
    return sa.dialects.postgresql.UUID(as_uuid=True)()


def upgrade() -> None:
    op.create_table(
        "payehyar_masterdata_records",
        sa.Column("id", _uuid_col(), primary_key=True),
        sa.Column("domain", sa.String(64), index=True, nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False, index=True),
        sa.Column("code", sa.String(128), nullable=True, index=True),
        sa.Column("title", sa.String(512), nullable=True, index=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True, index=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="payehyar360"),
        sa.Column("source_route", sa.String(32), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("domain", "external_id", name="uq_payehyar_domain_extid"),
    )
    op.create_table(
        "smart_learning_event_inbox",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("routing_key", sa.String(128), nullable=True, index=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING", index=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("smart_learning_event_inbox")
    op.drop_table("payehyar_masterdata_records")
