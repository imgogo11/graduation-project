from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260411_02"
down_revision = "20260411_01"
branch_labels = None
depends_on = None


ACTIVE_UPLOAD_FILTER = (
    "owner_user_id IS NOT NULL "
    "AND deleted_at IS NULL "
    "AND source_type = 'upload' "
    "AND source_name = 'user.upload'"
)
ACTIVE_UPLOAD_FILTER_SQL = sa.text(ACTIVE_UPLOAD_FILTER)


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _active_duplicate_dataset_names(bind: sa.Connection) -> list[sa.Row]:
    return list(
        bind.execute(
            sa.text(
                f"""
                SELECT owner_user_id, dataset_name, COUNT(*) AS row_count
                FROM import_runs
                WHERE {ACTIVE_UPLOAD_FILTER}
                GROUP BY owner_user_id, dataset_name
                HAVING COUNT(*) > 1
                ORDER BY owner_user_id, dataset_name
                """
            )
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "import_runs" not in _table_names(inspector):
        return

    duplicates = _active_duplicate_dataset_names(bind)
    if duplicates:
        preview = ", ".join(
            f"owner_user_id={row.owner_user_id} dataset_name={row.dataset_name!r} count={row.row_count}"
            for row in duplicates[:5]
        )
        raise RuntimeError(
            "Cannot enforce active dataset-name uniqueness until duplicate upload runs are cleaned up: "
            f"{preview}"
        )

    index_names = _index_names(inspector, "import_runs")
    if "ix_import_runs_asset_class" in index_names:
        op.drop_index("ix_import_runs_asset_class", table_name="import_runs")

    columns = _column_names(inspector, "import_runs")
    if "asset_class" in columns:
        with op.batch_alter_table("import_runs") as batch_op:
            batch_op.drop_column("asset_class")

    inspector = sa.inspect(bind)
    index_names = _index_names(inspector, "import_runs")
    if "uq_import_runs_owner_dataset_name_active_upload" not in index_names:
        op.create_index(
            "uq_import_runs_owner_dataset_name_active_upload",
            "import_runs",
            ["owner_user_id", "dataset_name"],
            unique=True,
            sqlite_where=ACTIVE_UPLOAD_FILTER_SQL,
            postgresql_where=ACTIVE_UPLOAD_FILTER_SQL,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "import_runs" not in _table_names(inspector):
        return

    index_names = _index_names(inspector, "import_runs")
    if "uq_import_runs_owner_dataset_name_active_upload" in index_names:
        op.drop_index("uq_import_runs_owner_dataset_name_active_upload", table_name="import_runs")

    columns = _column_names(inspector, "import_runs")
    if "asset_class" not in columns:
        with op.batch_alter_table("import_runs") as batch_op:
            batch_op.add_column(sa.Column("asset_class", sa.String(length=32), nullable=True))

    inspector = sa.inspect(bind)
    index_names = _index_names(inspector, "import_runs")
    if "ix_import_runs_asset_class" not in index_names:
        op.create_index("ix_import_runs_asset_class", "import_runs", ["asset_class"], unique=False)
