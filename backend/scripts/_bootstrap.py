# 作用:
# - 这是脚本层的公共引导文件，用来把 backend 目录加入 sys.path，
#   让命令行脚本可以稳定导入 app 包下的模块。
# 关联文件:
# - 被 backend/scripts/inspect_olist_dataset.py、generate_ecommerce_synthetic.py、
#   fetch_stock_akshare.py、crawl_demo_ecommerce.py 导入使用。
# - 为这些脚本提供 ensure_backend_on_path 接口。
#
from __future__ import annotations

from pathlib import Path
import sys


def ensure_backend_on_path() -> tuple[Path, Path]:
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    repo_root = backend_dir.parent
    backend_str = str(backend_dir)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)
    return backend_dir, repo_root
