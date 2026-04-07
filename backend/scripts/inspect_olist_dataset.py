# 作用:
# - 这是 Olist 数据集校验脚本的命令行入口，负责接收参数并调用底层校验逻辑。
# 关联文件:
# - 直接导入 backend/scripts/_bootstrap.py，用来准备 backend 的导入路径。
# - 直接调用 backend/app/data_sources/olist.py 中的 inspect_olist_dataset 接口。
# - 作为用户手动校验 Olist CSV 数据集的入口脚本。
#
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
