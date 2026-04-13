from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260413_01"
down_revision = "20260411_03"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name) if constraint.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "trading_records" not in _table_names(inspector):
        return

    columns = _column_names(inspector, "trading_records")
    with op.batch_alter_table("trading_records") as batch_op:
        if "instrument_code" in columns and "stock_code" not in columns:
            batch_op.alter_column("instrument_code", new_column_name="stock_code")
        if "instrument_name" in columns and "stock_name" not in columns:
            batch_op.alter_column("instrument_name", new_column_name="stock_name")

    inspector = sa.inspect(bind)
    index_names = _index_names(inspector, "trading_records")
    unique_names = _unique_constraint_names(inspector, "trading_records")

    if "ix_trading_records_run_code_date" in index_names:
        op.drop_index("ix_trading_records_run_code_date", table_name="trading_records")
    if "ix_trading_records_instrument_code" in index_names:
        op.drop_index("ix_trading_records_instrument_code", table_name="trading_records")
    if "uq_trading_records_run_code_date" in unique_names:
        op.drop_constraint("uq_trading_records_run_code_date", "trading_records", type_="unique")

    inspector = sa.inspect(bind)
    index_names = _index_names(inspector, "trading_records")
    unique_names = _unique_constraint_names(inspector, "trading_records")

    if "ix_trading_records_stock_code" not in index_names:
        op.create_index("ix_trading_records_stock_code", "trading_records", ["stock_code"], unique=False)
    if "ix_trading_records_run_stock_code_date" not in index_names:
        op.create_index(
            "ix_trading_records_run_stock_code_date",
            "trading_records",
            ["import_run_id", "stock_code", "trade_date"],
            unique=False,
        )
    if "uq_trading_records_run_stock_code_date" not in unique_names:
        op.create_unique_constraint(
            "uq_trading_records_run_stock_code_date",
            "trading_records",
            ["import_run_id", "stock_code", "trade_date"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "trading_records" not in _table_names(inspector):
        return

    index_names = _index_names(inspector, "trading_records")
    unique_names = _unique_constraint_names(inspector, "trading_records")

    if "ix_trading_records_run_stock_code_date" in index_names:
        op.drop_index("ix_trading_records_run_stock_code_date", table_name="trading_records")
    if "ix_trading_records_stock_code" in index_names:
        op.drop_index("ix_trading_records_stock_code", table_name="trading_records")
    if "uq_trading_records_run_stock_code_date" in unique_names:
        op.drop_constraint("uq_trading_records_run_stock_code_date", "trading_records", type_="unique")

    columns = _column_names(inspector, "trading_records")
    with op.batch_alter_table("trading_records") as batch_op:
        if "stock_code" in columns and "instrument_code" not in columns:
            batch_op.alter_column("stock_code", new_column_name="instrument_code")
        if "stock_name" in columns and "instrument_name" not in columns:
            batch_op.alter_column("stock_name", new_column_name="instrument_name")

    inspector = sa.inspect(bind)
    index_names = _index_names(inspector, "trading_records")
    unique_names = _unique_constraint_names(inspector, "trading_records")

    if "ix_trading_records_instrument_code" not in index_names:
        op.create_index("ix_trading_records_instrument_code", "trading_records", ["instrument_code"], unique=False)
    if "ix_trading_records_run_code_date" not in index_names:
        op.create_index(
            "ix_trading_records_run_code_date",
            "trading_records",
            ["import_run_id", "instrument_code", "trade_date"],
            unique=False,
        )
    if "uq_trading_records_run_code_date" not in unique_names:
        op.create_unique_constraint(
            "uq_trading_records_run_code_date",
            "trading_records",
            ["import_run_id", "instrument_code", "trade_date"],
        )
