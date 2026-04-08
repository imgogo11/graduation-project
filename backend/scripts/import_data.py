# 作用:
# - 这是数据库导入脚本的命令行入口，用来把已准备好的 manifest 批量导入到当前配置的数据库中。
# - 当前支持 `stock`、`olist`、`synthetic` 三类数据源。
# 关联文件:
# - 直接依赖 backend/scripts/_bootstrap.py 准备 backend 导入路径。
# - 直接调用 backend/app/services/imports.py 中的 ImportService。
# - 默认 manifest 路径来自 backend/app/core/config.py。
#
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_backend_on_path

ensure_backend_on_path()

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.services.imports import ImportService


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Import prepared manifests into the configured database.")
    parser.add_argument(
        "dataset",
        choices=["stock", "olist", "synthetic"],
        help="Which prepared dataset manifest to import",
    )
    parser.add_argument("--manifest-path", default="", help="Optional manifest path override")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path).expanduser().resolve() if args.manifest_path else None
    service = ImportService()
    session = get_session_factory()()
    try:
        if args.dataset == "stock":
            run = service.import_stock_manifest(session, manifest_path or settings.default_stock_manifest)
        elif args.dataset == "olist":
            run = service.import_olist_manifest(session, manifest_path or settings.default_olist_manifest)
        else:
            run = service.import_synthetic_manifest(session, manifest_path or settings.default_synthetic_manifest)
    finally:
        session.close()

    print(f"Import run {run.id} finished with status={run.status} dataset={run.dataset_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
