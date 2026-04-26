from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260422_01"
down_revision = "20260420_01"
branch_labels = None
depends_on = None


OPTIONAL_ANALYSIS_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("benchmark_close", sa.Numeric(18, 4)),
    ("pe_ttm", sa.Numeric(18, 6)),
    ("pb", sa.Numeric(18, 6)),
    ("roe", sa.Numeric(18, 6)),
    ("asset_liability_ratio", sa.Numeric(18, 6)),
    ("revenue_yoy", sa.Numeric(18, 6)),
    ("net_profit_yoy", sa.Numeric(18, 6)),
    ("valuation_as_of", sa.DateTime(timezone=False)),
    ("fundamental_report_date", sa.Date()),
)


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "trading_records" not in _table_names(inspector):
        return

    existing = _column_names(inspector, "trading_records")
    for column_name, column_type in OPTIONAL_ANALYSIS_COLUMNS:
        if column_name not in existing:
            op.add_column("trading_records", sa.Column(column_name, column_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "trading_records" not in _table_names(inspector):
        return

    existing = _column_names(inspector, "trading_records")
    for column_name, _ in reversed(OPTIONAL_ANALYSIS_COLUMNS):
        if column_name in existing:
            op.drop_column("trading_records", column_name)
