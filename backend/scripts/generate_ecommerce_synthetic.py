from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_backend_on_path

_, REPO_ROOT = ensure_backend_on_path()

from app.data_sources.ecommerce_synthetic import generate_bundle, write_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic e-commerce data for the MVP pipeline.")
    parser.add_argument("--order-count", type=int, default=10000, help="Number of orders to generate")
    parser.add_argument("--user-count", type=int, default=5000, help="Number of customers to generate")
    parser.add_argument("--product-count", type=int, default=1200, help="Number of products to generate")
    parser.add_argument("--start-date", default="2024-01-01", help="Start date in ISO format")
    parser.add_argument("--end-date", default="2026-04-06", help="End date in ISO format")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "data" / "processed" / "ecommerce" / "synthetic"),
        help="Directory for generated CSV files and manifest",
    )
    args = parser.parse_args()

    frames = generate_bundle(
        order_count=args.order_count,
        user_count=args.user_count,
        product_count=args.product_count,
        start_date=args.start_date,
        end_date=args.end_date,
        seed=args.seed,
    )
    manifest_path = write_bundle(
        frames=frames,
        output_dir=Path(args.out_dir),
        seed=args.seed,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(f"Generated tables: {', '.join(sorted(frames.keys()))}")
    print(f"Manifest written to: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
