from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260411_01"
down_revision = "20260409_02"
branch_labels = None
depends_on = None


def _get_column(inspector: sa.Inspector, table_name: str, column_name: str) -> dict[str, object] | None:
    for column in inspector.get_columns(table_name):
        if column["name"] == column_name:
            return column
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    amount_column = _get_column(inspector, "trading_records", "amount")
    if amount_column is None or amount_column.get("nullable"):
        return

    with op.batch_alter_table("trading_records") as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.Numeric(20, 4),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("trading_records") as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.Numeric(20, 4),
            nullable=False,
        )
