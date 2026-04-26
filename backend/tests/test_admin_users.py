from __future__ import annotations

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
from app.services.auth import AuthService
from postgres_integration import PostgresIntegrationTestCase


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


class AdminUsersTests(PostgresIntegrationTestCase):
    jwt_secret = "admin-users-secret"

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
        self.user_token = self._register_and_login("plain_user", "password123")
        self.data_user_token = self._register_and_login("data_user", "password123")
        self._upload_csv(self.data_user_token, "user_data_case", build_trading_frame())

    def tearDown(self) -> None:
        self.client.close()
        super().tearDown()

    def test_admin_can_manage_regular_users(self) -> None:
        list_response = self.client.get("/api/admin/users", headers=self._auth_headers(self.admin_token))
        self.assertEqual(list_response.status_code, 200, list_response.text)
        usernames = {row["username"] for row in list_response.json()}
        self.assertIn("admin", usernames)
        self.assertIn("plain_user", usernames)
        self.assertIn("data_user", usernames)

        plain_user = next(row for row in list_response.json() if row["username"] == "plain_user")
        data_user = next(row for row in list_response.json() if row["username"] == "data_user")
        self.assertFalse(plain_user["has_business_data"])
        self.assertTrue(data_user["has_business_data"])

        update_response = self.client.patch(
            f"/api/admin/users/{plain_user['id']}",
            json={"username": "plain_user_renamed", "password": "newpassword123", "is_active": True},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        self.assertEqual(update_response.json()["username"], "plain_user_renamed")

        disable_response = self.client.post(
            f"/api/admin/users/{plain_user['id']}/disable",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(disable_response.status_code, 200, disable_response.text)
        self.assertFalse(disable_response.json()["is_active"])

        disabled_login = self.client.post(
            "/api/auth/login",
            json={"username": "plain_user_renamed", "password": "newpassword123"},
        )
        self.assertEqual(disabled_login.status_code, 401)

        enable_response = self.client.post(
            f"/api/admin/users/{plain_user['id']}/enable",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(enable_response.status_code, 200, enable_response.text)
        self.assertTrue(enable_response.json()["is_active"])

        enabled_login = self.client.post(
            "/api/auth/login",
            json={"username": "plain_user_renamed", "password": "newpassword123"},
        )
        self.assertEqual(enabled_login.status_code, 200)

        blocked_delete = self.client.delete(
            f"/api/admin/users/{data_user['id']}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(blocked_delete.status_code, 409, blocked_delete.text)

        delete_response = self.client.delete(
            f"/api/admin/users/{plain_user['id']}",
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(delete_response.status_code, 200, delete_response.text)
        self.assertEqual(delete_response.json()["status"], "deleted")

    def test_admin_can_filter_users_by_partial_username_keyword(self) -> None:
        self._register_and_login("gogo11", "password123")
        filtered_response = self.client.get(
            "/api/admin/users",
            params={"query": "11"},
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(filtered_response.status_code, 200, filtered_response.text)
        body = filtered_response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["username"], "gogo11")

    def test_non_admin_cannot_access_admin_user_routes(self) -> None:
        response = self.client.get("/api/admin/users", headers=self._auth_headers(self.user_token))
        self.assertEqual(response.status_code, 403, response.text)

    def _register_and_login(self, username: str, password: str) -> str:
        self.client.post("/api/auth/register", json={"username": username, "password": password})
        return self._login(username, password)

    def _login(self, username: str, password: str) -> str:
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def _upload_csv(self, token: str, dataset_name: str, frame: pd.DataFrame) -> None:
        response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": dataset_name},
            files={"file": ("trading.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv")},
            headers=self._auth_headers(token),
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

if __name__ == "__main__":
    unittest.main()
