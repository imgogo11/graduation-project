from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_01"
down_revision = "20260413_01"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" in _table_names(inspector):
        return

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_username_snapshot", sa.String(length=64), nullable=True),
        sa.Column("actor_role", sa.String(length=16), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_label", sa.String(length=255), nullable=True),
        sa.Column("import_run_id", sa.Integer(), sa.ForeignKey("import_runs.id"), nullable=True),
        sa.Column("request_path", sa.String(length=255), nullable=True),
        sa.Column("http_method", sa.String(length=16), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)
    op.create_index("ix_audit_logs_category", "audit_logs", ["category"], unique=False)
    op.create_index("ix_audit_logs_category_success", "audit_logs", ["category", "success"], unique=False)
    op.create_index("ix_audit_logs_import_run_id", "audit_logs", ["import_run_id"], unique=False)
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"], unique=False)
    op.create_index("ix_audit_logs_success", "audit_logs", ["success"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in _table_names(inspector):
        return

    op.drop_index("ix_audit_logs_success", table_name="audit_logs")
    op.drop_index("ix_audit_logs_occurred_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_import_run_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_category_success", table_name="audit_logs")
    op.drop_index("ix_audit_logs_category", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
