from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import sys
import time
import unittest

from fastapi.testclient import TestClient
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "database_pipeline"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import create_all_tables, get_session_factory, reset_database_state
from app.models import ImportRun, utc_now
from app.services.auth import AuthService


def build_trading_frame() -> pd.DataFrame:
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
                "instrument_code": "CU2406",
                "instrument_name": "Copper Futures",
                "trade_date": "2026-01-02",
                "open": 68320.00,
                "high": 68980.00,
                "low": 68050.00,
                "close": 68810.00,
                "volume": 982,
                "amount": 67571420,
            },
        ]
    )


class DatabasePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_path = ARTIFACT_ROOT / f"case_{time.time_ns()}"
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_path / "pipeline.sqlite3"
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
        os.environ["JWT_SECRET"] = "unit-test-secret"
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

    def tearDown(self) -> None:
        self.client.close()
        reset_database_state()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_auth_endpoints_and_protected_routes(self) -> None:
        response = self.client.post(
            "/api/auth/register",
            json={"username": "alice_user", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user"]["username"], "alice_user")
        self.assertEqual(body["user"]["role"], "user")
        self.assertTrue(body["access_token"])

        duplicate_response = self.client.post(
            "/api/auth/register",
            json={"username": "alice_user", "password": "password123"},
        )
        self.assertEqual(duplicate_response.status_code, 409)

        invalid_login = self.client.post(
            "/api/auth/login",
            json={"username": "alice_user", "password": "wrong-password"},
        )
        self.assertEqual(invalid_login.status_code, 401)

        login_response = self.client.post(
            "/api/auth/login",
            json={"username": "alice_user", "password": "password123"},
        )
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()["access_token"]

        protected_response = self.client.get("/api/imports/runs")
        self.assertEqual(protected_response.status_code, 401)

        me_response = self.client.get("/api/auth/me", headers=self._auth_headers(token))
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["username"], "alice_user")

    def test_upload_permissions_stats_and_soft_delete(self) -> None:
        alice_token = self._register_and_login("alice_user", "password123")
        bob_token = self._register_and_login("bob_user", "password123")
        admin_token = self._login("admin", "admin123456")

        alice_csv_run = self._upload_csv(
            token=alice_token,
            dataset_name="alice_gold_csv",
            asset_class="commodity",
            frame=build_trading_frame(),
        )
        alice_xlsx_run = self._upload_xlsx(
            token=alice_token,
            dataset_name="alice_gold_xlsx",
            asset_class="commodity",
            frame=build_trading_frame(),
        )
        alice_third_run = self._upload_csv(
            token=alice_token,
            dataset_name="alice_gold_csv_2",
            asset_class="commodity",
            frame=build_trading_frame(),
        )
        bob_run = self._upload_csv(
            token=bob_token,
            dataset_name="bob_stock_csv",
            asset_class="stock",
            frame=build_trading_frame(),
        )
        self.assertEqual(alice_csv_run["display_id"], 1)
        self.assertEqual(alice_xlsx_run["display_id"], 2)
        self.assertEqual(alice_third_run["display_id"], 3)
        self.assertEqual(bob_run["display_id"], 1)
        self._insert_legacy_run(
            owner_user_id=int(alice_csv_run["owner_user_id"]),
            dataset_name="legacy_retired_run",
        )

        alice_runs = self.client.get("/api/imports/runs", headers=self._auth_headers(alice_token))
        self.assertEqual(alice_runs.status_code, 200)
        alice_run_rows = alice_runs.json()
        self.assertEqual(len(alice_run_rows), 3)
        self.assertTrue(all(item["owner_username"] == "alice_user" for item in alice_run_rows))
        self.assertEqual(
            [item["id"] for item in alice_run_rows],
            [alice_third_run["id"], alice_xlsx_run["id"], alice_csv_run["id"]],
        )
        self.assertEqual([item["display_id"] for item in alice_run_rows], [3, 2, 1])

        alice_stats = self.client.get("/api/imports/stats", headers=self._auth_headers(alice_token))
        self.assertEqual(alice_stats.status_code, 200)
        self.assertEqual(alice_stats.json()["total_runs"], 3)
        self.assertEqual(alice_stats.json()["completed_runs"], 3)

        instruments = self.client.get(
            "/api/trading/instruments",
            params={"import_run_id": alice_csv_run["id"]},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(instruments.status_code, 200)
        self.assertEqual(len(instruments.json()), 2)

        records = self.client.get(
            "/api/trading/records",
            params={"import_run_id": alice_csv_run["id"], "instrument_code": "AU9999"},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(records.status_code, 200)
        self.assertEqual(len(records.json()), 2)

        forbidden_to_bob = self.client.get(
            "/api/trading/instruments",
            params={"import_run_id": alice_csv_run["id"]},
            headers=self._auth_headers(bob_token),
        )
        self.assertEqual(forbidden_to_bob.status_code, 404)

        admin_runs = self.client.get("/api/imports/runs", headers=self._auth_headers(admin_token))
        self.assertEqual(admin_runs.status_code, 200)
        admin_run_rows = admin_runs.json()
        self.assertEqual(len(admin_run_rows), 4)
        self.assertEqual({item["owner_username"] for item in admin_run_rows}, {"alice_user", "bob_user"})
        self.assertNotIn("legacy_retired_run", {item["dataset_name"] for item in admin_run_rows})
        self.assertEqual([item["display_id"] for item in admin_run_rows], [4, 3, 2, 1])

        admin_filtered = self.client.get(
            "/api/imports/runs",
            params={"owner_user_id": bob_run["owner_user_id"]},
            headers=self._auth_headers(admin_token),
        )
        self.assertEqual(admin_filtered.status_code, 200)
        self.assertEqual(len(admin_filtered.json()), 1)
        self.assertEqual(admin_filtered.json()[0]["owner_username"], "bob_user")
        self.assertEqual(admin_filtered.json()[0]["display_id"], 1)

        delete_response = self.client.delete(
            f"/api/imports/runs/{alice_csv_run['id']}",
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], "deleted")

        after_delete_runs = self.client.get("/api/imports/runs", headers=self._auth_headers(alice_token))
        self.assertEqual(after_delete_runs.status_code, 200)
        after_delete_rows = after_delete_runs.json()
        self.assertEqual(len(after_delete_rows), 2)
        self.assertEqual(
            [item["id"] for item in after_delete_rows],
            [alice_third_run["id"], alice_xlsx_run["id"]],
        )
        self.assertEqual([item["display_id"] for item in after_delete_rows], [2, 1])

        deleted_records = self.client.get(
            "/api/trading/records",
            params={"import_run_id": alice_csv_run["id"], "instrument_code": "AU9999"},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(deleted_records.status_code, 404)

    def _register_and_login(self, username: str, password: str) -> str:
        self.client.post("/api/auth/register", json={"username": username, "password": password})
        return self._login(username, password)

    def _login(self, username: str, password: str) -> str:
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

    def _upload_xlsx(self, *, token: str, dataset_name: str, asset_class: str, frame: pd.DataFrame) -> dict[str, object]:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False)
        response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": dataset_name, "asset_class": asset_class},
            files={
                "file": (
                    "trading.xlsx",
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=self._auth_headers(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _insert_legacy_run(self, *, owner_user_id: int, dataset_name: str) -> None:
        session = get_session_factory()()
        try:
            session.add(
                ImportRun(
                    owner_user_id=owner_user_id,
                    dataset_name=dataset_name,
                    asset_class="stock",
                    source_type="legacy",
                    source_name="retired.import.path",
                    source_uri=None,
                    original_file_name=None,
                    file_format=None,
                    status="completed",
                    started_at=utc_now(),
                    completed_at=utc_now(),
                    deleted_at=None,
                    record_count=1449,
                    error_message=None,
                    metadata_json={"retired": True},
                )
            )
            session.commit()
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
