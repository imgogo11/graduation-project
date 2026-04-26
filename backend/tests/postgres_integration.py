from __future__ import annotations

import os
from pathlib import Path
import shutil
import time
import unittest

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.core.database import create_all_tables, get_engine, reset_database_state


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
TEST_UPLOAD_ROOT = REPO_ROOT / "data" / "uploads" / "_test_runtime"


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def truncate_public_business_tables() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    table_names = [
        name
        for name in inspector.get_table_names(schema="public")
        if name != "alembic_version"
    ]
    if not table_names:
        return

    joined = ", ".join(f'"public".{_quote_identifier(name)}' for name in sorted(table_names))
    statement = text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE")
    with engine.begin() as connection:
        connection.execute(statement)


def resolve_isolated_test_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    test_database_url = os.environ.get("TEST_DATABASE_URL")
    if not test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is required for PostgreSQL integration tests. "
            "Refusing to run destructive tests against the shared DATABASE_URL."
        )

    try:
        app_url = make_url(database_url) if database_url else None
        isolated_url = make_url(test_database_url)
    except Exception as exc:
        raise RuntimeError("Invalid DATABASE_URL or TEST_DATABASE_URL configuration for integration tests.") from exc

    isolated_database = str(isolated_url.database or "").strip()
    if not isolated_database:
        raise RuntimeError("TEST_DATABASE_URL must include a database name.")
    if not isolated_database.lower().endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must point to an isolated test database, for example graduation_project_test.")

    if (
        app_url is not None
        and app_url.drivername == isolated_url.drivername
        and app_url.host == isolated_url.host
        and app_url.port == isolated_url.port
        and app_url.database == isolated_url.database
    ):
        raise RuntimeError("TEST_DATABASE_URL must not point to the same database as DATABASE_URL.")

    return test_database_url


class PostgresIntegrationTestCase(unittest.TestCase):
    jwt_secret = "unit-test-secret"

    def setUp(self) -> None:
        self._previous_env = {
            "APP_ENV": os.environ.get("APP_ENV"),
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "JWT_SECRET": os.environ.get("JWT_SECRET"),
            "ADMIN_USERNAME": os.environ.get("ADMIN_USERNAME"),
            "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD"),
            "UPLOAD_ROOT": os.environ.get("UPLOAD_ROOT"),
        }

        case_id = f"{self.__class__.__name__}_{time.time_ns()}"
        self.upload_root = (TEST_UPLOAD_ROOT / case_id).resolve()
        self.upload_root.mkdir(parents=True, exist_ok=True)

        os.environ["APP_ENV"] = "test"
        os.environ["DATABASE_URL"] = resolve_isolated_test_database_url()
        os.environ["JWT_SECRET"] = self.jwt_secret
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "admin123456"
        os.environ["UPLOAD_ROOT"] = str(self.upload_root)

        reset_database_state()
        create_all_tables()
        truncate_public_business_tables()

    def tearDown(self) -> None:
        try:
            # Always clean business data at the end of each case so local
            # development databases are not polluted by integration test users.
            truncate_public_business_tables()
        finally:
            reset_database_state()
            shutil.rmtree(self.upload_root, ignore_errors=True)
            for key, value in self._previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
