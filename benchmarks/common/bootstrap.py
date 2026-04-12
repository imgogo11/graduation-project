from __future__ import annotations

from pathlib import Path
import sys


def ensure_project_paths() -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    for candidate in (repo_root, backend_dir):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    return repo_root, backend_dir


REPO_ROOT, BACKEND_DIR = ensure_project_paths()
BENCHMARKS_ROOT = REPO_ROOT / "benchmarks"
