from __future__ import annotations

from pathlib import Path
import sys
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine_bridge.adapters.trading import (
    load_algo_engine_module,
    query_range_kth,
    query_range_kth_tdigest,
)


def rank_error(values: list[int], estimate: int, k: int) -> int:
    strict_greater = sum(1 for value in values if value > estimate)
    greater_or_equal = sum(1 for value in values if value >= estimate)
    lower_rank = strict_greater + 1
    upper_rank = greater_or_equal
    if lower_rank <= k <= upper_rank:
        return 0
    if k < lower_rank:
        return lower_rank - k
    return k - upper_rank


class TDigestRangeKthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            load_algo_engine_module()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def test_tdigest_matches_exact_results_for_short_intervals(self) -> None:
        values = [100, 250, 250, 80, 300, 125, 400, 400, 50]

        exact = query_range_kth(values, 1, 4, 2)
        approx = query_range_kth_tdigest(values, 1, 4, 2)

        self.assertEqual(approx.kth_value_scaled, exact.kth_value_scaled)
        self.assertEqual(approx.matched_indices, [])
        self.assertTrue(approx.approximation_note)

    def test_tdigest_stays_within_reasonable_rank_error_budget(self) -> None:
        scenarios = {
            "duplicates": [2400 - (index // 32) * 100 for index in range(512)],
            "long_tail": [int(round((1.045**index) * 1000)) for index in range(512)],
            "extremes": [1000 + (index % 7) * 10 for index in range(480)] + [10000 + index * 750 for index in range(32)],
        }
        queries = [
            (0, 511, 1),
            (0, 511, 32),
            (0, 511, 128),
            (64, 255, 24),
            (128, 383, 80),
            (220, 511, 40),
        ]

        max_rank_error = 0
        max_value_error = 0

        for name, values in scenarios.items():
            for left, right, k in queries:
                with self.subTest(scenario=name, left=left, right=right, k=k):
                    exact = query_range_kth(values, left, right, k)
                    approx = query_range_kth_tdigest(values, left, right, k)
                    window = values[left : right + 1]
                    error = rank_error(window, approx.kth_value_scaled, k)
                    max_rank_error = max(max_rank_error, error)
                    max_value_error = max(max_value_error, abs(approx.kth_value_scaled - exact.kth_value_scaled))

                    self.assertLessEqual(error, max(8, len(window) // 10))
                    self.assertGreaterEqual(approx.kth_value_scaled, min(window))
                    self.assertLessEqual(approx.kth_value_scaled, max(window))

        self.assertGreaterEqual(max_value_error, 0)
        self.assertGreaterEqual(max_rank_error, 0)


if __name__ == "__main__":
    unittest.main()
