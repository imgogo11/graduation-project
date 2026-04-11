from __future__ import annotations

import os
from pathlib import Path
import sys
import time
import unittest

from fastapi.testclient import TestClient
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "risk_radar"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import create_all_tables, reset_database_state
from app.engine_bridge.adapters.trading import load_algo_engine_module
from app.services.algo_indexes import algo_index_manager
from app.services.auth import AuthService


def build_risk_radar_frame() -> pd.DataFrame:
    dates = list(pd.date_range("2026-01-01", periods=35, freq="D"))
    configs = {
        "ALPHA": {
            "name": "Alpha Asset",
            "base_close": 100.0,
            "daily_moves": [0.0030, -0.0010, 0.0040, 0.0005, -0.0020],
            "shock_moves": {24: 0.0850, 27: 0.0600},
            "volume_base": 1000.0,
            "volume_step": 15.0,
            "volume_spikes": {24: 4.2, 27: 3.4},
            "amplitude_spikes": {24: 0.11, 27: 0.08},
        },
        "BETA": {
            "name": "Beta Asset",
            "base_close": 82.0,
            "daily_moves": [0.0015, 0.0020, -0.0007, 0.0011, -0.0010],
            "shock_moves": {25: 0.0550},
            "volume_base": 860.0,
            "volume_step": 12.0,
            "volume_spikes": {25: 3.7},
            "amplitude_spikes": {25: 0.095},
        },
        "GAMMA": {
            "name": "Gamma Asset",
            "base_close": 61.0,
            "daily_moves": [-0.0010, 0.0025, 0.0010, -0.0008, 0.0018],
            "shock_moves": {26: 0.0700},
            "volume_base": 720.0,
            "volume_step": 11.0,
            "volume_spikes": {26: 4.0},
            "amplitude_spikes": {26: 0.10},
        },
    }

    rows: list[dict[str, object]] = []
    for instrument_code, config in configs.items():
        previous_close = float(config["base_close"])
        for index, trade_day in enumerate(dates):
            if index == 0:
                close_value = previous_close
            else:
                move = config["daily_moves"][index % len(config["daily_moves"])] + config["shock_moves"].get(index, 0.0)
                close_value = previous_close * (1.0 + move)

            open_value = previous_close if index > 0 else close_value * 0.998
            amplitude = config["amplitude_spikes"].get(index, 0.025)
            high_value = max(open_value, close_value) * (1.0 + amplitude / 2.0)
            low_value = min(open_value, close_value) * (1.0 - amplitude / 2.0)
            volume_value = config["volume_base"] + index * config["volume_step"]
            volume_value *= config["volume_spikes"].get(index, 1.0)

            rows.append(
                {
                    "instrument_code": instrument_code,
                    "instrument_name": str(config["name"]),
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

    return pd.DataFrame(rows).sort_values(["instrument_code", "trade_date"]).reset_index(drop=True)


class RiskRadarRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            load_algo_engine_module()
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def setUp(self) -> None:
        self.temp_path = ARTIFACT_ROOT / f"case_{time.time_ns()}"
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_path / "risk-radar.sqlite3"
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
        os.environ["JWT_SECRET"] = "risk-radar-test-secret"
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
        self.token = self._register_and_login("radar_user", "password123")
        self.run = self._upload_csv(token=self.token, dataset_name="risk_radar_case", frame=build_risk_radar_frame())

    def tearDown(self) -> None:
        self.client.close()
        reset_database_state()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_algo_index_status_and_rebuild_flow(self) -> None:
        status_response = self.client.get(
            "/api/algo/indexes/status",
            params={"import_run_id": self.run["id"]},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertEqual(status_response.json()["status"], "ready")
        self.assertTrue(status_response.json()["is_ready"])
        self.assertGreaterEqual(status_response.json()["instrument_count"], 3)
        self.assertGreater(status_response.json()["event_count"], 0)

        algo_index_manager.invalidate(int(self.run["id"]))
        algo_index_manager.prepare_after_import(int(self.run["id"]))

        pending_response = self.client.get(
            "/api/algo/indexes/status",
            params={"import_run_id": self.run["id"]},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(pending_response.json()["status"], "pending")

        rebuild_response = self.client.post(
            "/api/algo/indexes/rebuild",
            params={"import_run_id": self.run["id"]},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(rebuild_response.status_code, 200, rebuild_response.text)
        self.assertEqual(rebuild_response.json()["status"], "ready")

    def test_risk_radar_overview_events_and_context(self) -> None:
        overview_response = self.client.get(
            "/api/algo/risk-radar/overview",
            params={"import_run_id": self.run["id"]},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(overview_response.status_code, 200, overview_response.text)
        overview = overview_response.json()
        self.assertGreater(overview["total_events"], 0)
        self.assertGreater(overview["impacted_instrument_count"], 0)
        self.assertTrue(overview["top_instruments"])
        self.assertTrue(overview["busiest_dates"])

        events_response = self.client.get(
            "/api/algo/risk-radar/events",
            params={"import_run_id": self.run["id"], "top_n": 5},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(events_response.status_code, 200, events_response.text)
        events = events_response.json()["rows"]
        self.assertTrue(events)
        self.assertIn("amplitude_ratio20", events[0])
        self.assertTrue(events[0]["cause_label"])

        calendar_response = self.client.get(
            "/api/algo/risk-radar/calendar",
            params={"import_run_id": self.run["id"]},
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(calendar_response.status_code, 200, calendar_response.text)
        self.assertTrue(calendar_response.json()["rows"])

        event = events[0]
        context_response = self.client.get(
            "/api/algo/risk-radar/event-context",
            params={
                "import_run_id": self.run["id"],
                "instrument_code": event["instrument_code"],
                "trade_date": event["trade_date"],
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(context_response.status_code, 200, context_response.text)
        context = context_response.json()
        self.assertEqual(len(context["volume_windows"]), 3)
        self.assertEqual(len(context["amplitude_windows"]), 3)
        self.assertEqual(len(context["distribution_changes"]), 2)
        self.assertIsNotNone(context["local_amount_peak"])

    def _register_and_login(self, username: str, password: str) -> str:
        self.client.post("/api/auth/register", json={"username": username, "password": password})
        return self._login(username, password)

    def _login(self, username: str, password: str) -> str:
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _upload_csv(self, *, token: str, dataset_name: str, frame: pd.DataFrame) -> dict[str, object]:
        response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": dataset_name},
            files={"file": ("trading.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv")},
            headers=self._auth_headers(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}


from app.core.database import get_session_factory  # noqa: E402


if __name__ == "__main__":
    unittest.main()
