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
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "admin_dashboard"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import create_all_tables, reset_database_state
from app.services.auth import AuthService


def build_trading_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "stock_code": "600519.SH",
                "stock_name": "Kweichow Moutai",
                "trade_date": "2026-01-02",
                "open": 1520.15,
                "high": 1535.80,
                "low": 1518.40,
                "close": 1534.30,
                "volume": 12800,
                "amount": 19639040,
            },
            {
                "stock_code": "600519.SH",
                "stock_name": "Kweichow Moutai",
                "trade_date": "2026-01-03",
                "open": 1534.30,
                "high": 1548.20,
                "low": 1529.50,
                "close": 1541.70,
                "volume": 13120,
                "amount": 20274816,
            },
        ]
    )


class AdminDashboardRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_path = ARTIFACT_ROOT / f"case_{time.time_ns()}"
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_path / "admin-dashboard.sqlite3"
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
        os.environ["JWT_SECRET"] = "admin-dashboard-secret"
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
        self.admin_token = self._login("admin", "admin123456")
        self.user_token = self._register_and_login("dashboard_user", "password123")

    def tearDown(self) -> None:
        self.client.close()
        reset_database_state()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_admin_routes_return_overview_logs_stats_and_runs_monitor(self) -> None:
        upload_response = self._upload_csv(self.user_token, "dashboard_dataset", build_trading_frame())
        run_id = int(upload_response["id"])

        analysis_response = self.client.get(
            "/api/trading/analysis/summary",
            params={"import_run_id": run_id},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(analysis_response.status_code, 200, analysis_response.text)

        admin_overview = self.client.get("/api/admin/overview", headers=self._auth_headers(self.admin_token))
        self.assertEqual(admin_overview.status_code, 200, admin_overview.text)
        overview_body = admin_overview.json()
        self.assertGreaterEqual(overview_body["metrics"]["total_users"], 1)
        self.assertGreaterEqual(overview_body["metrics"]["total_runs"], 1)
        self.assertGreaterEqual(len(overview_body["recent_audit_logs"]), 1)

        audit_logs = self.client.get(
            "/api/admin/audit-logs",
            params={"page": 1, "page_size": 50},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(audit_logs.status_code, 200, audit_logs.text)
        logs_body = audit_logs.json()
        self.assertGreaterEqual(logs_body["total"], 1)
        categories = {item["category"] for item in logs_body["rows"]}
        self.assertIn("auth", categories)
        self.assertIn("data_ops", categories)
        self.assertIn("analysis_access", categories)

        stats_response = self.client.get("/api/admin/audit-logs/stats", headers=self._auth_headers(self.admin_token))
        self.assertEqual(stats_response.status_code, 200, stats_response.text)
        stats_body = stats_response.json()
        self.assertGreaterEqual(stats_body["total_events"], 1)
        self.assertGreaterEqual(stats_body["unique_actor_count"], 1)

        monitor_response = self.client.get("/api/admin/runs/monitor", headers=self._auth_headers(self.admin_token))
        self.assertEqual(monitor_response.status_code, 200, monitor_response.text)
        monitor_body = monitor_response.json()
        run_ids = {item["import_run_id"] for item in monitor_body["rows"]}
        self.assertIn(run_id, run_ids)

    def test_non_admin_cannot_access_admin_dashboard_routes(self) -> None:
        for endpoint in (
            "/api/admin/overview",
            "/api/admin/audit-logs",
            "/api/admin/audit-logs/stats",
            "/api/admin/runs/monitor",
        ):
            response = self.client.get(endpoint, headers=self._auth_headers(self.user_token))
            self.assertEqual(response.status_code, 403, response.text)

    def test_audit_log_stats_supports_success_filter(self) -> None:
        failed_login = self.client.post(
            "/api/auth/login",
            json={"username": "dashboard_user", "password": "wrong-password"},
        )
        self.assertEqual(failed_login.status_code, 401, failed_login.text)

        failed_stats = self.client.get(
            "/api/admin/audit-logs/stats",
            params={"success": "false"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(failed_stats.status_code, 200, failed_stats.text)
        failed_payload = failed_stats.json()
        self.assertGreaterEqual(failed_payload["total_events"], 1)
        self.assertEqual(failed_payload["failed_events"], failed_payload["total_events"])
        self.assertEqual(failed_payload["success_events"], 0)

        success_stats = self.client.get(
            "/api/admin/audit-logs/stats",
            params={"success": "true"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(success_stats.status_code, 200, success_stats.text)
        success_payload = success_stats.json()
        self.assertGreaterEqual(success_payload["total_events"], 1)
        self.assertEqual(success_payload["success_events"], success_payload["total_events"])
        self.assertEqual(success_payload["failed_events"], 0)

    def test_overview_includes_register_and_auto_login_for_new_user(self) -> None:
        register_response = self.client.post(
            "/api/auth/register",
            json={"username": "gogo11", "password": "password123"},
        )
        self.assertEqual(register_response.status_code, 200, register_response.text)

        admin_overview = self.client.get("/api/admin/overview", headers=self._auth_headers(self.admin_token))
        self.assertEqual(admin_overview.status_code, 200, admin_overview.text)
        rows = admin_overview.json()["recent_audit_logs"]

        self.assertTrue(
            any(
                item["category"] == "auth"
                and item["event_type"] == "register"
                and item["actor_username_snapshot"] == "gogo11"
                and item["success"] is True
                for item in rows
            )
        )
        self.assertTrue(
            any(
                item["category"] == "auth"
                and item["event_type"] == "login"
                and item["actor_username_snapshot"] == "gogo11"
                and item["success"] is True
                for item in rows
            )
        )

    def _register_and_login(self, username: str, password: str) -> str:
        self.client.post("/api/auth/register", json={"username": username, "password": password})
        return self._login(username, password)

    def _login(self, username: str, password: str) -> str:
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _upload_csv(self, token: str, dataset_name: str, frame: pd.DataFrame) -> dict[str, object]:
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
