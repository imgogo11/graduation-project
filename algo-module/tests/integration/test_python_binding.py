from __future__ import annotations

from importlib import import_module
import os
from pathlib import Path
import shutil
import sys
from typing import Protocol, cast


class RangeMaxResultProtocol(Protocol):
    max_value_scaled: int
    matched_indices: list[int]


class RangeMaxSegmentTreeProtocol(Protocol):
    def query_inclusive(self, left: int, right: int) -> RangeMaxResultProtocol: ...

    def size(self) -> int: ...


class RangeMaxSegmentTreeFactory(Protocol):
    def __call__(self, values: list[int]) -> RangeMaxSegmentTreeProtocol: ...


class RangeKthResultProtocol(Protocol):
    kth_value_scaled: int
    matched_indices: list[int]


class RangeKthPersistentSegmentTreeProtocol(Protocol):
    def query_inclusive(self, left: int, right: int, k: int) -> RangeKthResultProtocol: ...

    def size(self) -> int: ...


class RangeKthPersistentSegmentTreeFactory(Protocol):
    def __call__(self, values: list[int]) -> RangeKthPersistentSegmentTreeProtocol: ...


class AlgoModuleProtocol(Protocol):
    HistoricalDominanceCdqCounter: type
    HistoricalDominance3dCdqCounter: type
    RangeMaxSegmentTree: RangeMaxSegmentTreeFactory
    RangeKthPersistentSegmentTree: RangeKthPersistentSegmentTreeFactory


def configure_windows_dll_search_paths() -> None:
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return

    compiler_path = shutil.which("g++.exe")
    if compiler_path:
        os.add_dll_directory(str(Path(compiler_path).resolve().parent))
    os.add_dll_directory(str(Path(sys.executable).resolve().parent))


def load_algo_module() -> AlgoModuleProtocol:
    return cast(AlgoModuleProtocol, import_module("algo_module_py"))


def main() -> int:
    if len(sys.argv) > 1:
        module_dir = Path(sys.argv[1]).resolve()
        sys.path.insert(0, str(module_dir))

    configure_windows_dll_search_paths()
    algo_module_py = load_algo_module()

    tree = algo_module_py.RangeMaxSegmentTree([100, 250, 250, 80])
    result = tree.query_inclusive(0, 3)

    assert result.max_value_scaled == 250
    assert list(result.matched_indices) == [1, 2]
    assert tree.size() == 4

    kth_tree = algo_module_py.RangeKthPersistentSegmentTree([100, 250, 250, 80, 300])
    kth_result = kth_tree.query_inclusive(0, 4, 3)

    assert kth_result.kth_value_scaled == 250
    assert list(kth_result.matched_indices) == [1, 2]
    assert kth_tree.size() == 5

    invalid_k_thrown = False
    try:
        kth_tree.query_inclusive(0, 4, 0)
    except ValueError:
        invalid_k_thrown = True

    assert invalid_k_thrown

    dominance_counter = algo_module_py.HistoricalDominanceCdqCounter([5, 3, 7, 7, 8], [4, 6, 2, 4, 4])
    assert dominance_counter.size() == 5
    assert list(dominance_counter.count_prefix_dominance()) == [0, 0, 0, 2, 3]

    dominance_counter_3d = algo_module_py.HistoricalDominance3dCdqCounter([5, 3, 7, 7, 8], [4, 6, 2, 4, 4], [3, 3, 1, 4, 4])
    assert dominance_counter_3d.size() == 5
    assert list(dominance_counter_3d.count_prefix_dominance()) == [0, 0, 0, 2, 3]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
