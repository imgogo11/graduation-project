from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ARTIFACT_ROOT = Path(tempfile.gettempdir()) / "graduation-project-benchmarks-tests"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

from benchmarks.common.io import prepare_suite_paths  # noqa: E402
from benchmarks.common.metrics import classify_relative_error_band, rank_error, summarize_latencies  # noqa: E402
from benchmarks.common.plotting import save_grouped_bar_chart, save_pie_chart, save_table_image  # noqa: E402
from benchmarks.common.synthetic_data import build_query_windows, resolve_samples  # noqa: E402


class BenchmarkCommonTests(unittest.TestCase):
    def _workspace_case_dir(self) -> Path:
        case_dir = ARTIFACT_ROOT / f"case_{time.time_ns()}"
        case_dir.mkdir(parents=True, exist_ok=True)
        return case_dir

    def test_resolve_samples_supports_all_and_named_presets(self) -> None:
        self.assertEqual(resolve_samples("300x480")[0].label, "300x480")
        self.assertEqual([sample.label for sample in resolve_samples("all")], ["300x480", "1000x480", "3000x480"])

    def test_build_query_windows_is_deterministic_and_valid(self) -> None:
        dates = [
            Path("2024-01-01"),
            Path("2024-01-02"),
            Path("2024-01-03"),
            Path("2024-01-04"),
            Path("2024-01-05"),
        ]
        windows = build_query_windows(dates, total=10, seed=42)
        self.assertEqual(windows, build_query_windows(dates, total=10, seed=42))
        for left, right, kth in windows:
            left_index = dates.index(left)
            right_index = dates.index(right)
            self.assertLessEqual(left_index, right_index)
            self.assertGreaterEqual(kth, 1)
            self.assertLessEqual(kth, right_index - left_index + 1)

    def test_metrics_helpers_cover_expected_edges(self) -> None:
        summary = summarize_latencies([0.01, 0.02, 0.03])
        self.assertGreater(summary.mean_seconds, 0.0)
        self.assertEqual(rank_error([10, 9, 8, 7], 8, 3), 0)
        self.assertEqual(classify_relative_error_band(0.0), "0%")
        self.assertEqual(classify_relative_error_band(0.02), "<=5%")

    def test_prepare_suite_paths_creates_results_and_images(self) -> None:
        temp_dir = self._workspace_case_dir()
        paths = prepare_suite_paths("temp_suite", explicit_root=temp_dir)
        self.assertTrue(paths.results.exists())
        self.assertTrue(paths.images.exists())

    def test_plotting_helpers_write_png_files(self) -> None:
        temp_path = self._workspace_case_dir()
        try:
            save_table_image(temp_path / "table.png", title="Table", columns=["A"], rows=[["1"]])
            save_grouped_bar_chart(temp_path / "bar.png", title="Bar", categories=["A"], series={"S": [1.0]}, ylabel="Y")
            save_pie_chart(temp_path / "pie.png", title="Pie", labels=["A"], values=[1.0])
        except ImportError as exc:
            self.skipTest(str(exc))
        self.assertTrue((temp_path / "table.png").exists())
        self.assertTrue((temp_path / "bar.png").exists())
        self.assertTrue((temp_path / "pie.png").exists())


if __name__ == "__main__":
    unittest.main()
