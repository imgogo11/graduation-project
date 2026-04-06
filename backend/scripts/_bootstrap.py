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
