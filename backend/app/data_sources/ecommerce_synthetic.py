# 作用:
# - 这是合成电商数据生成模块，负责构造 customers、orders、order_items、products、
#   payments、reviews、user_events 等多张模拟数据表，并将其写成 CSV 与 manifest。
# 关联文件:
# - 被 backend/scripts/generate_ecommerce_synthetic.py 导入并作为实际业务实现调用。
# - 被 backend/tests/test_ecommerce_synthetic.py 导入，用于验证生成结果与写盘结果。
# - 依赖 backend/app/data_sources/contracts.py 提供的 DatasetArtifact、ImportManifest、
#   SourceType、now_utc_iso 和 write_manifest。
#
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import random
from typing import Any

import pandas as pd

from .contracts import DatasetArtifact, ImportManifest, SourceType, now_utc_iso, write_manifest

_CITIES = [
    ("Shanghai", "SH"),
    ("Beijing", "BJ"),
    ("Shenzhen", "GD"),
    ("Guangzhou", "GD"),
    ("Hangzhou", "ZJ"),
    ("Nanjing", "JS"),
    ("Chengdu", "SC"),
    ("Wuhan", "HB"),
]

_CATEGORIES = {
    "electronics": 1200.0,
    "fashion": 220.0,
    "home": 480.0,
    "books": 88.0,
    "sports": 360.0,
    "beauty": 160.0,
    "food": 65.0,
}

_ORDER_STATUSES = ["delivered", "shipped", "processing", "cancelled"]
_PAYMENT_TYPES = ["credit_card", "debit_card", "voucher", "pix"]
_EVENT_TYPES = ["view", "search", "wishlist", "cart", "purchase"]


def _random_datetime(rng: random.Random, start: datetime, end: datetime) -> datetime:
    span_seconds = int((end - start).total_seconds())
    if span_seconds <= 0:
        return start
    return start + timedelta(seconds=rng.randint(0, span_seconds))


def _build_month_starts(start: datetime, end: datetime) -> list[datetime]:
    current = datetime(start.year, start.month, 1)
    month_starts: list[datetime] = []
    while current <= end:
        month_starts.append(current)
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)
    return month_starts or [start]


