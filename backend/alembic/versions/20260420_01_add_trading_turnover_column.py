from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_01"
down_revision = "20260419_01"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "trading_records" not in tables:
        return

    columns = _column_names(inspector, "trading_records")
    if "turnover" not in columns:
        op.add_column("trading_records", sa.Column("turnover", sa.Numeric(18, 6), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "trading_records" not in tables:
        return

    columns = _column_names(inspector, "trading_records")
    if "turnover" in columns:
        op.drop_column("trading_records", "turnover")
