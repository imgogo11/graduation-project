from __future__ import annotations

from io import BytesIO
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
                "instrument_code": "600519.SH",
                "instrument_name": "Kweichow Moutai",
                "trade_date": "2026-01-02",
                "open": 1520.15,
                "high": 1535.80,
                "low": 1518.40,
                "close": 1534.30,
                "volume": 12800,
                "amount": 19639040,
            },
            {
                "instrument_code": "600519.SH",
                "instrument_name": "Kweichow Moutai",
                "trade_date": "2026-01-03",
                "open": 1534.30,
                "high": 1548.20,
                "low": 1529.50,
                "close": 1541.70,
                "volume": 13120,
                "amount": 20274816,
            },
            {
                "instrument_code": "000858.SZ",
                "instrument_name": "Wuliangye Yibin",
                "trade_date": "2026-01-02",
                "open": 168.32,
                "high": 170.15,
                "low": 167.50,
                "close": 169.88,
                "volume": 982,
                "amount": 166822.16,
            },
        ]
    )


def build_alias_frame(*, include_amount: bool = True) -> pd.DataFrame:
    frame = build_trading_frame().rename(
        columns={
            "instrument_code": "代码",
            "instrument_name": "名称",
            "trade_date": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
            "amount": "成交额",
        }
    )
    if not include_amount:
        frame = frame.drop(columns=["成交额"])
    return frame


