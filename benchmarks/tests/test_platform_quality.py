from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.platform_quality.run import build_history_rows, build_request_rows  # noqa: E402


class PlatformQualityRunTests(unittest.TestCase):
    def test_build_request_rows_skips_setup_and_aggregated_rows(self) -> None:
        rows = build_request_rows(
            [
                {
                    "Type": "GET",
                    "Name": "algo/range_max_amount",
                    "Request Count": "12",
                    "Failure Count": "0",
                    "Average Response Time": "7.25",
                    "95%": "13",
                    "Requests/s": "0.4",
                },
                {
                    "Type": "GET",
                    "Name": "setup/instruments",
                    "Request Count": "1",
                    "Failure Count": "0",
                    "Average Response Time": "2.1",
                    "95%": "3",
                    "Requests/s": "0.1",
                },
                {
                    "Type": "",
                    "Name": "Aggregated",
                    "Request Count": "13",
                    "Failure Count": "0",
                    "Average Response Time": "6.9",
                    "95%": "12",
                    "Requests/s": "0.5",
                },
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "algo/range_max_amount")
        self.assertEqual(rows[0]["request_count"], 12)
        self.assertEqual(rows[0]["avg_ms"], 7.25)
        self.assertEqual(rows[0]["p95_ms"], 13.0)

    def test_build_history_rows_uses_total_average_and_latest_row_per_user_count(self) -> None:
        rows = build_history_rows(
            [
                {
                    "Name": "Aggregated",
                    "User Count": "0",
                    "Total Request Count": "0",
                    "Total Average Response Time": "0.0",
                    "95%": "N/A",
                },
                {
                    "Name": "Aggregated",
                    "User Count": "4",
                    "Total Request Count": "15",
                    "Total Average Response Time": "52.5",
                    "95%": "120",
                },
                {
                    "Name": "Aggregated",
                    "User Count": "2",
                    "Total Request Count": "8",
                    "Total Average Response Time": "31.4",
                    "95%": "60",
                },
                {
                    "Name": "Aggregated",
                    "User Count": "4",
                    "Total Request Count": "24",
                    "Total Average Response Time": "18.2",
                    "95%": "24",
                },
            ]
        )

        self.assertEqual(
            rows,
            [
                {"user_count": 2, "total_request_count": 8, "avg_ms": 31.4, "p95_ms": 60.0},
                {"user_count": 4, "total_request_count": 24, "avg_ms": 18.2, "p95_ms": 24.0},
            ],
        )


if __name__ == "__main__":
    unittest.main()
