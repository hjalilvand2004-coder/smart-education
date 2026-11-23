"""نسخه ۳.۱ — مدل‌های «مسیر یادگیری»، کلینیک خطا، «به من یاد بده»، جلسه یادگیری،
آمادگی آزمون و همگام‌سازی مرجع پایه‌یار۳۶۰.

Revision ID: 0002_journey_v310
Revises: 0001_base
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_journey_v310"
down_revision = "0001_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reference_sync_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)(), primary_key=True),
        sa.Column("course_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("courses.id"), index=True),
        sa.Column("direction", sa.String(16), index=True),
        sa.Column("status", sa.String(16), index=True),
        sa.Column("reference_system", sa.String(32)),
        sa.Column("reference_version", sa.String(32), nullable=True),
        sa.Column("new_syllabus_version_id", sa.dialects.postgresql.UUID(as_uuid=True)(), nullable=True),
        sa.Column("report", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("synced_by", sa.dialects.postgresql.UUID(as_uuid=True)(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "stuck_marks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)(), primary_key=True),
        sa.Column("learner_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("users.id"), index=True),
        sa.Column("course_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("courses.id"), index=True),
        sa.Column("content_version_id", sa.dialects.postgresql.UUID(as_uuid=True)(), nullable=True, index=True),
        sa.Column("block_index", sa.Integer(), nullable=True),
        sa.Column("block_anchor", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(32), index=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=True),
        sa.Column("tutor_session_id", sa.dialects.postgresql.UUID(as_uuid=True)(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "error_notebook_entries",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)(), primary_key=True),
        sa.Column("learner_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("users.id"), index=True),
        sa.Column("course_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("courses.id"), index=True),
        sa.Column("concept_id", sa.dialects.postgresql.UUID(as_uuid=True)(), nullable=True, index=True),
        sa.Column("pattern_key", sa.String(64), index=True),
        sa.Column("title", sa.String(200)),
        sa.Column("evidence", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("suggested_practice", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), index=True),
        sa.Column("student_explanation", sa.Text(), nullable=True),
        sa.Column("recurrence_count", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("learner_id", "course_id", "concept_id", "pattern_key", name="uq_error_note"),
    )
    op.create_table(
        "teach_back_submissions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)(), primary_key=True),
        sa.Column("learner_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("users.id"), index=True),
        sa.Column("course_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("courses.id"), index=True),
        sa.Column("concept_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("concepts.id"), index=True),
        sa.Column("modality", sa.String(8)),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("audio_path", sa.String(500), nullable=True),
        sa.Column("rubric", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("follow_up_question", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "learning_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)(), primary_key=True),
        sa.Column("learner_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("users.id"), index=True),
        sa.Column("course_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("courses.id"), index=True),
        sa.Column("minutes", sa.Integer()),
        sa.Column("composition", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("state", sa.String(12), index=True),
        sa.Column("progress", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "exam_prep_plans",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)(), primary_key=True),
        sa.Column("learner_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("users.id"), index=True),
        sa.Column("course_id", sa.dialects.postgresql.UUID(as_uuid=True)(), sa.ForeignKey("courses.id"), index=True),
        sa.Column("exam_date", sa.String(10), nullable=True),
        sa.Column("available_minutes", sa.Integer(), nullable=True),
        sa.Column("plan", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    # ستون‌های رونوشت مرجع
    for col in ("reference_system", "reference_id", "reference_version", "owner_system", "sync_state"):
        op.add_column("courses", sa.Column(col, sa.String(64) if col == "reference_id" else sa.String(32), nullable=True))
    op.add_column("courses", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("syllabus_versions", sa.Column("reference_version", sa.String(32), nullable=True))
    op.add_column("syllabus_topics", sa.Column("reference_id", sa.String(64), nullable=True))
    op.add_column("topic_concepts", sa.Column("needs_review", sa.Boolean(), nullable=True))
    op.add_column("topic_concepts", sa.Column("review_reason", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("topic_concepts", "review_reason")
    op.drop_column("topic_concepts", "needs_review")
    op.drop_column("syllabus_topics", "reference_id")
    op.drop_column("syllabus_versions", "reference_version")
    op.drop_column("courses", "last_synced_at")
    for col in ("sync_state", "owner_system", "reference_version", "reference_id", "reference_system"):
        op.drop_column("courses", col)
    for t in ("exam_prep_plans", "learning_sessions", "teach_back_submissions",
              "error_notebook_entries", "stuck_marks", "reference_sync_logs"):
        op.drop_table(t)