def build_turnover_frame() -> pd.DataFrame:
    frame = build_trading_frame().copy()
    frame["turnover"] = [0.12, 0.13, 0.08]
    return frame


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
            dataset_name="alice_stock_csv",
            frame=build_trading_frame(),
        )
        alice_xlsx_run = self._upload_xlsx(
            token=alice_token,
            dataset_name="alice_stock_xlsx",
            frame=build_trading_frame(),
        )
        alice_third_run = self._upload_csv(
            token=alice_token,
            dataset_name="alice_stock_csv_2",
            frame=build_trading_frame(),
        )
        bob_run = self._upload_csv(
            token=bob_token,
            dataset_name="bob_stock_csv",
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
            params={"import_run_id": alice_csv_run["id"], "instrument_code": "600519.SH"},
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
            params={"import_run_id": alice_csv_run["id"], "instrument_code": "600519.SH"},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(deleted_records.status_code, 404)

    def test_upload_supports_alias_headers_and_optional_amount(self) -> None:
        token = self._register_and_login("alias_user", "password123")
        alias_run = self._upload_csv(
            token=token,
            dataset_name="alias_headers",
            frame=build_alias_frame(include_amount=False),
        )

        instruments = self.client.get(
            "/api/trading/instruments",
            params={"import_run_id": alias_run["id"]},
            headers=self._auth_headers(token),
        )
        self.assertEqual(instruments.status_code, 200, instruments.text)
        self.assertEqual(len(instruments.json()), 2)

        records = self.client.get(
            "/api/trading/records",
            params={"import_run_id": alias_run["id"], "instrument_code": "600519.SH"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(records.status_code, 200, records.text)
        body = records.json()
        self.assertEqual(body[0]["instrument_name"], "Kweichow Moutai")
        self.assertIsNone(body[0]["amount"])

    def test_upload_supports_optional_turnover_without_conflicting_with_amount(self) -> None:
        token = self._register_and_login("turnover_user", "password123")
        turnover_run = self._upload_csv(
            token=token,
            dataset_name="turnover_headers",
            frame=build_turnover_frame(),
        )

        records = self.client.get(
            "/api/trading/records",
            params={"import_run_id": turnover_run["id"], "instrument_code": "600519.SH"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(records.status_code, 200, records.text)
        body = records.json()
        self.assertEqual(len(body), 2)
        self.assertIsNotNone(body[0]["amount"])

    def test_dataset_name_conflicts_are_user_scoped_and_deleted_names_can_be_reused(self) -> None:
        alice_token = self._register_and_login("alice_name_user", "password123")
        bob_token = self._register_and_login("bob_name_user", "password123")
        dataset_name = "shared_stock_dataset"
        frame = build_trading_frame()

        first_run = self._upload_csv(
            token=alice_token,
            dataset_name=dataset_name,
            frame=frame,
        )

        duplicate_response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": dataset_name},
            files={"file": ("trading.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv")},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertIn("同名数据集", duplicate_response.json()["detail"])

        other_user_run = self._upload_csv(
            token=bob_token,
            dataset_name=dataset_name,
            frame=frame,
        )
        self.assertNotEqual(other_user_run["id"], first_run["id"])

        delete_response = self.client.delete(
            f"/api/imports/runs/{first_run['id']}",
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(delete_response.status_code, 200)

        reused_run = self._upload_csv(
            token=alice_token,
            dataset_name=dataset_name,
            frame=frame,
        )
        self.assertNotEqual(reused_run["id"], first_run["id"])

    def test_upload_rejects_missing_required_headers_and_duplicate_alias_matches(self) -> None:
        token = self._register_and_login("invalid_alias_user", "password123")

        missing_code_response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": "missing_code"},
            files={
                "file": (
                    "trading.csv",
                    build_alias_frame().drop(columns=["代码"]).to_csv(index=False).encode("utf-8"),
                    "text/csv",
                )
            },
            headers=self._auth_headers(token),
        )
        self.assertEqual(missing_code_response.status_code, 400)
        self.assertIn("导入失败，数据不符合格式", missing_code_response.json()["detail"])

        duplicate_alias_frame = build_trading_frame().rename(columns={"instrument_code": "code"})
        duplicate_alias_frame["symbol"] = duplicate_alias_frame["code"]
        duplicate_response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": "duplicate_alias"},
            files={
                "file": (
                    "trading.csv",
                    duplicate_alias_frame.to_csv(index=False).encode("utf-8"),
                    "text/csv",
                )
            },
            headers=self._auth_headers(token),
        )
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertIn("导入失败，数据不符合格式", duplicate_response.json()["detail"])

    def test_failed_uploads_are_hidden_allow_name_reuse_and_block_data_access(self) -> None:
        token = self._register_and_login("failed_upload_user", "password123")
        invalid_frame = build_trading_frame().drop(columns=["instrument_code"])

        failed_response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": "sample2"},
            files={
                "file": (
                    "invalid.csv",
                    invalid_frame.to_csv(index=False).encode("utf-8"),
                    "text/csv",
                )
            },
            headers=self._auth_headers(token),
        )
        self.assertEqual(failed_response.status_code, 400)
        self.assertIn("导入失败", failed_response.json()["detail"])

        runs_after_failure = self.client.get("/api/imports/runs", headers=self._auth_headers(token))
        self.assertEqual(runs_after_failure.status_code, 200)
        self.assertEqual(runs_after_failure.json(), [])

        failed_run_id = self._find_run_id(dataset_name="sample2", status="failed")

        blocked_instruments = self.client.get(
            "/api/trading/instruments",
            params={"import_run_id": failed_run_id},
            headers=self._auth_headers(token),
        )
        self.assertEqual(blocked_instruments.status_code, 404)

        successful_run = self._upload_csv(
            token=token,
            dataset_name="sample2",
            frame=build_trading_frame(),
        )
        self.assertEqual(successful_run["display_id"], 1)

        runs_after_success = self.client.get("/api/imports/runs", headers=self._auth_headers(token))
        self.assertEqual(runs_after_success.status_code, 200)
        success_rows = runs_after_success.json()
        self.assertEqual(len(success_rows), 1)
        self.assertEqual(success_rows[0]["id"], successful_run["id"])
        self.assertEqual(success_rows[0]["dataset_name"], "sample2")
        self.assertEqual(success_rows[0]["status"], "completed")

        stats_response = self.client.get("/api/imports/stats", headers=self._auth_headers(token))
        self.assertEqual(stats_response.status_code, 200)
        stats_body = stats_response.json()
        self.assertEqual(stats_body["total_runs"], 2)
        self.assertEqual(stats_body["completed_runs"], 1)
        self.assertEqual(stats_body["failed_runs"], 1)

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

    def _upload_xlsx(self, *, token: str, dataset_name: str, frame: pd.DataFrame) -> dict[str, object]:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False)
        response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": dataset_name},
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

    def _insert_legacy_run(self, *, owner_user_id: int, dataset_name: str) -> None:
        session = get_session_factory()()
        try:
            session.add(
                ImportRun(
                    owner_user_id=owner_user_id,
                    dataset_name=dataset_name,
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
