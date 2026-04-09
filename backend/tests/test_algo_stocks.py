from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import unittest

from fastapi import HTTPException
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "algo_stocks"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.routes.algo import stocks as algo_stock_routes
from app.api.routes import imports as import_routes
from app.core.database import create_all_tables, get_session_factory, reset_database_state
from app.engine_bridge.adapters.stocks import load_algo_engine_module
from app.schemas.api import ImportRequest


class AlgoStockRouteTests(unittest.TestCase):
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
        }
        os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{self.db_path.resolve().as_posix()}"
        os.environ["APP_ENV"] = "test"
        reset_database_state()
        create_all_tables()
        self.session = get_session_factory()()

    def tearDown(self) -> None:
        self.session.close()
        reset_database_state()
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_range_max_amount_returns_all_duplicate_max_dates(self) -> None:
        manifest = self._create_stock_manifest()
        import_routes.import_stock_manifest(ImportRequest(manifest_path=str(manifest)), session=self.session)

        response = algo_stock_routes.get_range_max_amount(
            symbol="000001",
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 5),
            adjust="qfq",
            session=self.session,
        )

        self.assertEqual(response.symbol, "000001")
        self.assertEqual(response.adjust, "qfq")
        self.assertEqual(str(response.max_amount), "1500000.0000")
        self.assertEqual([item.trade_date.isoformat() for item in response.matches], ["2024-01-03", "2024-01-04"])
        self.assertEqual([item.series_index for item in response.matches], [1, 2])

    def test_range_max_amount_rejects_invalid_date_range(self) -> None:
        manifest = self._create_stock_manifest()
        import_routes.import_stock_manifest(ImportRequest(manifest_path=str(manifest)), session=self.session)

        with self.assertRaises(HTTPException) as context:
            algo_stock_routes.get_range_max_amount(
                symbol="000001",
                start_date=date(2024, 1, 5),
                end_date=date(2024, 1, 2),
                adjust="qfq",
                session=self.session,
            )

        self.assertEqual(context.exception.status_code, 400)

    def test_range_max_amount_returns_404_when_interval_has_no_data(self) -> None:
        manifest = self._create_stock_manifest()
        import_routes.import_stock_manifest(ImportRequest(manifest_path=str(manifest)), session=self.session)

        with self.assertRaises(HTTPException) as context:
            algo_stock_routes.get_range_max_amount(
                symbol="000001",
                start_date=date(2023, 1, 1),
                end_date=date(2023, 1, 31),
                adjust="qfq",
                session=self.session,
            )

        self.assertEqual(context.exception.status_code, 404)

    def _create_stock_manifest(self) -> Path:
        frame = pd.DataFrame(
            [
                {
                    "symbol": "000001",
                    "trade_date": "2024-01-02",
                    "open": 10.0,
                    "close": 10.5,
                    "high": 10.7,
                    "low": 9.9,
                    "volume": 100000,
                    "amount": 1000000,
                    "amplitude": 2.3,
                    "pct_change": 1.1,
                    "change": 0.1,
                    "turnover": 3.2,
                    "adjust": "qfq",
                    "source_type": "api",
                    "股票代码": "000001",
                },
                {
                    "symbol": "000001",
                    "trade_date": "2024-01-03",
                    "open": 10.5,
                    "close": 10.8,
                    "high": 11.0,
                    "low": 10.2,
                    "volume": 120000,
                    "amount": 1500000,
                    "amplitude": 2.1,
                    "pct_change": 2.5,
                    "change": 0.3,
                    "turnover": 3.6,
                    "adjust": "qfq",
                    "source_type": "api",
                    "股票代码": "000001",
                },
                {
                    "symbol": "000001",
                    "trade_date": "2024-01-04",
                    "open": 10.8,
                    "close": 10.7,
                    "high": 11.2,
                    "low": 10.5,
                    "volume": 130000,
                    "amount": 1500000,
                    "amplitude": 1.9,
                    "pct_change": -0.9,
                    "change": -0.1,
                    "turnover": 3.7,
                    "adjust": "qfq",
                    "source_type": "api",
                    "股票代码": "000001",
                },
                {
                    "symbol": "000001",
                    "trade_date": "2024-01-05",
                    "open": 10.7,
                    "close": 10.4,
                    "high": 10.9,
                    "low": 10.3,
                    "volume": 110000,
                    "amount": 800000,
                    "amplitude": 1.5,
                    "pct_change": -2.8,
                    "change": -0.3,
                    "turnover": 3.1,
                    "adjust": "qfq",
                    "source_type": "api",
                    "股票代码": "000001",
                },
            ]
        )
        csv_path = self.temp_path / "stock.csv"
        frame.to_csv(csv_path, index=False, encoding="utf-8-sig")

        manifest_path = self.temp_path / "stock_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "dataset_name": "unit_stock_dataset",
                    "source_type": "api",
                    "source_name": "unit.akshare",
                    "source_uri": "https://example.com/stock",
                    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "record_count": len(frame),
                    "columns": list(frame.columns),
                    "artifacts": [
                        {
                            "name": "000001",
                            "path": str(csv_path),
                            "rows": len(frame),
                            "columns": list(frame.columns),
                        }
                    ],
                    "metadata": {"symbols": ["000001"]},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return manifest_path


if __name__ == "__main__":
    unittest.main()
