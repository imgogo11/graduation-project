from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib
import os
import shutil
import sys
from pathlib import Path
from typing import Sequence

from app.core.config import get_settings
from app.engine_bridge.tdigest import RangeKthTDigestBlockIndex


@dataclass(frozen=True, slots=True)
class RangeMaxEngineResult:
    max_value_scaled: int
    matched_indices: list[int]


@dataclass(frozen=True, slots=True)
class RangeKthEngineResult:
    kth_value_scaled: int
    matched_indices: list[int]
    approximation_note: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalDominanceEngineResult:
    dominated_counts: list[int]


def _module_directory() -> Path:
    return get_settings().project_root / "algo-engine" / "build" / "python"


def _configure_windows_dll_search_paths() -> None:
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return

    candidates: list[Path] = []
    compiler_path = shutil.which("g++.exe")
    if compiler_path:
        candidates.append(Path(compiler_path).resolve().parent)
    candidates.append(Path(sys.executable).resolve().parent)

    for candidate in candidates:
        if candidate.exists():
            os.add_dll_directory(str(candidate))


@lru_cache(maxsize=1)
def load_algo_engine_module():
    module_name = "algo_engine_py"
    _configure_windows_dll_search_paths()
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        module_dir = _module_directory()
        if str(module_dir) not in sys.path:
            sys.path.insert(0, str(module_dir))
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"{module_name} is not available. Build the algo-engine module so it exists under {module_dir}."
            ) from exc


def query_range_max(values_scaled: Sequence[int], left: int, right: int) -> RangeMaxEngineResult:
    module = load_algo_engine_module()
    tree = module.RangeMaxSegmentTree(list(values_scaled))
    result = tree.query_inclusive(left, right)
    return RangeMaxEngineResult(
        max_value_scaled=int(result.max_value_scaled),
        matched_indices=[int(index) for index in result.matched_indices],
    )


def query_range_kth(values_scaled: Sequence[int], left: int, right: int, k: int) -> RangeKthEngineResult:
    module = load_algo_engine_module()
    tree = module.RangeKthPersistentSegmentTree(list(values_scaled))
    result = tree.query_inclusive(left, right, k)
    return RangeKthEngineResult(
        kth_value_scaled=int(result.kth_value_scaled),
        matched_indices=[int(index) for index in result.matched_indices],
        approximation_note=None,
    )


def query_range_kth_tdigest(values_scaled: Sequence[int], left: int, right: int, k: int) -> RangeKthEngineResult:
    digest_index = RangeKthTDigestBlockIndex(values_scaled)
    result = digest_index.query_inclusive(left, right, k)
    return RangeKthEngineResult(
        kth_value_scaled=int(result.kth_value_scaled),
        matched_indices=[int(index) for index in result.matched_indices],
        approximation_note=result.approximation_note,
    )


def query_historical_dominance(
    primary_values_scaled: Sequence[int],
    secondary_values_scaled: Sequence[int],
) -> HistoricalDominanceEngineResult:
    module = load_algo_engine_module()
    counter = module.HistoricalDominanceCdqCounter(list(primary_values_scaled), list(secondary_values_scaled))
    return HistoricalDominanceEngineResult(
        dominated_counts=[int(item) for item in counter.count_prefix_dominance()],
    )
