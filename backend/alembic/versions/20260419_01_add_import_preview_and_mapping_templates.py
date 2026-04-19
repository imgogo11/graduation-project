from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_01"
down_revision = "20260417_01"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name) if constraint.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "import_preview_sessions" not in tables:
        op.create_table(
            "import_preview_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("dataset_name", sa.String(length=128), nullable=False),
            sa.Column("original_file_name", sa.String(length=255), nullable=False),
            sa.Column("file_format", sa.String(length=16), nullable=False),
            sa.Column("staged_file_path", sa.String(length=512), nullable=False),
            sa.Column("header_fingerprint", sa.String(length=128), nullable=False),
            sa.Column("preview_payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("committed_run_id", sa.Integer(), sa.ForeignKey("import_runs.id"), nullable=True),
        )
        op.create_index(
            "ix_import_preview_sessions_owner_status",
            "import_preview_sessions",
            ["owner_user_id", "status"],
            unique=False,
        )
        op.create_index("ix_import_preview_sessions_expires_at", "import_preview_sessions", ["expires_at"], unique=False)
        op.create_index(
            "ix_import_preview_sessions_header_fingerprint",
            "import_preview_sessions",
            ["header_fingerprint"],
            unique=False,
        )
        op.create_index(
            "ix_import_preview_sessions_committed_run_id",
            "import_preview_sessions",
            ["committed_run_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "import_mapping_templates" not in tables:
        op.create_table(
            "import_mapping_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("header_fingerprint", sa.String(length=128), nullable=False),
            sa.Column("mapping_json", sa.JSON(), nullable=False),
            sa.Column("usage_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_import_mapping_templates_owner_last_used",
            "import_mapping_templates",
            ["owner_user_id", "last_used_at"],
            unique=False,
        )
        op.create_index(
            "ix_import_mapping_templates_owner_user_id",
            "import_mapping_templates",
            ["owner_user_id"],
            unique=False,
        )
        op.create_index(
            "ix_import_mapping_templates_header_fingerprint",
            "import_mapping_templates",
            ["header_fingerprint"],
            unique=False,
        )
        op.create_unique_constraint(
            "uq_import_mapping_templates_owner_fingerprint",
            "import_mapping_templates",
            ["owner_user_id", "header_fingerprint"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "import_mapping_templates" in tables:
        index_names = _index_names(inspector, "import_mapping_templates")
        unique_names = _unique_constraint_names(inspector, "import_mapping_templates")
        if "uq_import_mapping_templates_owner_fingerprint" in unique_names:
            op.drop_constraint(
                "uq_import_mapping_templates_owner_fingerprint",
                "import_mapping_templates",
                type_="unique",
            )
        if "ix_import_mapping_templates_header_fingerprint" in index_names:
            op.drop_index("ix_import_mapping_templates_header_fingerprint", table_name="import_mapping_templates")
        if "ix_import_mapping_templates_owner_user_id" in index_names:
            op.drop_index("ix_import_mapping_templates_owner_user_id", table_name="import_mapping_templates")
        if "ix_import_mapping_templates_owner_last_used" in index_names:
            op.drop_index("ix_import_mapping_templates_owner_last_used", table_name="import_mapping_templates")
        op.drop_table("import_mapping_templates")

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "import_preview_sessions" in tables:
        index_names = _index_names(inspector, "import_preview_sessions")
        if "ix_import_preview_sessions_committed_run_id" in index_names:
            op.drop_index("ix_import_preview_sessions_committed_run_id", table_name="import_preview_sessions")
        if "ix_import_preview_sessions_header_fingerprint" in index_names:
            op.drop_index("ix_import_preview_sessions_header_fingerprint", table_name="import_preview_sessions")
        if "ix_import_preview_sessions_expires_at" in index_names:
            op.drop_index("ix_import_preview_sessions_expires_at", table_name="import_preview_sessions")
        if "ix_import_preview_sessions_owner_status" in index_names:
            op.drop_index("ix_import_preview_sessions_owner_status", table_name="import_preview_sessions")
        op.drop_table("import_preview_sessions")
