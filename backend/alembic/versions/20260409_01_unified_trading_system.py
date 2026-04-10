from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_01"
down_revision = "20260407_01"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _has_foreign_key(inspector: sa.Inspector, table_name: str, constrained_columns: list[str]) -> bool:
    expected = tuple(constrained_columns)
    for foreign_key in inspector.get_foreign_keys(table_name):
        if tuple(foreign_key.get("constrained_columns", [])) == expected:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("username", name="uq_users_username"),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.create_index("ix_users_role", "users", ["role"], unique=False)

    inspector = sa.inspect(bind)
    if "import_runs" in _table_names(inspector):
        columns = _column_names(inspector, "import_runs")
        if "owner_user_id" not in columns:
            op.add_column("import_runs", sa.Column("owner_user_id", sa.Integer(), nullable=True))
        if "asset_class" not in columns:
            op.add_column("import_runs", sa.Column("asset_class", sa.String(length=32), nullable=True))
        if "original_file_name" not in columns:
            op.add_column("import_runs", sa.Column("original_file_name", sa.String(length=255), nullable=True))
        if "file_format" not in columns:
            op.add_column("import_runs", sa.Column("file_format", sa.String(length=16), nullable=True))
        if "deleted_at" not in columns:
            op.add_column("import_runs", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

        inspector = sa.inspect(bind)
        if not _has_foreign_key(inspector, "import_runs", ["owner_user_id"]):
            op.create_foreign_key(
                "fk_import_runs_owner_user_id_users",
                "import_runs",
                "users",
                ["owner_user_id"],
                ["id"],
            )

        index_names = _index_names(inspector, "import_runs")
        if "ix_import_runs_owner_user_id" not in index_names:
            op.create_index("ix_import_runs_owner_user_id", "import_runs", ["owner_user_id"], unique=False)
        if "ix_import_runs_asset_class" not in index_names:
            op.create_index("ix_import_runs_asset_class", "import_runs", ["asset_class"], unique=False)
        if "ix_import_runs_owner_deleted_started" not in index_names:
            op.create_index(
                "ix_import_runs_owner_deleted_started",
                "import_runs",
                ["owner_user_id", "deleted_at", "started_at"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if "trading_records" not in _table_names(inspector):
        op.create_table(
            "trading_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("import_run_id", sa.Integer(), nullable=False),
            sa.Column("instrument_code", sa.String(length=64), nullable=False),
            sa.Column("instrument_name", sa.String(length=255), nullable=True),
            sa.Column("trade_date", sa.Date(), nullable=False),
            sa.Column("open", sa.Numeric(18, 4), nullable=False),
            sa.Column("high", sa.Numeric(18, 4), nullable=False),
            sa.Column("low", sa.Numeric(18, 4), nullable=False),
            sa.Column("close", sa.Numeric(18, 4), nullable=False),
            sa.Column("volume", sa.Numeric(20, 4), nullable=False),
            sa.Column("amount", sa.Numeric(20, 4), nullable=False),
            sa.ForeignKeyConstraint(["import_run_id"], ["import_runs.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "import_run_id",
                "instrument_code",
                "trade_date",
                name="uq_trading_records_run_code_date",
            ),
        )
        op.create_index("ix_trading_records_import_run_id", "trading_records", ["import_run_id"], unique=False)
        op.create_index("ix_trading_records_instrument_code", "trading_records", ["instrument_code"], unique=False)
        op.create_index("ix_trading_records_trade_date", "trading_records", ["trade_date"], unique=False)
        op.create_index(
            "ix_trading_records_run_code_date",
            "trading_records",
            ["import_run_id", "instrument_code", "trade_date"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "trading_records" in tables:
        op.drop_index("ix_trading_records_run_code_date", table_name="trading_records")
        op.drop_index("ix_trading_records_trade_date", table_name="trading_records")
        op.drop_index("ix_trading_records_instrument_code", table_name="trading_records")
        op.drop_index("ix_trading_records_import_run_id", table_name="trading_records")
        op.drop_table("trading_records")

    if "import_runs" in tables:
        index_names = _index_names(inspector, "import_runs")
        if "ix_import_runs_owner_deleted_started" in index_names:
            op.drop_index("ix_import_runs_owner_deleted_started", table_name="import_runs")
        if "ix_import_runs_asset_class" in index_names:
            op.drop_index("ix_import_runs_asset_class", table_name="import_runs")
        if "ix_import_runs_owner_user_id" in index_names:
            op.drop_index("ix_import_runs_owner_user_id", table_name="import_runs")

        columns = _column_names(inspector, "import_runs")
        if "deleted_at" in columns:
            op.drop_column("import_runs", "deleted_at")
        if "file_format" in columns:
            op.drop_column("import_runs", "file_format")
        if "original_file_name" in columns:
            op.drop_column("import_runs", "original_file_name")
        if "asset_class" in columns:
            op.drop_column("import_runs", "asset_class")
        if "owner_user_id" in columns:
            op.drop_column("import_runs", "owner_user_id")

    if "users" in tables:
        op.drop_index("ix_users_role", table_name="users")
        op.drop_index("ix_users_username", table_name="users")
        op.drop_table("users")
