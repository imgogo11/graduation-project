from __future__ import annotations

import os
from pathlib import Path
import sys
import time
import unittest

from fastapi.testclient import TestClient
import pandas as pd
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "algo_trading"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import create_all_tables, get_session_factory, reset_database_state
from app.algo_bridge.adapters.trading import load_algo_module
from app.models import ImportRun
from app.services.auth import AuthService


def build_algo_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_code": "600519.SH",
                "stock_name": "Kweichow Moutai",
                "trade_date": "2026-01-02",
                "open": 520.15,
                "high": 525.80,
                "low": 518.40,
                "close": 524.30,
                "volume": 12800,
                "amount": 6711040,
            },
            {
                "stock_code": "600519.SH",
                "stock_name": "Kweichow Moutai",
                "trade_date": "2026-01-03",
                "open": 524.30,
                "high": 529.20,
                "low": 522.50,
                "close": 528.70,
                "volume": 13120,
                "amount": 6936544,
            },
            {
                "stock_code": "600519.SH",
                "stock_name": "Kweichow Moutai",
                "trade_date": "2026-01-04",
                "open": 528.70,
                "high": 531.00,
                "low": 526.00,
                "close": 529.10,
                "volume": 13120,
                "amount": 6936544,
            },
            {
                "stock_code": "600519.SH",
                "stock_name": "Kweichow Moutai",
                "trade_date": "2026-01-05",
                "open": 529.10,
                "high": 530.40,
                "low": 521.80,
                "close": 523.60,
                "volume": 12600,
                "amount": 6512000,
            },
        ]
    )


def build_algo_frame_without_amount() -> pd.DataFrame:
    return build_algo_frame().drop(columns=["amount"])


def build_joint_anomaly_frame() -> pd.DataFrame:
    dates = list(pd.date_range("2026-01-01", periods=30, freq="D"))
    configs = {
        "ALPHA": {
            "name": "Alpha Asset",
            "base_close": 100.0,
            "daily_moves": [0.0030, -0.0010, 0.0040, 0.0005, -0.0020],
            "shock_moves": {24: 0.0850, 27: 0.0600},
            "volume_base": 1000.0,
            "volume_step": 15.0,
            "volume_spikes": {24: 4.2, 27: 3.4},
        },
        "BETA": {
            "name": "Beta Asset",
            "base_close": 82.0,
            "daily_moves": [0.0015, 0.0020, -0.0007, 0.0011, -0.0010],
            "shock_moves": {25: 0.0550},
            "volume_base": 860.0,
            "volume_step": 12.0,
            "volume_spikes": {25: 3.7},
        },
        "GAMMA": {
            "name": "Gamma Asset",
            "base_close": 61.0,
            "daily_moves": [-0.0010, 0.0025, 0.0010, -0.0008, 0.0018],
            "shock_moves": {26: 0.0700},
            "volume_base": 720.0,
            "volume_step": 11.0,
            "volume_spikes": {26: 4.0},
        },
    }

    rows: list[dict[str, object]] = []
    for stock_code, config in configs.items():
        previous_close = float(config["base_close"])
        for index, trade_day in enumerate(dates):
            if index == 0:
                close_value = previous_close
            else:
                move = config["daily_moves"][index % len(config["daily_moves"])] + config["shock_moves"].get(index, 0.0)
                close_value = previous_close * (1.0 + move)

            open_value = previous_close if index > 0 else close_value * 0.998
            high_value = max(open_value, close_value) * 1.01
            low_value = min(open_value, close_value) * 0.99
            volume_value = config["volume_base"] + index * config["volume_step"]
            volume_value *= config["volume_spikes"].get(index, 1.0)

            rows.append(
                {
                    "stock_code": stock_code,
                    "stock_name": str(config["name"]),
                    "trade_date": trade_day.strftime("%Y-%m-%d"),
                    "open": round(open_value, 4),
                    "high": round(high_value, 4),
                    "low": round(low_value, 4),
                    "close": round(close_value, 4),
                    "volume": round(volume_value, 4),
                    "amount": round(close_value * volume_value, 4),
                }
            )
            previous_close = close_value

    return pd.DataFrame(rows).sort_values(["stock_code", "trade_date"]).reset_index(drop=True)


