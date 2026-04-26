from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from app.core.database import get_session_factory
from app.models import ImportRun, utc_now
from app.services.auth import AuthService
from postgres_integration import PostgresIntegrationTestCase


def build_trading_frame(stock_code: str = "600519.SH", start_date: str = "2026-01-02") -> pd.DataFrame:
    trade_day = pd.Timestamp(start_date)
    next_day = trade_day + pd.Timedelta(days=1)
    return pd.DataFrame(
        [
            {
                "stock_code": stock_code,
                "stock_name": f"Stock {stock_code}",
                "trade_date": trade_day.strftime("%Y-%m-%d"),
                "open": 1520.15,
                "high": 1535.80,
                "low": 1518.40,
                "close": 1534.30,
                "volume": 12800,
                "amount": 19639040,
            },
            {
                "stock_code": stock_code,
                "stock_name": f"Stock {stock_code}",
                "trade_date": next_day.strftime("%Y-%m-%d"),
                "open": 1534.30,
                "high": 1548.20,
                "low": 1529.50,
                "close": 1541.70,
                "volume": 13120,
                "amount": 20274816,
            },
        ]
    )


class AdminDashboardRouteTests(PostgresIntegrationTestCase):
    jwt_secret = "admin-dashboard-secret"

    def setUp(self) -> None:
        super().setUp()
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
        super().tearDown()

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

    def test_admin_assets_overview_returns_empty_payload_without_completed_assets(self) -> None:
        response = self.client.get("/api/admin/assets/overview", headers=self._auth_headers(self.admin_token))
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["summary"]["owner_count"], 0)
        self.assertEqual(body["summary"]["unique_stock_count"], 0)
        self.assertEqual(body["summary"]["largest_dataset_records"], 0)
        self.assertEqual(body["summary"]["median_dataset_records"], 0.0)
        self.assertIsNone(body["summary"]["first_trade_date"])
        self.assertIsNone(body["summary"]["last_trade_date"])
        self.assertIsNone(body["summary"]["latest_imported_at"])
        self.assertEqual(body["growth"], [])
        self.assertEqual(body["growth_daily"], [])
        self.assertEqual(body["size_buckets"], [])
        self.assertEqual(body["owner_rows"], [])
        self.assertEqual(body["top_datasets"], [])

    def test_admin_assets_overview_aggregates_completed_assets_only(self) -> None:
        second_user_token = self._register_and_login("asset_user_b", "password123")

        alpha = self._upload_csv(
            self.user_token,
            "asset_alpha",
            build_trading_frame(stock_code="600519.SH", start_date="2026-01-02"),
        )
        beta = self._upload_csv(
            second_user_token,
            "asset_beta",
            build_trading_frame(stock_code="000001.SZ", start_date="2026-02-10"),
        )
        gamma = self._upload_csv(
            self.user_token,
            "asset_gamma",
            build_trading_frame(stock_code="300750.SZ", start_date="2026-03-15"),
        )
        deleted_run = self._upload_csv(
            self.user_token,
            "asset_deleted",
            build_trading_frame(stock_code="688001.SH", start_date="2026-04-01"),
        )
        failed_run = self._upload_csv(
            self.user_token,
            "asset_failed",
            build_trading_frame(stock_code="601318.SH", start_date="2026-04-11"),
        )

        self._rewrite_run(
            int(alpha["id"]),
            record_count=8_000,
            started_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc),
        )
        self._rewrite_run(
            int(beta["id"]),
            record_count=25_000,
            started_at=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 2, 20, 10, 30, tzinfo=timezone.utc),
        )
        self._rewrite_run(
            int(gamma["id"]),
            record_count=220_000,
            started_at=datetime(2026, 3, 30, 11, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 3, 30, 11, 30, tzinfo=timezone.utc),
        )
        self._rewrite_run(
            int(deleted_run["id"]),
            record_count=50_000,
            started_at=datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 4, 2, 8, 30, tzinfo=timezone.utc),
            deleted_at=utc_now(),
        )
        self._rewrite_run(
            int(failed_run["id"]),
            record_count=120_000,
            started_at=datetime(2026, 4, 12, 8, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 4, 12, 8, 30, tzinfo=timezone.utc),
            status="failed",
        )

        response = self.client.get("/api/admin/assets/overview", headers=self._auth_headers(self.admin_token))
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()

        self.assertEqual(body["summary"]["owner_count"], 2)
        self.assertEqual(body["summary"]["unique_stock_count"], 3)
        self.assertEqual(body["summary"]["largest_dataset_records"], 220000)
        self.assertEqual(body["summary"]["median_dataset_records"], 25000.0)
        self.assertEqual(body["summary"]["first_trade_date"], "2026-01-02")
        self.assertEqual(body["summary"]["last_trade_date"], "2026-03-16")
        self.assertEqual(body["summary"]["latest_imported_at"], "2026-03-30T11:30:00Z")

        self.assertEqual(
            body["growth"],
            [
                {"month": "2026-01", "cumulative_datasets": 1, "cumulative_records": 8000},
                {"month": "2026-02", "cumulative_datasets": 2, "cumulative_records": 33000},
                {"month": "2026-03", "cumulative_datasets": 3, "cumulative_records": 253000},
            ],
        )
        self.assertEqual(
            body["growth_daily"],
            [
                {"day": "2026-01-05", "cumulative_datasets": 1, "cumulative_records": 8000},
                {"day": "2026-02-20", "cumulative_datasets": 2, "cumulative_records": 33000},
                {"day": "2026-03-30", "cumulative_datasets": 3, "cumulative_records": 253000},
            ],
        )
        self.assertEqual(
            body["size_buckets"],
            [
                {"bucket_label": "< 1万", "dataset_count": 1, "record_count": 8000},
                {"bucket_label": "1万 - 5万", "dataset_count": 1, "record_count": 25000},
                {"bucket_label": "20万+", "dataset_count": 1, "record_count": 220000},
            ],
        )

        owner_rows = body["owner_rows"]
        self.assertEqual(len(owner_rows), 2)
        self.assertEqual(owner_rows[0]["owner_username"], "dashboard_user")
        self.assertEqual(owner_rows[0]["dataset_count"], 2)
        self.assertEqual(owner_rows[0]["record_count"], 228000)
        self.assertAlmostEqual(owner_rows[0]["record_share_ratio"], 228000 / 253000, places=6)
        self.assertEqual(owner_rows[0]["avg_records_per_dataset"], 114000.0)
        self.assertEqual(owner_rows[0]["latest_completed_at"], "2026-03-30T11:30:00Z")
        self.assertEqual(owner_rows[1]["owner_username"], "asset_user_b")
        self.assertEqual(owner_rows[1]["record_count"], 25000)

        top_datasets = body["top_datasets"]
        self.assertEqual([item["dataset_name"] for item in top_datasets], ["asset_gamma", "asset_beta", "asset_alpha"])
        self.assertEqual([item["record_count"] for item in top_datasets], [220000, 25000, 8000])

    def test_non_admin_cannot_access_admin_dashboard_routes(self) -> None:
        for endpoint in (
            "/api/admin/overview",
            "/api/admin/audit-logs",
            "/api/admin/audit-logs/stats",
            "/api/admin/runs/monitor",
            "/api/admin/assets/overview",
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

    def test_audit_log_filters_support_partial_actor_username(self) -> None:
        register_response = self.client.post(
            "/api/auth/register",
            json={"username": "gogo11", "password": "password123"},
        )
        self.assertEqual(register_response.status_code, 200, register_response.text)

        logs_response = self.client.get(
            "/api/admin/audit-logs",
            params={"actor_username": "11", "page": 1, "page_size": 20},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(logs_response.status_code, 200, logs_response.text)
        logs_body = logs_response.json()
        self.assertGreaterEqual(logs_body["total"], 2)
        self.assertTrue(all(item["actor_username_snapshot"] == "gogo11" for item in logs_body["rows"]))

        stats_response = self.client.get(
            "/api/admin/audit-logs/stats",
            params={"actor_username": "gogo"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(stats_response.status_code, 200, stats_response.text)
        stats_body = stats_response.json()
        self.assertGreaterEqual(stats_body["total_events"], 2)
        self.assertEqual(stats_body["unique_actor_count"], 1)

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

    def _rewrite_run(
        self,
        run_id: int,
        *,
        record_count: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        deleted_at: datetime | None = None,
        status: str | None = None,
    ) -> None:
        session = get_session_factory()()
        try:
            run = session.get(ImportRun, run_id)
            self.assertIsNotNone(run)
            if run is None:
                return
            if record_count is not None:
                run.record_count = record_count
            if started_at is not None:
                run.started_at = started_at
            if completed_at is not None:
                run.completed_at = completed_at
            if deleted_at is not None:
                run.deleted_at = deleted_at
            if status is not None:
                run.status = status
            session.add(run)
            session.commit()
        finally:
            session.close()

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

if __name__ == "__main__":
    unittest.main()
