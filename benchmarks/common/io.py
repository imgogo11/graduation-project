from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path

from .bootstrap import BENCHMARKS_ROOT


@dataclass(frozen=True, slots=True)
class SuitePaths:
    root: Path
    results: Path
    images: Path


def prepare_suite_paths(suite_name: str, *, explicit_root: Path | None = None) -> SuitePaths:
    root = explicit_root.resolve() if explicit_root is not None else (BENCHMARKS_ROOT / suite_name).resolve()
    results = root / "results"
    images = root / "images"
    results.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)
    return SuitePaths(root=root, results=results, images=images)


def write_csv(path: Path, rows: list[dict[str, object]], *, fieldnames: list[str] | None = None) -> None:
    fieldnames_to_use = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames_to_use)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
