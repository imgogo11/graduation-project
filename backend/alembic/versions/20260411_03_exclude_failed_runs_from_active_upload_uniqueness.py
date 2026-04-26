from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260411_03"
down_revision = "20260411_02"
branch_labels = None
depends_on = None


UPGRADED_ACTIVE_UPLOAD_FILTER = (
    "owner_user_id IS NOT NULL "
    "AND deleted_at IS NULL "
    "AND status IN ('running', 'completed') "
    "AND source_type = 'upload' "
    "AND source_name = 'user.upload'"
)
DOWNGRADED_ACTIVE_UPLOAD_FILTER = (
    "owner_user_id IS NOT NULL "
    "AND deleted_at IS NULL "
    "AND source_type = 'upload' "
    "AND source_name = 'user.upload'"
)


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _active_duplicate_dataset_names(bind: sa.Connection) -> list[sa.Row]:
    return list(
        bind.execute(
            sa.text(
                f"""
                SELECT owner_user_id, dataset_name, COUNT(*) AS row_count
                FROM import_runs
                WHERE {UPGRADED_ACTIVE_UPLOAD_FILTER}
                GROUP BY owner_user_id, dataset_name
                HAVING COUNT(*) > 1
                ORDER BY owner_user_id, dataset_name
                """
            )
        )
    )


def _recreate_index(filter_sql: str) -> None:
    op.create_index(
        "uq_import_runs_owner_dataset_name_active_upload",
        "import_runs",
        ["owner_user_id", "dataset_name"],
        unique=True,
        postgresql_where=sa.text(filter_sql),
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
            "Cannot narrow active dataset-name uniqueness until duplicate running/completed uploads are cleaned up: "
            f"{preview}"
        )

    if "uq_import_runs_owner_dataset_name_active_upload" in _index_names(inspector, "import_runs"):
        op.drop_index("uq_import_runs_owner_dataset_name_active_upload", table_name="import_runs")

    _recreate_index(UPGRADED_ACTIVE_UPLOAD_FILTER)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "import_runs" not in _table_names(inspector):
        return

    if "uq_import_runs_owner_dataset_name_active_upload" in _index_names(inspector, "import_runs"):
        op.drop_index("uq_import_runs_owner_dataset_name_active_upload", table_name="import_runs")

    _recreate_index(DOWNGRADED_ACTIVE_UPLOAD_FILTER)
