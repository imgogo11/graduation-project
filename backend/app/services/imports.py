# 作用:
# - 这是数据导入服务模块，用来编排 manifest 读取、导入记录写入、CSV 解析和 ORM 批量入库流程。
# - 当前覆盖 AkShare 股票快照、Olist 电商数据、Synthetic 电商数据三条导入链路。
# 关联文件:
# - 被 backend/app/api/routes/imports.py 和 backend/scripts/import_data.py 直接调用。
# - 依赖 backend/app/repositories/imports.py、stocks.py 以及 backend/app/models/ 中的 ORM 实体。
# - 对应集成测试位于 backend/tests/test_database_pipeline.py。
#
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    ImportRun,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductPriceHistory,
    Review,
    Seller,
    StockDailyPrice,
    UserEvent,
)
from app.repositories.imports import ImportRunRepository
from app.repositories.stocks import StockRepository


class ImportExecutionError(RuntimeError):
    def __init__(self, run_id: int, message: str):
        self.run_id = run_id
        super().__init__(message)


@dataclass(slots=True)
class ManifestBundle:
    path: Path
    payload: dict[str, Any]

    @property
    def dataset_name(self) -> str:
        return str(self.payload["dataset_name"])

    @property
    def source_type(self) -> str:
        return str(self.payload["source_type"])

    @property
    def source_name(self) -> str:
        return str(self.payload["source_name"])

    @property
    def source_uri(self) -> str | None:
        value = self.payload.get("source_uri")
        return str(value) if value else None

    @property
    def record_count(self) -> int:
        return int(self.payload.get("record_count", 0))

    @property
    def created_at(self) -> datetime:
        return datetime.fromisoformat(str(self.payload["created_at"]))

    @property
    def columns(self) -> list[str]:
        return list(self.payload.get("columns", []))

    @property
    def metadata(self) -> dict[str, Any]:
        value = self.payload.get("metadata", {})
        return value if isinstance(value, dict) else {}

    @property
    def artifacts(self) -> list[dict[str, Any]]:
        return list(self.payload.get("artifacts", []))