def build_expected_joint_anomaly_rows(
    frame: pd.DataFrame,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    top_n: int = 50,
    lookback_window: int = 20,
) -> list[dict[str, object]]:
    working = frame.copy()
    working["trade_date"] = pd.to_datetime(working["trade_date"])
    working["close"] = pd.to_numeric(working["close"])
    working["volume"] = pd.to_numeric(working["volume"])

    events: list[dict[str, object]] = []
    for stock_code, group in working.groupby("stock_code", sort=True):
        enriched = group.sort_values("trade_date").reset_index(drop=True).copy()
        enriched["daily_return"] = enriched["close"].pct_change(fill_method=None)
        enriched["previous_return_std20"] = (
            enriched["daily_return"]
            .shift(1)
            .rolling(window=lookback_window, min_periods=lookback_window)
            .std(ddof=0)
        )
        enriched["previous_volume_mean20"] = (
            enriched["volume"]
            .shift(1)
            .rolling(window=lookback_window, min_periods=lookback_window)
            .mean()
        )
        enriched["return_z20"] = enriched["daily_return"].abs() / enriched["previous_return_std20"]
        enriched["volume_ratio20"] = enriched["volume"] / enriched["previous_volume_mean20"]
        valid = enriched[
            enriched["daily_return"].notna()
            & enriched["previous_return_std20"].notna()
            & enriched["previous_volume_mean20"].notna()
            & (enriched["previous_return_std20"] > 0)
            & (enriched["previous_volume_mean20"] > 0)
        ].copy()

        for row in valid.itertuples(index=False):
            events.append(
                {
                    "stock_code": str(stock_code),
                    "stock_name": str(row.stock_name) if row.stock_name else None,
                    "trade_date": row.trade_date.date().isoformat(),
                    "daily_return": float(row.daily_return),
                    "return_z20": float(row.return_z20),
                    "volume_ratio20": float(row.volume_ratio20),
                }
            )

    events.sort(key=lambda item: (item["trade_date"], item["stock_code"]))

    def classify(percentile: float) -> str | None:
        if percentile >= 0.99:
            return "critical"
        if percentile >= 0.95:
            return "high"
        if percentile >= 0.90:
            return "medium"
        return None

    filtered_rows: list[dict[str, object]] = []
    for index, event in enumerate(events):
        dominated_count = sum(
            1
            for previous_event in events[:index]
            if previous_event["return_z20"] <= event["return_z20"]
            and previous_event["volume_ratio20"] <= event["volume_ratio20"]
        )
        percentile = (dominated_count / index) if index else 0.0
        severity = classify(percentile)
        if severity is None:
            continue
        if start_date and event["trade_date"] < start_date:
            continue
        if end_date and event["trade_date"] > end_date:
            continue

        filtered_rows.append(
            {
                **event,
                "historical_dominated_count": dominated_count,
                "historical_sample_count": index,
                "joint_percentile": round(percentile, 6),
                "severity": severity,
            }
        )

    filtered_rows.sort(
        key=lambda item: (
            item["joint_percentile"],
            item["historical_dominated_count"],
            item["return_z20"],
            item["volume_ratio20"],
            pd.Timestamp(item["trade_date"]).toordinal(),
        ),
        reverse=True,
    )
    return filtered_rows[:top_n]


class AlgoTradingRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            load_algo_module()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def setUp(self) -> None:
        self.temp_path = ARTIFACT_ROOT / f"case_{time.time_ns()}"
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_path / "algo.sqlite3"
        self.previous_env = {
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "APP_ENV": os.environ.get("APP_ENV"),
            "JWT_SECRET": os.environ.get("JWT_SECRET"),
            "ADMIN_USERNAME": os.environ.get("ADMIN_USERNAME"),
            "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD"),
            "UPLOAD_ROOT": os.environ.get("UPLOAD_ROOT"),
        }
        os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{self.db_path.resolve().as_posix()}"
        os.environ["APP_ENV"] = "test"
        os.environ["JWT_SECRET"] = "algo-test-secret"
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "admin123456"
        os.environ["UPLOAD_ROOT"] = str((self.temp_path / "uploads").resolve())
        reset_database_state()
        create_all_tables()
        session = get_session_factory()()
        try:
            AuthService().ensure_admin_user(session, username="admin", password="admin123456")
        finally:
            session.close()

        from app.main import app

        self.client = TestClient(app)
        self.token = self._register_and_login("alice_user", "password123")
        self.run = self._upload_csv(
            token=self.token,
            dataset_name="algo_case",
            frame=build_algo_frame(),
        )

    def tearDown(self) -> None:
        self.client.close()
        reset_database_state()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_range_max_amount_returns_all_duplicate_max_dates(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
            },
            headers=self._auth_headers(self.token),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stock_code"], "600519.SH")
        self.assertEqual(body["max_amount"], "6936544.0000")
        self.assertEqual([item["trade_date"] for item in body["matches"]], ["2026-01-03", "2026-01-04"])
        self.assertEqual([item["series_index"] for item in body["matches"]], [1, 2])

    def test_range_max_amount_rejects_invalid_date_range(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-05",
                "end_date": "2026-01-02",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 400)

    def test_range_max_amount_returns_404_when_interval_has_no_data(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 404)

    def test_range_max_amount_reports_data_insufficient_when_amount_is_missing(self) -> None:
        run = self._upload_csv(
            token=self.token,
            dataset_name="algo_no_amount",
            frame=build_algo_frame_without_amount(),
        )

        response = self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("数据不足分析", response.json()["detail"])

    def test_range_kth_volume_returns_duplicate_matches_for_counted_rank(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 2,
            },
            headers=self._auth_headers(self.token),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stock_code"], "600519.SH")
        self.assertEqual(body["k"], 2)
        self.assertEqual(body["value"], "13120.0000")
        self.assertEqual(body["method"], "persistent_segment_tree")
        self.assertFalse(body["is_approx"])
        self.assertEqual([item["trade_date"] for item in body["matches"]], ["2026-01-03", "2026-01-04"])
        self.assertEqual([item["series_index"] for item in body["matches"]], [1, 2])

    def test_range_kth_volume_rejects_k_out_of_range(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 5,
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 400)

    def test_range_kth_volume_tdigest_returns_approximate_result_without_matches(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 2,
                "method": "t_digest",
            },
            headers=self._auth_headers(self.token),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stock_code"], "600519.SH")
        self.assertEqual(body["k"], 2)
        self.assertEqual(body["value"], "13120.0000")
        self.assertEqual(body["method"], "t_digest")
        self.assertTrue(body["is_approx"])
        self.assertEqual(body["matches"], [])
        self.assertIsInstance(body["approximation_note"], str)
        self.assertTrue(body["approximation_note"])

    def test_range_kth_volume_tdigest_supports_boundary_ranks(self) -> None:
        largest = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 1,
                "method": "t_digest",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(largest.status_code, 200)
        self.assertEqual(largest.json()["value"], "13120.0000")

        smallest = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 4,
                "method": "t_digest",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(smallest.status_code, 200)
        self.assertEqual(smallest.json()["value"], "12600.0000")

    def test_range_kth_volume_tdigest_supports_short_intervals(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-03",
                "end_date": "2026-01-04",
                "k": 1,
                "method": "t_digest",
            },
            headers=self._auth_headers(self.token),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["value"], "13120.0000")
        self.assertEqual(body["matches"], [])

    def test_range_kth_volume_rejects_unsupported_method(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 2,
                "method": "not_supported",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 400)

    def test_joint_anomaly_ranking_returns_expected_rows(self) -> None:
        frame = build_joint_anomaly_frame()
        run = self._upload_csv(
            token=self.token,
            dataset_name="joint_anomaly_case",
            frame=frame,
        )

        response = self.client.get(
            "/api/algo/trading/joint-anomaly-ranking",
            params={
                "import_run_id": run["id"],
                "start_date": "2026-01-24",
                "top_n": 5,
            },
            headers=self._auth_headers(self.token),
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["lookback_window"], 20)

        expected_rows = build_expected_joint_anomaly_rows(
            frame,
            start_date="2026-01-24",
            top_n=5,
        )
        self.assertEqual(len(body["rows"]), len(expected_rows))

        for actual_row, expected_row in zip(body["rows"], expected_rows, strict=True):
            self.assertEqual(actual_row["stock_code"], expected_row["stock_code"])
            self.assertEqual(actual_row["stock_name"], expected_row["stock_name"])
            self.assertEqual(actual_row["trade_date"], expected_row["trade_date"])
            self.assertEqual(actual_row["severity"], expected_row["severity"])
            self.assertEqual(actual_row["historical_dominated_count"], expected_row["historical_dominated_count"])
            self.assertEqual(actual_row["historical_sample_count"], expected_row["historical_sample_count"])
            self.assertAlmostEqual(float(actual_row["daily_return"]), expected_row["daily_return"], places=6)
            self.assertAlmostEqual(float(actual_row["return_z20"]), expected_row["return_z20"], places=6)
            self.assertAlmostEqual(float(actual_row["volume_ratio20"]), expected_row["volume_ratio20"], places=6)
            self.assertAlmostEqual(float(actual_row["joint_percentile"]), expected_row["joint_percentile"], places=6)

    def test_joint_anomaly_ranking_rejects_invalid_top_n(self) -> None:
        frame = build_joint_anomaly_frame()
        run = self._upload_csv(
            token=self.token,
            dataset_name="joint_anomaly_case_invalid_top_n",
            frame=frame,
        )

        response = self.client.get(
            "/api/algo/trading/joint-anomaly-ranking",
            params={"import_run_id": run["id"], "top_n": 0},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 400)

    def test_joint_anomaly_ranking_reports_data_insufficient_when_history_is_too_short(self) -> None:
        response = self.client.get(
            "/api/algo/trading/joint-anomaly-ranking",
            params={"import_run_id": self.run["id"], "top_n": 5},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("数据不足分析", response.json()["detail"])

    def test_range_kth_volume_enforces_visibility_and_admin_can_access(self) -> None:
        bob_token = self._register_and_login("bob_user", "password123")
        admin_token = self._login("admin", "admin123456")

        forbidden = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 1,
            },
            headers=self._auth_headers(bob_token),
        )
        self.assertEqual(forbidden.status_code, 404)

        allowed = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 1,
            },
            headers=self._auth_headers(admin_token),
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["value"], "13120.0000")

    def test_range_kth_volume_tdigest_enforces_visibility_and_admin_can_access(self) -> None:
        bob_token = self._register_and_login("bob_tdigest", "password123")
        admin_token = self._login("admin", "admin123456")

        forbidden = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 2,
                "method": "t_digest",
            },
            headers=self._auth_headers(bob_token),
        )
        self.assertEqual(forbidden.status_code, 404)

        allowed = self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run["id"],
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "k": 2,
                "method": "t_digest",
            },
            headers=self._auth_headers(admin_token),
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()["is_approx"])

    def test_joint_anomaly_ranking_enforces_visibility_and_admin_can_access(self) -> None:
        frame = build_joint_anomaly_frame()
        run = self._upload_csv(
            token=self.token,
            dataset_name="joint_anomaly_visibility",
            frame=frame,
        )
        bob_token = self._register_and_login("bob_joint", "password123")
        admin_token = self._login("admin", "admin123456")

        forbidden = self.client.get(
            "/api/algo/trading/joint-anomaly-ranking",
            params={"import_run_id": run["id"], "top_n": 5},
            headers=self._auth_headers(bob_token),
        )
        self.assertEqual(forbidden.status_code, 404)

        allowed = self.client.get(
            "/api/algo/trading/joint-anomaly-ranking",
            params={"import_run_id": run["id"], "top_n": 5},
            headers=self._auth_headers(admin_token),
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(allowed.json()["lookback_window"], 20)

    def test_failed_runs_are_hidden_from_algo_endpoints(self) -> None:
        invalid_frame = build_algo_frame().drop(columns=["stock_code"])

        failed_response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": "algo_failed"},
            files={
                "file": (
                    "invalid.csv",
                    invalid_frame.to_csv(index=False).encode("utf-8"),
                    "text/csv",
                )
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(failed_response.status_code, 400)

        failed_run_id = self._find_run_id(dataset_name="algo_failed", status="failed")

        response = self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": failed_run_id,
                "stock_code": "600519.SH",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 404)

    def _register_and_login(self, username: str, password: str) -> str:
        self.client.post("/api/auth/register", json={"username": username, "password": password})
        return self._login(username, password)

    def _login(self, username: str, password: str) -> str:
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _upload_csv(self, *, token: str, dataset_name: str, frame: pd.DataFrame) -> dict[str, object]:
        csv_text = frame.to_csv(index=False)
        response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": dataset_name},
            files={"file": ("trading.csv", csv_text.encode("utf-8"), "text/csv")},
            headers=self._auth_headers(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _find_run_id(self, *, dataset_name: str, status: str) -> int:
        session = get_session_factory()()
        try:
            run = session.scalar(
                select(ImportRun)
                .where(ImportRun.dataset_name == dataset_name)
                .where(ImportRun.status == status)
                .order_by(ImportRun.id.desc())
            )
            self.assertIsNotNone(run)
            return int(run.id)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()

