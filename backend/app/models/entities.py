# 作用:
# - 这是后端 ORM 实体定义模块，用来集中声明导入元数据层和业务真值层的数据库表结构。
# - 当前覆盖 import_runs / import_manifests / import_artifacts，以及股票、电商相关核心表。
# 关联文件:
# - 被 backend/app/core/database.py 建表与迁移流程依赖。
# - 被 backend/app/services/imports.py 作为批量入库目标。
# - 被 backend/app/repositories/*.py 和 backend/tests/test_database_pipeline.py 直接查询或验证。
#
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(128), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str] = mapped_column(String(255))
    source_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class StockSymbol(Base):
    __tablename__ = "stock_symbols"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    market: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class StockDailyPrice(Base):
    __tablename__ = "stock_daily_prices"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", "adjust", name="uq_stock_daily_prices_symbol_date_adjust"),
        Index("ix_stock_daily_prices_symbol_trade_date", "symbol", "trade_date"),
        Index("ix_stock_daily_prices_source_dataset", "source_dataset"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("stock_symbols.symbol"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    amplitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    change: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    adjust: Mapped[str] = mapped_column(String(16), default="none")
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128), default="akshare_a_share_daily")
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_source_dataset", "source_dataset"),)

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_unique_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_zip_code_prefix: Mapped[str | None] = mapped_column(String(32), nullable=True)
    signup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class Seller(Base):
    __tablename__ = "sellers"
    __table_args__ = (Index("ix_sellers_source_dataset", "source_dataset"),)

    seller_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seller_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seller_zip_code_prefix: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_source_dataset", "source_dataset"),)

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seller_id: Mapped[str | None] = mapped_column(ForeignKey("sellers.seller_id"), nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_category_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    product_category_name_english: Mapped[str | None] = mapped_column(String(128), nullable=True)
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    product_name_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_description_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_photos_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    product_length_cm: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    product_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    product_width_cm: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class ProductPriceHistory(Base):
    __tablename__ = "product_price_history"
    __table_args__ = (Index("ix_product_price_history_product_effective_at", "product_id", "effective_at"),)

    price_event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_source_dataset", "source_dataset"),
        Index("ix_orders_purchase_timestamp", "order_purchase_timestamp"),
    )

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.customer_id"), nullable=True, index=True)
    order_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    order_purchase_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    order_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    order_delivered_carrier_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    order_delivered_customer_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    order_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    order_estimated_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("ix_order_items_source_dataset", "source_dataset"),
    )

    order_item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.product_id"), nullable=True, index=True)
    seller_id: Mapped[str | None] = mapped_column(ForeignKey("sellers.seller_id"), nullable=True, index=True)
    source_item_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_limit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    freight_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    line_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_source_dataset", "source_dataset"),)

    payment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    payment_sequential: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payment_installments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("order_id", "review_id", name="uq_reviews_order_review_id"),
        Index("ix_reviews_source_dataset", "source_dataset"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    review_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_comment_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_comment_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_creation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    review_answer_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)


class UserEvent(Base):
    __tablename__ = "user_events"
    __table_args__ = (
        Index("ix_user_events_source_dataset", "source_dataset"),
        Index("ix_user_events_customer_occurred_at", "customer_id", "occurred_at"),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.customer_id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.product_id"), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.order_id"), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(128))
    import_run_id: Mapped[int | None] = mapped_column(ForeignKey("import_runs.id"), nullable=True, index=True)
