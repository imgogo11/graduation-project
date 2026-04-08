# 作用:
# - 这是数据库主链路集成测试文件，用来验证建表、导入和最小 API 查询在 SQLite 下能否完整跑通。
# - 重点覆盖数据库骨架阶段的核心链路，而不是大规模性能测试。
# 关联文件:
# - 直接依赖 backend/app/core/database.py、backend/app/services/imports.py 间接驱动 ORM 建表和导入流程。
# - 直接调用 backend/app/api/routes/*.py 中的最小接口函数。
# - 与 backend/app/models/entities.py、backend/app/schemas/api.py 共同构成数据库阶段的回归测试基础。
#
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import unittest

import pandas as pd
from sqlalchemy import inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "database_pipeline"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.routes import commerce as commerce_routes
from app.api.routes import health as health_routes
from app.api.routes import imports as import_routes
from app.api.routes import stocks as stock_routes
from app.core.database import create_all_tables, get_engine, get_session_factory, reset_database_state
from app.models import Order, Product, StockDailyPrice
from app.schemas.api import ImportRequest


class DatabasePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_path = ARTIFACT_ROOT / f"case_{time.time_ns()}"
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_path / "pipeline.sqlite3"
        self.previous_env = {
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "APP_ENV": os.environ.get("APP_ENV"),
        }
        os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{self.db_path.resolve().as_posix()}"
        os.environ["APP_ENV"] = "test"
        reset_database_state()
        create_all_tables()
        self.session = get_session_factory()()

    def tearDown(self) -> None:
        self.session.close()
        reset_database_state()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_create_all_tables_builds_expected_schema(self) -> None:
        inspector = inspect(get_engine())
        table_names = set(inspector.get_table_names())
        self.assertTrue(
            {
                "import_runs",
                "import_manifests",
                "import_artifacts",
                "stock_symbols",
                "stock_daily_prices",
                "customers",
                "sellers",
                "products",
                "product_price_history",
                "orders",
                "order_items",
                "payments",
                "reviews",
                "user_events",
            }.issubset(table_names)
        )

    def test_import_endpoints_and_read_endpoints_work_with_sqlite(self) -> None:
        stock_manifest = self._create_stock_manifest()
        olist_manifest = self._create_olist_manifest()
        synthetic_manifest = self._create_synthetic_manifest()

        stock_run = import_routes.import_stock_manifest(
            ImportRequest(manifest_path=str(stock_manifest)),
            session=self.session,
        )
        olist_run = import_routes.import_olist_manifest(
            ImportRequest(manifest_path=str(olist_manifest)),
            session=self.session,
        )
        synthetic_run = import_routes.import_synthetic_manifest(
            ImportRequest(manifest_path=str(synthetic_manifest)),
            session=self.session,
        )

        self.assertEqual(stock_run.status, "completed")
        self.assertEqual(olist_run.status, "completed")
        self.assertEqual(synthetic_run.status, "completed")

        runs = import_routes.list_import_runs(limit=10, session=self.session)
        self.assertEqual(len(runs), 3)

        stock_rows = stock_routes.list_daily_prices(symbol="000001", limit=10, session=self.session)
        self.assertEqual(len(stock_rows), 2)
        self.assertEqual(stock_rows[0].symbol, "000001")

        orders = commerce_routes.list_orders(limit=10, session=self.session)
        self.assertEqual(len(orders), 2)
        products = commerce_routes.list_products(limit=10, session=self.session)
        self.assertEqual(len(products), 2)

        health = health_routes.health_check()
        self.assertEqual(health.status, "ok")
        self.assertTrue(health.database_ok)

        self.assertEqual(self.session.query(StockDailyPrice).count(), 2)
        self.assertEqual(self.session.query(Order).count(), 2)
        self.assertEqual(self.session.query(Product).count(), 2)

        olist_order = self.session.query(Order).filter(Order.order_id == "olist-order-1").one()
        self.assertIsNotNone(olist_order.total_amount)
        self.assertEqual(str(olist_order.total_amount), "110.0000")

    def _create_stock_manifest(self) -> Path:
        frame = pd.DataFrame(
            [
                {
                    "symbol": "000001",
                    "trade_date": "2024-01-02",
                    "open": 10.0,
                    "close": 10.5,
                    "high": 10.7,
                    "low": 9.9,
                    "volume": 100000,
                    "amount": 1000000,
                    "amplitude": 2.3,
                    "pct_change": 1.1,
                    "change": 0.1,
                    "turnover": 3.2,
                    "adjust": "qfq",
                    "source_type": "api",
                    "股票代码": "000001",
                },
                {
                    "symbol": "000001",
                    "trade_date": "2024-01-03",
                    "open": 10.5,
                    "close": 10.8,
                    "high": 11.0,
                    "low": 10.2,
                    "volume": 120000,
                    "amount": 1200000,
                    "amplitude": 2.1,
                    "pct_change": 2.5,
                    "change": 0.3,
                    "turnover": 3.6,
                    "adjust": "qfq",
                    "source_type": "api",
                    "股票代码": "000001",
                },
            ]
        )
        csv_path = self.temp_path / "stock.csv"
        frame.to_csv(csv_path, index=False, encoding="utf-8-sig")

        return self._write_manifest(
            name="stock_manifest.json",
            payload={
                "dataset_name": "unit_stock_dataset",
                "source_type": "api",
                "source_name": "unit.akshare",
                "source_uri": "https://example.com/stock",
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "record_count": 2,
                "columns": list(frame.columns),
                "artifacts": [
                    {
                        "name": "000001",
                        "path": str(csv_path),
                        "rows": 2,
                        "columns": list(frame.columns),
                    }
                ],
                "metadata": {"symbols": ["000001"]},
            },
        )

    def _create_olist_manifest(self) -> Path:
        customers = pd.DataFrame(
            [
                {
                    "customer_id": "olist-customer-1",
                    "customer_unique_id": "olist-unique-1",
                    "customer_zip_code_prefix": "100000",
                    "customer_city": "Shanghai",
                    "customer_state": "SH",
                }
            ]
        )
        sellers = pd.DataFrame(
            [
                {
                    "seller_id": "olist-seller-1",
                    "seller_zip_code_prefix": "200000",
                    "seller_city": "Beijing",
                    "seller_state": "BJ",
                }
            ]
        )
        products = pd.DataFrame(
            [
                {
                    "product_id": "olist-product-1",
                    "product_category_name": "books",
                    "product_name_lenght": 12,
                    "product_description_lenght": 40,
                    "product_photos_qty": 1,
                    "product_weight_g": 300,
                    "product_length_cm": 20,
                    "product_height_cm": 3,
                    "product_width_cm": 15,
                }
            ]
        )
        orders = pd.DataFrame(
            [
                {
                    "order_id": "olist-order-1",
                    "customer_id": "olist-customer-1",
                    "order_status": "delivered",
                    "order_purchase_timestamp": "2024-02-01T10:00:00",
                    "order_approved_at": "2024-02-01T10:05:00",
                    "order_delivered_carrier_date": "2024-02-02T08:00:00",
                    "order_delivered_customer_date": "2024-02-05T16:00:00",
                    "order_estimated_delivery_date": "2024-02-06T00:00:00",
                }
            ]
        )
        order_items = pd.DataFrame(
            [
                {
                    "order_id": "olist-order-1",
                    "order_item_id": 1,
                    "product_id": "olist-product-1",
                    "seller_id": "olist-seller-1",
                    "shipping_limit_date": "2024-02-02T00:00:00",
                    "price": 100.0,
                    "freight_value": 10.0,
                }
            ]
        )
        payments = pd.DataFrame(
            [
                {
                    "order_id": "olist-order-1",
                    "payment_sequential": 1,
                    "payment_type": "credit_card",
                    "payment_installments": 2,
                    "payment_value": 110.0,
                }
            ]
        )
        reviews = pd.DataFrame(
            [
                {
                    "review_id": "olist-review-1",
                    "order_id": "olist-order-1",
                    "review_score": 5,
                    "review_comment_title": "great",
                    "review_comment_message": "works",
                    "review_creation_date": "2024-02-05T18:00:00",
                    "review_answer_timestamp": "2024-02-05T20:00:00",
                }
            ]
        )
        translations = pd.DataFrame(
            [{"product_category_name": "books", "product_category_name_english": "books"}]
        )

        paths = {
            "customers": self._write_csv("olist_customers.csv", customers),
            "sellers": self._write_csv("olist_sellers.csv", sellers),
            "products": self._write_csv("olist_products.csv", products),
            "orders": self._write_csv("olist_orders.csv", orders),
            "order_items": self._write_csv("olist_order_items.csv", order_items),
            "payments": self._write_csv("olist_payments.csv", payments),
            "reviews": self._write_csv("olist_reviews.csv", reviews),
            "category_translation": self._write_csv("olist_category_translation.csv", translations),
        }

        artifacts = [
            {"name": name, "path": str(path), "rows": len(frame), "columns": list(frame.columns)}
            for name, path, frame in [
                ("customers", paths["customers"], customers),
                ("sellers", paths["sellers"], sellers),
                ("products", paths["products"], products),
                ("orders", paths["orders"], orders),
                ("order_items", paths["order_items"], order_items),
                ("payments", paths["payments"], payments),
                ("reviews", paths["reviews"], reviews),
                ("category_translation", paths["category_translation"], translations),
            ]
        ]

        return self._write_manifest(
            name="olist_manifest.json",
            payload={
                "dataset_name": "unit_olist_dataset",
                "source_type": "csv",
                "source_name": "unit.olist",
                "source_uri": "https://example.com/olist",
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "record_count": sum(item["rows"] for item in artifacts),
                "columns": sorted({column for item in artifacts for column in item["columns"]}),
                "artifacts": artifacts,
                "metadata": {"dataset_dir": str(self.temp_path)},
            },
        )

    def _create_synthetic_manifest(self) -> Path:
        customers = pd.DataFrame(
            [
                {
                    "customer_id": "syn-customer-1",
                    "customer_name": "Synthetic Customer",
                    "customer_city": "Shenzhen",
                    "customer_state": "GD",
                    "signup_at": "2024-01-10T09:00:00",
                    "source_type": "synthetic",
                }
            ]
        )
        sellers = pd.DataFrame(
            [
                {
                    "seller_id": "syn-seller-1",
                    "seller_name": "Synthetic Seller",
                    "seller_city": "Guangzhou",
                    "seller_state": "GD",
                    "source_type": "synthetic",
                }
            ]
        )
        products = pd.DataFrame(
            [
                {
                    "product_id": "syn-product-1",
                    "seller_id": "syn-seller-1",
                    "product_name": "Synthetic Product",
                    "category": "electronics",
                    "base_price": 599.0,
                    "created_at": "2024-01-01T00:00:00",
                    "source_type": "synthetic",
                }
            ]
        )
        price_history = pd.DataFrame(
            [
                {
                    "price_event_id": "syn-price-1",
                    "product_id": "syn-product-1",
                    "effective_at": "2024-01-01T00:00:00",
                    "price": 599.0,
                    "source_type": "synthetic",
                }
            ]
        )
        orders = pd.DataFrame(
            [
                {
                    "order_id": "syn-order-1",
                    "customer_id": "syn-customer-1",
                    "order_status": "delivered",
                    "order_purchase_timestamp": "2024-03-01T12:00:00",
                    "order_approved_at": "2024-03-01T12:15:00",
                    "order_delivered_at": "2024-03-03T12:00:00",
                    "total_amount": 629.0,
                    "source_type": "synthetic",
                }
            ]
        )
        order_items = pd.DataFrame(
            [
                {
                    "order_item_id": "syn-order-1-01",
                    "order_id": "syn-order-1",
                    "product_id": "syn-product-1",
                    "seller_id": "syn-seller-1",
                    "quantity": 1,
                    "unit_price": 599.0,
                    "freight_value": 30.0,
                    "line_amount": 629.0,
                    "source_type": "synthetic",
                }
            ]
        )
        payments = pd.DataFrame(
            [
                {
                    "payment_id": "syn-payment-1",
                    "order_id": "syn-order-1",
                    "payment_type": "credit_card",
                    "payment_installments": 3,
                    "payment_value": 629.0,
                    "source_type": "synthetic",
                }
            ]
        )
        reviews = pd.DataFrame(
            [
                {
                    "review_id": "syn-review-1",
                    "order_id": "syn-order-1",
                    "review_score": 4,
                    "review_comment_title": "ok",
                    "review_comment_message": "synthetic",
                    "source_type": "synthetic",
                }
            ]
        )
        user_events = pd.DataFrame(
            [
                {
                    "event_id": "syn-event-1",
                    "customer_id": "syn-customer-1",
                    "event_type": "purchase",
                    "product_id": "syn-product-1",
                    "order_id": "syn-order-1",
                    "occurred_at": "2024-03-01T12:00:00",
                    "source_type": "synthetic",
                }
            ]
        )

        paths = {
            "customers": self._write_csv("syn_customers.csv", customers),
            "sellers": self._write_csv("syn_sellers.csv", sellers),
            "products": self._write_csv("syn_products.csv", products),
            "product_price_history": self._write_csv("syn_product_price_history.csv", price_history),
            "orders": self._write_csv("syn_orders.csv", orders),
            "order_items": self._write_csv("syn_order_items.csv", order_items),
            "payments": self._write_csv("syn_payments.csv", payments),
            "reviews": self._write_csv("syn_reviews.csv", reviews),
            "user_events": self._write_csv("syn_user_events.csv", user_events),
        }

        artifacts = [
            {"name": name, "path": str(path), "rows": len(frame), "columns": list(frame.columns)}
            for name, path, frame in [
                ("customers", paths["customers"], customers),
                ("sellers", paths["sellers"], sellers),
                ("products", paths["products"], products),
                ("product_price_history", paths["product_price_history"], price_history),
                ("orders", paths["orders"], orders),
                ("order_items", paths["order_items"], order_items),
                ("payments", paths["payments"], payments),
                ("reviews", paths["reviews"], reviews),
                ("user_events", paths["user_events"], user_events),
            ]
        ]

        return self._write_manifest(
            name="synthetic_manifest.json",
            payload={
                "dataset_name": "unit_synthetic_dataset",
                "source_type": "synthetic",
                "source_name": "unit.synthetic",
                "source_uri": None,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "record_count": sum(item["rows"] for item in artifacts),
                "columns": sorted({column for item in artifacts for column in item["columns"]}),
                "artifacts": artifacts,
                "metadata": {"seed": 1},
            },
        )

    def _write_csv(self, name: str, frame: pd.DataFrame) -> Path:
        path = self.temp_path / name
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def _write_manifest(self, *, name: str, payload: dict[str, object]) -> Path:
        path = self.temp_path / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
