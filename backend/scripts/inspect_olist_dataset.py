from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_backend_on_path

_, REPO_ROOT = ensure_backend_on_path()

from app.data_sources.olist import inspect_olist_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a manually downloaded Olist dataset directory.")
    parser.add_argument(
        "--dataset-dir",
        default=str(REPO_ROOT / "data" / "raw" / "ecommerce" / "olist"),
        help="Directory containing the Kaggle Olist CSV files",
    )
    parser.add_argument(
        "--manifest-dir",
        default="",
        help="Optional output directory for the generated manifest; defaults to dataset-dir",
    )
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    manifest_dir = Path(args.manifest_dir) if args.manifest_dir else None
    manifest_path = inspect_olist_dataset(dataset_dir=dataset_dir, manifest_dir=manifest_dir)
    print(f"Olist dataset manifest written to: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