class ImportService:
    def import_stock_manifest(self, session: Session, manifest_path: Path) -> ImportRun:
        manifest = self._load_manifest(manifest_path)
        return self._execute_import(session, manifest, self._load_stock_dataset)

    def import_olist_manifest(self, session: Session, manifest_path: Path) -> ImportRun:
        manifest = self._load_manifest(manifest_path)
        return self._execute_import(session, manifest, self._load_olist_dataset)

    def import_synthetic_manifest(self, session: Session, manifest_path: Path) -> ImportRun:
        manifest = self._load_manifest(manifest_path)
        return self._execute_import(session, manifest, self._load_synthetic_dataset)

    def _execute_import(
        self,
        session: Session,
        manifest: ManifestBundle,
        loader: Callable[[Session, ManifestBundle, int], None],
    ) -> ImportRun:
        run = ImportRunRepository.create_run(
            session,
            dataset_name=manifest.dataset_name,
            source_type=manifest.source_type,
            source_name=manifest.source_name,
            source_uri=manifest.source_uri,
            metadata_json={"manifest_path": str(manifest.path), **manifest.metadata},
        )
        try:
            manifest_record = ImportRunRepository.add_manifest(
                session,
                import_run_id=run.id,
                manifest_path=str(manifest.path),
                created_at=manifest.created_at,
                record_count=manifest.record_count,
                columns_json=manifest.columns,
                metadata_json=manifest.metadata,
            )
            for artifact in manifest.artifacts:
                ImportRunRepository.add_artifact(
                    session,
                    import_run_id=run.id,
                    manifest_id=manifest_record.id,
                    name=str(artifact["name"]),
                    path=str(artifact["path"]),
                    row_count=int(artifact.get("rows", 0)),
                    columns_json=list(artifact.get("columns", [])),
                )
            loader(session, manifest, run.id)
            ImportRunRepository.mark_completed(session, run, record_count=manifest.record_count)
            session.commit()
            session.refresh(run)
            return run
        except Exception as exc:
            session.rollback()
            ImportRunRepository.mark_failed(session, run_id=run.id, error_message=str(exc))
            raise ImportExecutionError(run.id, str(exc)) from exc

    def _load_stock_dataset(self, session: Session, manifest: ManifestBundle, run_id: int) -> None:
        session.execute(delete(StockDailyPrice).where(StockDailyPrice.source_dataset == manifest.dataset_name))

        symbol_rows: list[dict[str, str | int | None]] = []
        price_rows: list[dict[str, Any]] = []
        for artifact in manifest.artifacts:
            frame = pd.read_csv(Path(str(artifact["path"])), dtype={"symbol": str, "股票代码": str})
            if "股票代码" in frame.columns:
                frame = frame.drop(columns=["股票代码"])
            if frame.empty:
                continue

            symbol = str(frame.iloc[0]["symbol"])
            symbol_rows.append(
                {
                    "symbol": symbol,
                    "market": self._infer_stock_market(symbol),
                    "last_import_run_id": run_id,
                }
            )
            for raw in frame.to_dict(orient="records"):
                price_rows.append(
                    {
                        "symbol": str(raw["symbol"]),
                        "trade_date": self._parse_date(raw.get("trade_date")),
                        "open": self._to_decimal(raw.get("open")) or Decimal("0"),
                        "close": self._to_decimal(raw.get("close")) or Decimal("0"),
                        "high": self._to_decimal(raw.get("high")) or Decimal("0"),
                        "low": self._to_decimal(raw.get("low")) or Decimal("0"),
                        "volume": self._to_decimal(raw.get("volume")) or Decimal("0"),
                        "amount": self._to_decimal(raw.get("amount")),
                        "amplitude": self._to_decimal(raw.get("amplitude")),
                        "pct_change": self._to_decimal(raw.get("pct_change")),
                        "change": self._to_decimal(raw.get("change")),
                        "turnover": self._to_decimal(raw.get("turnover")),
                        "adjust": str(raw.get("adjust", "none") or "none"),
                        "source_type": str(raw.get("source_type") or manifest.source_type),
                        "source_dataset": manifest.dataset_name,
                        "import_run_id": run_id,
                    }
                )

        StockRepository.ensure_symbols(session, symbols=symbol_rows)
        self._bulk_insert(session, StockDailyPrice, price_rows)

    def _load_olist_dataset(self, session: Session, manifest: ManifestBundle, run_id: int) -> None:
        self._delete_existing_ecommerce_dataset(session, manifest.dataset_name)
        artifact_map = {str(item["name"]): Path(str(item["path"])) for item in manifest.artifacts}

        translations: dict[str, str] = {}
        if "category_translation" in artifact_map:
            translation_frame = pd.read_csv(artifact_map["category_translation"])
            translations = {
                str(row["product_category_name"]): str(row["product_category_name_english"])
                for row in translation_frame.to_dict(orient="records")
            }

        customers = pd.read_csv(artifact_map["customers"])
        sellers = pd.read_csv(artifact_map["sellers"])
        products = pd.read_csv(artifact_map["products"])
        orders = pd.read_csv(artifact_map["orders"])
        order_items = pd.read_csv(artifact_map["order_items"])
        payments = pd.read_csv(artifact_map["payments"])
        reviews = pd.read_csv(artifact_map["reviews"])

        customer_rows = [
            {
                "customer_id": str(row["customer_id"]),
                "customer_unique_id": self._to_str(row.get("customer_unique_id")),
                "customer_name": None,
                "customer_city": self._to_str(row.get("customer_city")),
                "customer_state": self._to_str(row.get("customer_state")),
                "customer_zip_code_prefix": self._to_str(row.get("customer_zip_code_prefix")),
                "signup_at": None,
                "source_type": manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in customers.to_dict(orient="records")
        ]
        seller_rows = [
            {
                "seller_id": str(row["seller_id"]),
                "seller_name": None,
                "seller_city": self._to_str(row.get("seller_city")),
                "seller_state": self._to_str(row.get("seller_state")),
                "seller_zip_code_prefix": self._to_str(row.get("seller_zip_code_prefix")),
                "source_type": manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in sellers.to_dict(orient="records")
        ]
        product_rows = [
            {
                "product_id": str(row["product_id"]),
                "seller_id": None,
                "product_name": None,
                "product_category_name": self._to_str(row.get("product_category_name")),
                "product_category_name_english": translations.get(str(row.get("product_category_name"))),
                "base_price": None,
                "product_name_length": self._to_int(row.get("product_name_lenght")),
                "product_description_length": self._to_int(row.get("product_description_lenght")),
                "product_photos_qty": self._to_int(row.get("product_photos_qty")),
                "product_weight_g": self._to_decimal(row.get("product_weight_g")),
                "product_length_cm": self._to_decimal(row.get("product_length_cm")),
                "product_height_cm": self._to_decimal(row.get("product_height_cm")),
                "product_width_cm": self._to_decimal(row.get("product_width_cm")),
                "created_at": None,
                "source_type": manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in products.to_dict(orient="records")
        ]
        order_rows = [
            {
                "order_id": str(row["order_id"]),
                "customer_id": self._to_str(row.get("customer_id")),
                "order_status": self._to_str(row.get("order_status")),
                "order_purchase_timestamp": self._parse_datetime(row.get("order_purchase_timestamp")),
                "order_approved_at": self._parse_datetime(row.get("order_approved_at")),
                "order_delivered_carrier_date": self._parse_datetime(row.get("order_delivered_carrier_date")),
                "order_delivered_customer_date": self._parse_datetime(row.get("order_delivered_customer_date")),
                "order_delivered_at": self._parse_datetime(row.get("order_delivered_customer_date")),
                "order_estimated_delivery_date": self._parse_datetime(row.get("order_estimated_delivery_date")),
                "total_amount": None,
                "source_type": manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in orders.to_dict(orient="records")
        ]

        order_item_rows: list[dict[str, Any]] = []
        for row in order_items.to_dict(orient="records"):
            item_index = self._to_int(row.get("order_item_id"))
            unit_price = self._to_decimal(row.get("price"))
            freight_value = self._to_decimal(row.get("freight_value"))
            order_item_rows.append(
                {
                    "order_item_id": f"{row['order_id']}-{item_index or 0:02d}",
                    "order_id": str(row["order_id"]),
                    "product_id": self._to_str(row.get("product_id")),
                    "seller_id": self._to_str(row.get("seller_id")),
                    "source_item_index": item_index,
                    "shipping_limit_date": self._parse_datetime(row.get("shipping_limit_date")),
                    "quantity": 1,
                    "unit_price": unit_price,
                    "freight_value": freight_value,
                    "line_amount": self._sum_decimals(unit_price, freight_value),
                    "source_type": manifest.source_type,
                    "source_dataset": manifest.dataset_name,
                    "import_run_id": run_id,
                }
            )

        payment_rows: list[dict[str, Any]] = []
        for row in payments.to_dict(orient="records"):
            sequence = self._to_int(row.get("payment_sequential")) or 0
            payment_rows.append(
                {
                    "payment_id": f"{row['order_id']}-{sequence:02d}",
                    "order_id": str(row["order_id"]),
                    "payment_sequential": sequence,
                    "payment_type": self._to_str(row.get("payment_type")),
                    "payment_installments": self._to_int(row.get("payment_installments")),
                    "payment_value": self._to_decimal(row.get("payment_value")),
                    "source_type": manifest.source_type,
                    "source_dataset": manifest.dataset_name,
                    "import_run_id": run_id,
                }
            )

        review_rows = [
            {
                "review_id": self._to_str(row.get("review_id")),
                "order_id": str(row["order_id"]),
                "review_score": self._to_int(row.get("review_score")),
                "review_comment_title": self._to_str(row.get("review_comment_title")),
                "review_comment_message": self._to_str(row.get("review_comment_message")),
                "review_creation_date": self._parse_datetime(row.get("review_creation_date")),
                "review_answer_timestamp": self._parse_datetime(row.get("review_answer_timestamp")),
                "source_type": manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in reviews.to_dict(orient="records")
        ]

        self._bulk_insert(session, Seller, seller_rows)
        self._bulk_insert(session, Customer, customer_rows)
        self._bulk_insert(session, Product, product_rows)
        self._bulk_insert(session, Order, order_rows)
        self._bulk_insert(session, OrderItem, order_item_rows)
        self._bulk_insert(session, Payment, payment_rows)
        self._bulk_insert(session, Review, review_rows)
        self._update_order_totals(session, dataset_name=manifest.dataset_name)

    def _load_synthetic_dataset(self, session: Session, manifest: ManifestBundle, run_id: int) -> None:
        self._delete_existing_ecommerce_dataset(session, manifest.dataset_name)
        artifact_map = {str(item["name"]): Path(str(item["path"])) for item in manifest.artifacts}

        customers = pd.read_csv(artifact_map["customers"])
        sellers = pd.read_csv(artifact_map["sellers"])
        products = pd.read_csv(artifact_map["products"])
        price_history = pd.read_csv(artifact_map["product_price_history"])
        orders = pd.read_csv(artifact_map["orders"])
        order_items = pd.read_csv(artifact_map["order_items"])
        payments = pd.read_csv(artifact_map["payments"])
        reviews = pd.read_csv(artifact_map["reviews"])
        user_events = pd.read_csv(artifact_map["user_events"])

        customer_rows = [
            {
                "customer_id": str(row["customer_id"]),
                "customer_unique_id": None,
                "customer_name": self._to_str(row.get("customer_name")),
                "customer_city": self._to_str(row.get("customer_city")),
                "customer_state": self._to_str(row.get("customer_state")),
                "customer_zip_code_prefix": None,
                "signup_at": self._parse_datetime(row.get("signup_at")),
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in customers.to_dict(orient="records")
        ]
        seller_rows = [
            {
                "seller_id": str(row["seller_id"]),
                "seller_name": self._to_str(row.get("seller_name")),
                "seller_city": self._to_str(row.get("seller_city")),
                "seller_state": self._to_str(row.get("seller_state")),
                "seller_zip_code_prefix": None,
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in sellers.to_dict(orient="records")
        ]
        product_rows = [
            {
                "product_id": str(row["product_id"]),
                "seller_id": self._to_str(row.get("seller_id")),
                "product_name": self._to_str(row.get("product_name")),
                "product_category_name": self._to_str(row.get("category")),
                "product_category_name_english": self._to_str(row.get("category")),
                "base_price": self._to_decimal(row.get("base_price")),
                "product_name_length": None,
                "product_description_length": None,
                "product_photos_qty": None,
                "product_weight_g": None,
                "product_length_cm": None,
                "product_height_cm": None,
                "product_width_cm": None,
                "created_at": self._parse_datetime(row.get("created_at")),
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in products.to_dict(orient="records")
        ]
        price_rows = [
            {
                "price_event_id": str(row["price_event_id"]),
                "product_id": str(row["product_id"]),
                "effective_at": self._parse_datetime(row.get("effective_at")) or datetime.min,
                "price": self._to_decimal(row.get("price")) or Decimal("0"),
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in price_history.to_dict(orient="records")
        ]
        order_rows = [
            {
                "order_id": str(row["order_id"]),
                "customer_id": self._to_str(row.get("customer_id")),
                "order_status": self._to_str(row.get("order_status")),
                "order_purchase_timestamp": self._parse_datetime(row.get("order_purchase_timestamp")),
                "order_approved_at": self._parse_datetime(row.get("order_approved_at")),
                "order_delivered_carrier_date": None,
                "order_delivered_customer_date": self._parse_datetime(row.get("order_delivered_at")),
                "order_delivered_at": self._parse_datetime(row.get("order_delivered_at")),
                "order_estimated_delivery_date": None,
                "total_amount": self._to_decimal(row.get("total_amount")),
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in orders.to_dict(orient="records")
        ]
        order_item_rows = [
            {
                "order_item_id": str(row["order_item_id"]),
                "order_id": str(row["order_id"]),
                "product_id": self._to_str(row.get("product_id")),
                "seller_id": self._to_str(row.get("seller_id")),
                "source_item_index": None,
                "shipping_limit_date": None,
                "quantity": self._to_int(row.get("quantity")),
                "unit_price": self._to_decimal(row.get("unit_price")),
                "freight_value": self._to_decimal(row.get("freight_value")),
                "line_amount": self._to_decimal(row.get("line_amount")),
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in order_items.to_dict(orient="records")
        ]
        payment_rows = [
            {
                "payment_id": str(row["payment_id"]),
                "order_id": str(row["order_id"]),
                "payment_sequential": None,
                "payment_type": self._to_str(row.get("payment_type")),
                "payment_installments": self._to_int(row.get("payment_installments")),
                "payment_value": self._to_decimal(row.get("payment_value")),
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in payments.to_dict(orient="records")
        ]
        review_rows = [
            {
                "review_id": self._to_str(row.get("review_id")),
                "order_id": str(row["order_id"]),
                "review_score": self._to_int(row.get("review_score")),
                "review_comment_title": self._to_str(row.get("review_comment_title")),
                "review_comment_message": self._to_str(row.get("review_comment_message")),
                "review_creation_date": None,
                "review_answer_timestamp": None,
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in reviews.to_dict(orient="records")
        ]
        event_rows = [
            {
                "event_id": str(row["event_id"]),
                "customer_id": self._to_str(row.get("customer_id")),
                "event_type": str(row["event_type"]),
                "product_id": self._to_str(row.get("product_id")),
                "order_id": self._to_str(row.get("order_id")),
                "occurred_at": self._parse_datetime(row.get("occurred_at")) or datetime.min,
                "source_type": self._to_str(row.get("source_type")) or manifest.source_type,
                "source_dataset": manifest.dataset_name,
                "import_run_id": run_id,
            }
            for row in user_events.to_dict(orient="records")
        ]

        self._bulk_insert(session, Seller, seller_rows)
        self._bulk_insert(session, Customer, customer_rows)
        self._bulk_insert(session, Product, product_rows)
        self._bulk_insert(session, ProductPriceHistory, price_rows)
        self._bulk_insert(session, Order, order_rows)
        self._bulk_insert(session, OrderItem, order_item_rows)
        self._bulk_insert(session, Payment, payment_rows)
        self._bulk_insert(session, Review, review_rows)
        self._bulk_insert(session, UserEvent, event_rows)

    def _delete_existing_ecommerce_dataset(self, session: Session, dataset_name: str) -> None:
        for model in [UserEvent, Review, Payment, OrderItem, ProductPriceHistory, Order, Product, Customer, Seller]:
            session.execute(delete(model).where(model.source_dataset == dataset_name))

    def _update_order_totals(self, session: Session, *, dataset_name: str) -> None:
        orders = session.query(Order).filter(Order.source_dataset == dataset_name).all()
        item_totals: dict[str, Decimal] = {}
        for row in session.query(OrderItem).filter(OrderItem.source_dataset == dataset_name).all():
            if row.line_amount is None:
                continue
            item_totals[row.order_id] = item_totals.get(row.order_id, Decimal("0")) + Decimal(row.line_amount)
        for order in orders:
            order.total_amount = item_totals.get(order.order_id)
            session.add(order)

    def _bulk_insert(self, session: Session, model: type[Any], rows: list[dict[str, Any]], chunk_size: int = 1000) -> None:
        if not rows:
            return
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            session.execute(insert(model), chunk)

    def _load_manifest(self, manifest_path: Path) -> ManifestBundle:
        path = manifest_path.resolve()
        if not path.exists():
            raise FileNotFoundError(f"Manifest not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ManifestBundle(path=path, payload=payload)

    def _infer_stock_market(self, symbol: str) -> str:
        if symbol.startswith("6"):
            return "SH"
        return "SZ"

    def _to_str(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    def _to_int(self, value: Any) -> int | None:
        if value is None or pd.isna(value):
            return None
        return int(value)

    def _to_decimal(self, value: Any) -> Decimal | None:
        if value is None or pd.isna(value):
            return None
        return Decimal(str(value))

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None
        return pd.to_datetime(text).to_pydatetime()

    def _parse_date(self, value: Any) -> date | None:
        parsed = self._parse_datetime(value)
        return parsed.date() if parsed else None

    def _sum_decimals(self, left: Decimal | None, right: Decimal | None) -> Decimal | None:
        if left is None and right is None:
            return None
        return (left or Decimal("0")) + (right or Decimal("0"))
