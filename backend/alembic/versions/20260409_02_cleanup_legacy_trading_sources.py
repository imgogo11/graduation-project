from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_02"
down_revision = "20260409_01"
branch_labels = None
depends_on = None


CURRENT_SOURCE_TYPE = "upload"
CURRENT_SOURCE_NAME = "user.upload"
LEGACY_TABLES = [
    "user_events",
    "reviews",
    "payments",
    "order_items",
    "orders",
    "product_price_history",
    "products",
    "sellers",
    "customers",
    "stock_daily_prices",
    "stock_symbols",
]


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    for table_name in LEGACY_TABLES:
        if table_name in tables:
            op.drop_table(table_name)

    tables = _table_names(sa.inspect(bind))
    if "import_runs" not in tables:
        return

    if "import_artifacts" in tables:
        op.execute(
            sa.text(
                """
                DELETE FROM import_artifacts
                WHERE import_run_id IN (
                    SELECT id
                    FROM import_runs
                    WHERE NOT (source_type = :source_type AND source_name = :source_name)
                )
                """
            ).bindparams(source_type=CURRENT_SOURCE_TYPE, source_name=CURRENT_SOURCE_NAME)
        )

    if "import_manifests" in tables:
        op.execute(
            sa.text(
                """
                DELETE FROM import_manifests
                WHERE import_run_id IN (
                    SELECT id
                    FROM import_runs
                    WHERE NOT (source_type = :source_type AND source_name = :source_name)
                )
                """
            ).bindparams(source_type=CURRENT_SOURCE_TYPE, source_name=CURRENT_SOURCE_NAME)
        )

    if "trading_records" in tables:
        op.execute(
            sa.text(
                """
                DELETE FROM trading_records
                WHERE import_run_id IN (
                    SELECT id
                    FROM import_runs
                    WHERE NOT (source_type = :source_type AND source_name = :source_name)
                )
                """
            ).bindparams(source_type=CURRENT_SOURCE_TYPE, source_name=CURRENT_SOURCE_NAME)
        )

    op.execute(
        sa.text(
            """
            DELETE FROM import_runs
            WHERE NOT (source_type = :source_type AND source_name = :source_name)
            """
        ).bindparams(source_type=CURRENT_SOURCE_TYPE, source_name=CURRENT_SOURCE_NAME)
    )


def downgrade() -> None:
    raise RuntimeError("Cleanup migration 20260409_02 is irreversible.")
