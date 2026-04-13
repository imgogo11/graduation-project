from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from collections import defaultdict


revision = "20260411_02"
down_revision = "20260411_01"
branch_labels = None
depends_on = None


MAX_DATASET_NAME_LENGTH = 128
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


def _active_upload_rows(bind: sa.Connection) -> list[sa.RowMapping]:
    return list(
        bind.execute(
            sa.text(
                f"""
                SELECT id, owner_user_id, dataset_name, started_at
                FROM import_runs
                WHERE {ACTIVE_UPLOAD_FILTER}
                ORDER BY owner_user_id, dataset_name, started_at DESC, id DESC
                """
            )
        ).mappings()
    )


def _build_renamed_dataset_name(dataset_name: str, run_id: int, existing_names: set[str]) -> str:
    sequence = 0
    while True:
        suffix = f"__legacy_{run_id}" if sequence == 0 else f"__legacy_{run_id}_{sequence}"
        available_length = MAX_DATASET_NAME_LENGTH - len(suffix)
        normalized_base = dataset_name[:available_length] if available_length > 0 else ""
        candidate = f"{normalized_base}{suffix}"
        if candidate not in existing_names:
            return candidate
        sequence += 1


def _rename_active_duplicate_dataset_names(bind: sa.Connection) -> None:
    rows = _active_upload_rows(bind)
    rows_by_group: dict[tuple[int, str], list[sa.RowMapping]] = defaultdict(list)
    existing_names_by_owner: dict[int, set[str]] = defaultdict(set)

    for row in rows:
        owner_user_id = int(row["owner_user_id"])
        dataset_name = str(row["dataset_name"])
        rows_by_group[(owner_user_id, dataset_name)].append(row)
        existing_names_by_owner[owner_user_id].add(dataset_name)

    for (owner_user_id, _dataset_name), grouped_rows in rows_by_group.items():
        if len(grouped_rows) <= 1:
            continue

        owner_existing_names = existing_names_by_owner[owner_user_id]
        for row in grouped_rows[1:]:
            original_name = str(row["dataset_name"])
            new_name = _build_renamed_dataset_name(original_name, int(row["id"]), owner_existing_names)
            bind.execute(
                sa.text(
                    """
                    UPDATE import_runs
                    SET dataset_name = :dataset_name
                    WHERE id = :run_id
                    """
                ),
                {
                    "dataset_name": new_name,
                    "run_id": int(row["id"]),
                },
            )
            owner_existing_names.add(new_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "import_runs" not in _table_names(inspector):
        return

    duplicates = _active_duplicate_dataset_names(bind)
    if duplicates:
        _rename_active_duplicate_dataset_names(bind)

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
