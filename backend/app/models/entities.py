from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportRun(Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        Index("ix_import_runs_owner_deleted_started", "owner_user_id", "deleted_at", "started_at"),
        Index(
            "uq_import_runs_owner_dataset_name_active_upload",
            "owner_user_id",
            "dataset_name",
            unique=True,
            sqlite_where=text(
                "owner_user_id IS NOT NULL AND deleted_at IS NULL AND status IN ('running', 'completed') "
                "AND source_type = 'upload' AND source_name = 'user.upload'"
            ),
            postgresql_where=text(
                "owner_user_id IS NOT NULL AND deleted_at IS NULL AND status IN ('running', 'completed') "
                "AND source_type = 'upload' AND source_name = 'user.upload'"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    dataset_name: Mapped[str] = mapped_column(String(128), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str] = mapped_column(String(255))
    source_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ImportManifestRecord(Base):
    __tablename__ = "import_manifests"
    __table_args__ = (UniqueConstraint("import_run_id", name="uq_import_manifests_import_run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), index=True)
    manifest_path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    record_count: Mapped[int] = mapped_column(Integer)
    columns_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ImportArtifactRecord(Base):
    __tablename__ = "import_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), index=True)
    manifest_id: Mapped[int] = mapped_column(ForeignKey("import_manifests.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    path: Mapped[str] = mapped_column(String(512))
    row_count: Mapped[int] = mapped_column(Integer)
    columns_json: Mapped[list[str]] = mapped_column(JSON, default=list)


class TradingRecord(Base):
    __tablename__ = "trading_records"
    __table_args__ = (
        UniqueConstraint("import_run_id", "stock_code", "trade_date", name="uq_trading_records_run_stock_code_date"),
        Index("ix_trading_records_run_stock_code_date", "import_run_id", "stock_code", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), index=True)
    stock_code: Mapped[str] = mapped_column(String(64), index=True)
    stock_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