def generate_bundle(
    order_count: int,
    user_count: int,
    product_count: int,
    start_date: str,
    end_date: str,
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    if order_count <= 0 or user_count <= 0 or product_count <= 0:
        raise ValueError("order_count, user_count and product_count must all be positive")

    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    if end_dt <= start_dt:
        raise ValueError("end_date must be later than start_date")

    rng = random.Random(seed)
    source_type = SourceType.SYNTHETIC.value

    seller_count = max(10, product_count // 20)
    sellers: list[dict[str, Any]] = []
    for index in range(1, seller_count + 1):
        city, state = rng.choice(_CITIES)
        sellers.append(
            {
                "seller_id": f"SEL{index:05d}",
                "seller_name": f"Seller {index:05d}",
                "seller_city": city,
                "seller_state": state,
                "source_type": source_type,
            }
        )

    customers: list[dict[str, Any]] = []
    for index in range(1, user_count + 1):
        city, state = rng.choice(_CITIES)
        signup_at = _random_datetime(rng, start_dt - timedelta(days=180), end_dt - timedelta(days=30))
        customers.append(
            {
                "customer_id": f"CUS{index:06d}",
                "customer_name": f"Customer {index:06d}",
                "customer_city": city,
                "customer_state": state,
                "signup_at": signup_at.isoformat(timespec="seconds"),
                "source_type": source_type,
            }
        )

    products: list[dict[str, Any]] = []
    category_names = list(_CATEGORIES.keys())
    for index in range(1, product_count + 1):
        category = rng.choice(category_names)
        seller = rng.choice(sellers)
        products.append(
            {
                "product_id": f"PROD{index:06d}",
                "seller_id": seller["seller_id"],
                "product_name": f"{category.title()} Item {index:06d}",
                "category": category,
                "base_price": round(_CATEGORIES[category] * rng.uniform(0.7, 1.4), 2),
                "created_at": _random_datetime(rng, start_dt - timedelta(days=365), start_dt).isoformat(timespec="seconds"),
                "source_type": source_type,
            }
        )

    month_starts = _build_month_starts(start_dt, end_dt)
    price_history: list[dict[str, Any]] = []
    for product in products:
        current_price = float(product["base_price"])
        for point in month_starts:
            current_price = max(9.9, current_price * rng.uniform(0.95, 1.08))
            price_history.append(
                {
                    "price_event_id": f"PH-{product['product_id']}-{point.strftime('%Y%m')}",
                    "product_id": product["product_id"],
                    "effective_at": point.isoformat(timespec="seconds"),
                    "price": round(current_price, 2),
                    "source_type": source_type,
                }
            )

    customer_ids = [customer["customer_id"] for customer in customers]
    product_lookup = {product["product_id"]: product for product in products}
    product_ids = list(product_lookup.keys())
    orders: list[dict[str, Any]] = []
    order_items: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    user_events: list[dict[str, Any]] = []

    for order_index in range(1, order_count + 1):
        order_id = f"ORD{order_index:08d}"
        customer_id = rng.choice(customer_ids)
        purchased_at = _random_datetime(rng, start_dt, end_dt)
        status = rng.choices(_ORDER_STATUSES, weights=[0.68, 0.14, 0.12, 0.06], k=1)[0]
        approved_at = purchased_at + timedelta(minutes=rng.randint(5, 180))
        delivered_at = None
        if status in {"delivered", "shipped"}:
            delivered_at = approved_at + timedelta(days=rng.randint(1, 12), hours=rng.randint(0, 20))

        item_count = rng.choices([1, 2, 3, 4], weights=[0.54, 0.26, 0.14, 0.06], k=1)[0]
        total_amount = 0.0
        for item_index in range(1, item_count + 1):
            product_id = rng.choice(product_ids)
            product = product_lookup[product_id]
            quantity = rng.choices([1, 2, 3], weights=[0.72, 0.21, 0.07], k=1)[0]
            unit_price = round(float(product["base_price"]) * rng.uniform(0.92, 1.15), 2)
            freight_value = round(unit_price * quantity * rng.uniform(0.03, 0.12), 2)
            line_amount = round(unit_price * quantity + freight_value, 2)
            total_amount += line_amount
            order_items.append(
                {
                    "order_item_id": f"{order_id}-{item_index:02d}",
                    "order_id": order_id,
                    "product_id": product_id,
                    "seller_id": product["seller_id"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "freight_value": freight_value,
                    "line_amount": line_amount,
                    "source_type": source_type,
                }
            )

        total_amount = round(total_amount, 2)
        payment_type = rng.choice(_PAYMENT_TYPES)
        payments.append(
            {
                "payment_id": f"PAY{order_index:08d}",
                "order_id": order_id,
                "payment_type": payment_type,
                "payment_installments": rng.randint(1, 6) if payment_type == "credit_card" else 1,
                "payment_value": total_amount,
                "source_type": source_type,
            }
        )

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_status": status,
                "order_purchase_timestamp": purchased_at.isoformat(timespec="seconds"),
                "order_approved_at": approved_at.isoformat(timespec="seconds"),
                "order_delivered_at": delivered_at.isoformat(timespec="seconds") if delivered_at else "",
                "total_amount": total_amount,
                "source_type": source_type,
            }
        )

        if status == "delivered" and rng.random() < 0.74:
            reviews.append(
                {
                    "review_id": f"REV{order_index:08d}",
                    "order_id": order_id,
                    "review_score": rng.choices([5, 4, 3, 2, 1], weights=[0.46, 0.28, 0.14, 0.07, 0.05], k=1)[0],
                    "review_comment_title": "Synthetic review",
                    "review_comment_message": "Generated for MVP pipeline and benchmark validation.",
                    "source_type": source_type,
                }
            )

        pre_purchase_events = rng.randint(2, 5)
        for event_index in range(pre_purchase_events):
            event_time = purchased_at - timedelta(hours=rng.randint(1, 96), minutes=rng.randint(0, 59))
            user_events.append(
                {
                    "event_id": f"EVT{order_index:08d}-{event_index:02d}",
                    "customer_id": customer_id,
                    "event_type": rng.choice(_EVENT_TYPES[:-1]),
                    "product_id": rng.choice(product_ids),
                    "order_id": "",
                    "occurred_at": event_time.isoformat(timespec="seconds"),
                    "source_type": source_type,
                }
            )
        user_events.append(
            {
                "event_id": f"EVT{order_index:08d}-99",
                "customer_id": customer_id,
                "event_type": "purchase",
                "product_id": order_items[-1]["product_id"],
                "order_id": order_id,
                "occurred_at": purchased_at.isoformat(timespec="seconds"),
                "source_type": source_type,
            }
        )

    return {
        "customers": pd.DataFrame(customers),
        "sellers": pd.DataFrame(sellers),
        "products": pd.DataFrame(products),
        "product_price_history": pd.DataFrame(price_history),
        "orders": pd.DataFrame(orders),
        "order_items": pd.DataFrame(order_items),
        "payments": pd.DataFrame(payments),
        "reviews": pd.DataFrame(reviews),
        "user_events": pd.DataFrame(user_events),
    }


def write_bundle(
    frames: dict[str, pd.DataFrame],
    output_dir: Path,
    seed: int,
    start_date: str,
    end_date: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[DatasetArtifact] = []
    all_columns: set[str] = set()
    total_rows = 0

    for name, frame in frames.items():
        file_path = output_dir / f"{name}.csv"
        frame.to_csv(file_path, index=False, encoding="utf-8-sig")
        artifacts.append(
            DatasetArtifact(
                name=name,
                path=str(file_path),
                rows=len(frame),
                columns=list(frame.columns),
            )
        )
        total_rows += len(frame)
        all_columns.update(frame.columns)

    manifest = ImportManifest(
        dataset_name="synthetic_ecommerce_mvp",
        source_type=SourceType.SYNTHETIC,
        source_name="local.synthetic.generator",
        source_uri=None,
        created_at=now_utc_iso(),
        record_count=total_rows,
        columns=sorted(all_columns),
        artifacts=artifacts,
        metadata={
            "seed": seed,
            "start_date": start_date,
            "end_date": end_date,
            "tables": list(frames.keys()),
        },
    )
    return write_manifest(manifest, output_dir / "synthetic_ecommerce_manifest.json")
