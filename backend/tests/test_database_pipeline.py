from __future__ import annotations

from datetime import timedelta
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
from app.models import ImportMappingTemplate, ImportPreviewSession, ImportRun, utc_now
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
            {
                "stock_code": "000858.SZ",
                "stock_name": "Wuliangye Yibin",
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


def build_legacy_header_frame(*, include_amount: bool = True) -> pd.DataFrame:
    frame = build_trading_frame().rename(
        columns={
            "stock_code": "instrument_code",
            "stock_name": "instrument_name",
            "trade_date": "date",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
            "volume": "trade_volume",
            "amount": "trade_amount",
        }
    )
    if not include_amount:
        frame = frame.drop(columns=["trade_amount"])
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
            "/api/trading/stocks",
            params={"import_run_id": alice_csv_run["id"]},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(instruments.status_code, 200)
        self.assertEqual(len(instruments.json()), 2)

        records = self.client.get(
            "/api/trading/records",
            params={"import_run_id": alice_csv_run["id"], "stock_code": "600519.SH"},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(records.status_code, 200)
        self.assertEqual(len(records.json()), 2)

        forbidden_to_bob = self.client.get(
            "/api/trading/stocks",
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
            params={"import_run_id": alice_csv_run["id"], "stock_code": "600519.SH"},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(deleted_records.status_code, 404)

    def test_upload_supports_optional_turnover_without_conflicting_with_amount(self) -> None:
        token = self._register_and_login("turnover_user", "password123")
        preview = self._preview_csv(
            token=token,
            dataset_name="turnover_headers_default_required_only",
            frame=build_turnover_frame(),
        )
        turnover_run = self._commit_preview(
            token=token,
            preview_id=str(preview["preview_id"]),
            mapping_overrides={},
        )
        session = get_session_factory()()
        try:
            template = session.scalar(select(ImportMappingTemplate).where(ImportMappingTemplate.owner_user_id.is_not(None)))
            self.assertIsNotNone(template)
            template_mapping = dict(template.mapping_json) if template is not None else {}
            self.assertNotIn("amount", template_mapping)
            self.assertNotIn("turnover", template_mapping)
        finally:
            session.close()

        records = self.client.get(
            "/api/trading/records",
            params={"import_run_id": turnover_run["id"], "stock_code": "600519.SH"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(records.status_code, 200, records.text)
        body = records.json()
        self.assertEqual(len(body), 2)
        self.assertIsNone(body[0]["amount"])

        preview_with_optional = self._preview_csv(
            token=token,
            dataset_name="turnover_headers_with_optional",
            frame=build_turnover_frame(),
        )
        run_with_optional = self._commit_preview(
            token=token,
            preview_id=str(preview_with_optional["preview_id"]),
            mapping_overrides={"amount": "amount"},
        )
        session = get_session_factory()()
        try:
            template = session.scalar(select(ImportMappingTemplate).where(ImportMappingTemplate.owner_user_id.is_not(None)))
            self.assertIsNotNone(template)
            template_mapping = dict(template.mapping_json) if template is not None else {}
            self.assertEqual(template_mapping.get("amount"), "amount")
            self.assertNotIn("turnover", template_mapping)
        finally:
            session.close()
        records_with_optional = self.client.get(
            "/api/trading/records",
            params={"import_run_id": run_with_optional["id"], "stock_code": "600519.SH"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(records_with_optional.status_code, 200, records_with_optional.text)
        body_with_optional = records_with_optional.json()
        self.assertEqual(len(body_with_optional), 2)
        self.assertIsNotNone(body_with_optional[0]["amount"])

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

    def test_preview_and_commit_support_alias_headers_and_manual_confirmation(self) -> None:
        token = self._register_and_login("preview_user", "password123")

        legacy_preview = self._preview_csv(
            token=token,
            dataset_name="legacy_headers",
            frame=build_legacy_header_frame(include_amount=False),
        )
        self.assertIn("preview_id", legacy_preview)
        self.assertIn("required_confirmation_needed", legacy_preview)
        legacy_mapping_overrides: dict[str, str] = {}
        for canonical in legacy_preview.get("required_issue_columns", []):
            selected = legacy_preview.get("suggested_mapping", {}).get(canonical)
            if selected:
                legacy_mapping_overrides[str(canonical)] = str(selected)
        legacy_commit = self._commit_preview(
            token=token,
            preview_id=str(legacy_preview["preview_id"]),
            mapping_overrides=legacy_mapping_overrides,
        )
        self.assertEqual(legacy_commit["dataset_name"], "legacy_headers")

        old_alias_frame = build_trading_frame().rename(columns={"stock_code": "code"})
        old_alias_frame["symbol"] = old_alias_frame["code"]
        old_alias_response = self.client.post(
            "/api/imports/trading",
            data={"dataset_name": "old_alias_columns"},
            files={"file": ("trading.csv", old_alias_frame.to_csv(index=False).encode("utf-8"), "text/csv")},
            headers=self._auth_headers(token),
        )
        self.assertEqual(old_alias_response.status_code, 400)
        self.assertIn("/api/imports/trading/preview", old_alias_response.json()["detail"])

        old_alias_preview = self._preview_csv(token=token, dataset_name="old_alias_columns", frame=old_alias_frame)
        self.assertFalse(old_alias_preview["can_auto_commit"])
        self.assertTrue(old_alias_preview["conflicts"])
        self.assertTrue(old_alias_preview["required_confirmation_needed"])
        self.assertIn("stock_code", old_alias_preview["required_issue_columns"])
        old_alias_mapping_overrides: dict[str, str] = {"stock_code": "code"}
        for canonical in old_alias_preview.get("required_issue_columns", []):
            if str(canonical) == "stock_code":
                continue
            selected = old_alias_preview.get("suggested_mapping", {}).get(canonical)
            if selected:
                old_alias_mapping_overrides[str(canonical)] = str(selected)
        old_alias_commit = self._commit_preview(
            token=token,
            preview_id=str(old_alias_preview["preview_id"]),
            mapping_overrides=old_alias_mapping_overrides,
        )
        self.assertEqual(old_alias_commit["dataset_name"], "old_alias_columns")

        missing_code_preview = self._preview_csv(
            token=token,
            dataset_name="missing_code",
            frame=build_trading_frame().drop(columns=["stock_code"]),
        )
        self.assertIn("stock_code", missing_code_preview["missing_required"])
        self.assertTrue(missing_code_preview["required_confirmation_needed"])
        self.assertIn("stock_code", missing_code_preview["required_issue_columns"])
        self.assertFalse(missing_code_preview["can_auto_commit"])

    def test_preview_commit_permissions_expiry_and_template_learning(self) -> None:
        alice_token = self._register_and_login("preview_alice", "password123")
        bob_token = self._register_and_login("preview_bob", "password123")

        preview = self._preview_csv(token=alice_token, dataset_name="preview_scope", frame=build_trading_frame())
        preview_id = str(preview["preview_id"])

        forbidden = self.client.post(
            "/api/imports/trading/commit",
            json={"preview_id": preview_id, "required_confirmation_ack": True, "mapping_overrides": {}},
            headers=self._auth_headers(bob_token),
        )
        self.assertEqual(forbidden.status_code, 404)

        session = get_session_factory()()
        try:
            row = session.get(ImportPreviewSession, preview_id)
            self.assertIsNotNone(row)
            row.expires_at = utc_now() - timedelta(hours=1)  # type: ignore[assignment]
            session.add(row)
            session.commit()
        finally:
            session.close()

        expired = self.client.post(
            "/api/imports/trading/commit",
            json={"preview_id": preview_id, "required_confirmation_ack": True, "mapping_overrides": {}},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(expired.status_code, 410)

        preview2 = self._preview_csv(token=alice_token, dataset_name="preview_scope_ok", frame=build_trading_frame())
        preview2_id = str(preview2["preview_id"])
        committed = self._commit_preview(token=alice_token, preview_id=preview2_id, mapping_overrides={})
        self.assertEqual(committed["dataset_name"], "preview_scope_ok")

        repeated = self.client.post(
            "/api/imports/trading/commit",
            json={"preview_id": preview2_id, "required_confirmation_ack": True, "mapping_overrides": {}},
            headers=self._auth_headers(alice_token),
        )
        self.assertEqual(repeated.status_code, 409)

        session = get_session_factory()()
        try:
            template = session.scalar(select(ImportMappingTemplate).where(ImportMappingTemplate.owner_user_id.is_not(None)))
            self.assertIsNotNone(template)
        finally:
            session.close()

    def test_failed_uploads_are_hidden_allow_name_reuse_and_block_data_access(self) -> None:
        token = self._register_and_login("failed_upload_user", "password123")
        invalid_frame = build_trading_frame().drop(columns=["stock_code"])

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
        self.assertIn("/api/imports/trading/preview", failed_response.json()["detail"])

        runs_after_failure = self.client.get("/api/imports/runs", headers=self._auth_headers(token))
        self.assertEqual(runs_after_failure.status_code, 200)
        self.assertEqual(runs_after_failure.json(), [])

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
        self.assertEqual(stats_body["total_runs"], 1)
        self.assertEqual(stats_body["completed_runs"], 1)
        self.assertEqual(stats_body["failed_runs"], 0)

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

    def _preview_csv(self, *, token: str, dataset_name: str, frame: pd.DataFrame) -> dict[str, object]:
        response = self.client.post(
            "/api/imports/trading/preview",
            data={"dataset_name": dataset_name},
            files={"file": ("trading.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv")},
            headers=self._auth_headers(token),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _commit_preview(
        self,
        *,
        token: str,
        preview_id: str,
        required_confirmation_ack: bool = True,
        mapping_overrides: dict[str, str | None],
    ) -> dict[str, object]:
        response = self.client.post(
            "/api/imports/trading/commit",
            json={
                "preview_id": preview_id,
                "required_confirmation_ack": required_confirmation_ack,
                "mapping_overrides": mapping_overrides,
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

