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
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "algo_trading"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import create_all_tables, get_session_factory, reset_database_state
from app.engine_bridge.adapters.trading import load_algo_engine_module
from app.services.auth import AuthService


def build_algo_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "instrument_code": "AU9999",
                "instrument_name": "Shanghai Gold",
                "trade_date": "2026-01-02",
                "open": 520.15,
                "high": 525.80,
                "low": 518.40,
                "close": 524.30,
                "volume": 12800,
                "amount": 6711040,
            },
            {
                "instrument_code": "AU9999",
                "instrument_name": "Shanghai Gold",
                "trade_date": "2026-01-03",
                "open": 524.30,
                "high": 529.20,
                "low": 522.50,
                "close": 528.70,
                "volume": 13120,
                "amount": 6936544,
            },
            {
                "instrument_code": "AU9999",
                "instrument_name": "Shanghai Gold",
                "trade_date": "2026-01-04",
                "open": 528.70,
                "high": 531.00,
                "low": 526.00,
                "close": 529.10,
                "volume": 12990,
                "amount": 6936544,
            },
            {
                "instrument_code": "AU9999",
                "instrument_name": "Shanghai Gold",
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


class AlgoTradingRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            load_algo_engine_module()
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
            asset_class="commodity",
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
                "instrument_code": "AU9999",
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
            },
            headers=self._auth_headers(self.token),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["instrument_code"], "AU9999")
        self.assertEqual(body["max_amount"], "6936544.0000")
        self.assertEqual([item["trade_date"] for item in body["matches"]], ["2026-01-03", "2026-01-04"])
        self.assertEqual([item["series_index"] for item in body["matches"]], [1, 2])

    def test_range_max_amount_rejects_invalid_date_range(self) -> None:
        response = self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": self.run["id"],
                "instrument_code": "AU9999",
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
                "instrument_code": "AU9999",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
            headers=self._auth_headers(self.token),
        )
        self.assertEqual(response.status_code, 404)

    def _register_and_login(self, username: str, password: str) -> str:
        self.client.post("/api/auth/register", json={"username": username, "password": password})
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _upload_csv(self, *, token: str, dataset_name: str, asset_class: str, frame: pd.DataFrame) -> dict[str, object]:
        csv_text = frame.to_csv(index=False)
        response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": dataset_name, "asset_class": asset_class},
            files={"file": ("trading.csv", csv_text.encode("utf-8"), "text/csv")},
            headers=self._auth_headers(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}


if __name__ == "__main__":
    unittest.main()
