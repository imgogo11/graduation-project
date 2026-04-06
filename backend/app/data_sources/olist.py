from __future__ import annotations

from pathlib import Path

import pandas as pd

from .contracts import DatasetArtifact, ImportManifest, SourceType, now_utc_iso, write_manifest

OLIST_DATASET_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"

EXPECTED_FILES: dict[str, dict[str, object]] = {
    "orders": {
        "filename": "olist_orders_dataset.csv",
        "required": True,
        "columns": {"order_id", "customer_id", "order_status", "order_purchase_timestamp"},
    },
    "order_items": {
        "filename": "olist_order_items_dataset.csv",
        "required": True,
        "columns": {"order_id", "order_item_id", "product_id", "seller_id", "price"},
    },
    "products": {
        "filename": "olist_products_dataset.csv",
        "required": True,
        "columns": {"product_id", "product_category_name"},
    },
    "customers": {
        "filename": "olist_customers_dataset.csv",
        "required": True,
        "columns": {"customer_id", "customer_unique_id"},
    },
    "sellers": {
        "filename": "olist_sellers_dataset.csv",
        "required": True,
        "columns": {"seller_id"},
    },
    "payments": {
        "filename": "olist_order_payments_dataset.csv",
        "required": True,
        "columns": {"order_id", "payment_type", "payment_value"},
    },
    "reviews": {
        "filename": "olist_order_reviews_dataset.csv",
        "required": True,
        "columns": {"review_id", "order_id", "review_score"},
    },
    "category_translation": {
        "filename": "product_category_name_translation.csv",
        "required": False,
        "columns": {"product_category_name", "product_category_name_english"},
    },
}


def inspect_olist_dataset(dataset_dir: Path, manifest_dir: Path | None = None) -> Path:
    dataset_dir = dataset_dir.resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Olist dataset directory does not exist: {dataset_dir}")

    artifacts: list[DatasetArtifact] = []
    missing_required: list[str] = []
    found_optional: list[str] = []
    all_columns: set[str] = set()
    total_rows = 0

    for logical_name, config in EXPECTED_FILES.items():
        file_path = dataset_dir / str(config["filename"])
        required = bool(config["required"])
        required_columns = set(config["columns"])

        if not file_path.exists():
            if required:
                missing_required.append(file_path.name)
            continue

        frame = pd.read_csv(file_path)
        missing_columns = sorted(required_columns - set(frame.columns))
        if missing_columns:
            raise ValueError(f"{file_path.name} is missing columns: {missing_columns}")

        if not required:
            found_optional.append(file_path.name)

        artifacts.append(
            DatasetArtifact(
                name=logical_name,
                path=str(file_path),
                rows=len(frame),
                columns=list(frame.columns),
            )
        )
        all_columns.update(frame.columns)
        total_rows += len(frame)

    if missing_required:
        raise FileNotFoundError(f"Missing required Olist files: {missing_required}")

    if manifest_dir is None:
        manifest_dir = dataset_dir
    manifest = ImportManifest(
        dataset_name="olist_brazilian_ecommerce",
        source_type=SourceType.CSV,
        source_name="kaggle/olistbr/brazilian-ecommerce",
        source_uri=OLIST_DATASET_URL,
        created_at=now_utc_iso(),
        record_count=total_rows,
        columns=sorted(all_columns),
        artifacts=artifacts,
        metadata={
            "dataset_dir": str(dataset_dir),
            "required_files": [
                str(config["filename"])
                for config in EXPECTED_FILES.values()
                if bool(config["required"])
            ],
            "optional_files_found": found_optional,
        },
    )
    return write_manifest(manifest, manifest_dir / "olist_dataset_manifest.json")
