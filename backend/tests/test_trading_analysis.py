from __future__ import annotations

from io import BytesIO
import math
import os
from pathlib import Path
import sys
import time
import unittest

from fastapi.testclient import TestClient
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "test_artifacts" / "trading_analysis"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import create_all_tables, get_session_factory, reset_database_state
from app.services.auth import AuthService


def _build_rows(
    code: str,
    name: str,
    dates: list[pd.Timestamp],
    closes: list[float],
    *,
    volume_base: float,
    skip_indices: set[int] | None = None,
    spike_index: int | None = None,
    amplitude_index: int | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    skip_indices = skip_indices or set()
    for index, (trade_day, close_value) in enumerate(zip(dates, closes, strict=True)):
        if index in skip_indices:
            continue

        previous_close = closes[index - 1] if index > 0 else close_value * 0.995
        open_value = previous_close
        high_value = max(open_value, close_value) * 1.01
        low_value = min(open_value, close_value) * 0.99
        volume_value = volume_base + index * 12

        if spike_index is not None and index == spike_index:
            volume_value *= 4.2
        if amplitude_index is not None and index == amplitude_index:
            high_value = max(open_value, close_value) * 1.12
            low_value = min(open_value, close_value) * 0.88

        rows.append(
            {
                "instrument_code": code,
                "instrument_name": name,
                "trade_date": trade_day.strftime("%Y-%m-%d"),
                "open": round(open_value, 4),
                "high": round(high_value, 4),
                "low": round(low_value, 4),
                "close": round(close_value, 4),
                "volume": round(volume_value, 4),
                "amount": round(close_value * volume_value, 4),
            }
        )
    return rows


def build_primary_frame() -> pd.DataFrame:
    dates = list(pd.date_range("2026-01-01", periods=25, freq="D"))
    alpha_close = [
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
        106.0,
        107.0,
        108.0,
        109.0,
        110.0,
        111.0,
        90.0,
        92.0,
        95.0,
        98.0,
        100.0,
        102.0,
        104.0,
        106.0,
        108.0,
        110.0,
        112.0,
        114.0,
        116.0,
    ]
    beta_close = [
        80.0,
        80.3,
        80.5,
        80.8,
        81.0,
        81.2,
        81.4,
        81.6,
        81.8,
        82.0,
        82.1,
        82.3,
        82.5,
        82.8,
        83.0,
        83.2,
        83.4,
        83.7,
        83.9,
        84.1,
        84.3,
        84.6,
        84.8,
        85.0,
        85.2,
    ]
    gamma_close = [
        60.0,
        59.4,
        58.8,
        58.0,
        57.5,
        57.0,
        56.4,
        56.0,
        56.5,
        57.0,
        57.6,
        58.1,
        58.7,
        59.2,
        59.7,
        60.1,
        60.5,
        60.8,
        61.0,
        61.4,
        61.8,
        62.0,
        62.4,
        62.6,
        62.8,
    ]

    rows = []
    rows.extend(_build_rows("ALPHA", "Alpha Asset", dates, alpha_close, volume_base=1000, spike_index=20, amplitude_index=20))
    rows.extend(_build_rows("BETA", "Beta Asset", dates, beta_close, volume_base=900, skip_indices={7}))
    rows.extend(_build_rows("GAMMA", "Gamma Asset", dates, gamma_close, volume_base=700))
    frame = pd.DataFrame(rows)
    return frame.sort_values(["instrument_code", "trade_date"]).reset_index(drop=True)


def build_compare_frame() -> pd.DataFrame:
    dates = list(pd.date_range("2026-02-01", periods=12, freq="D"))
    alpha_close = [116.0, 117.0, 118.0, 119.0, 120.0, 121.0, 122.0, 123.0, 124.0, 125.0, 126.0, 127.0]
    gamma_close = [62.8, 62.9, 63.0, 63.1, 63.2, 63.4, 63.5, 63.7, 63.9, 64.0, 64.1, 64.3]
    delta_close = [45.0, 45.1, 45.3, 45.5, 45.6, 45.8, 46.0, 46.2, 46.4, 46.6, 46.8, 47.0]
    rows = []
    rows.extend(_build_rows("ALPHA", "Alpha Asset", dates, alpha_close, volume_base=1300))
    rows.extend(_build_rows("GAMMA", "Gamma Asset", dates, gamma_close, volume_base=750))
    rows.extend(_build_rows("DELTA", "Delta Asset", dates, delta_close, volume_base=680))
    frame = pd.DataFrame(rows)
    return frame.sort_values(["instrument_code", "trade_date"]).reset_index(drop=True)


def build_expected_alpha_metrics(frame: pd.DataFrame) -> dict[str, float]:
    alpha = frame.loc[frame["instrument_code"] == "ALPHA"].copy()
    alpha["close"] = pd.to_numeric(alpha["close"])
    alpha["high"] = pd.to_numeric(alpha["high"])
    alpha["low"] = pd.to_numeric(alpha["low"])
    alpha["open"] = pd.to_numeric(alpha["open"])
    alpha["volume"] = pd.to_numeric(alpha["volume"])
    alpha = alpha.sort_values("trade_date").reset_index(drop=True)

    close = alpha["close"]
    ma5 = close.rolling(window=5, min_periods=1).mean().iloc[-1]
    ema12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = close.ewm(span=26, adjust=False).mean().iloc[-1]

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = losses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi14 = (100 - (100 / (1 + rs))).iloc[-1]

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            alpha["high"] - alpha["low"],
            (alpha["high"] - previous_close).abs(),
            (alpha["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = true_range.rolling(window=14, min_periods=1).mean().iloc[-1]

    cumulative_return = (close.iloc[-1] / close.iloc[0]) - 1.0
    daily_return = close.pct_change().dropna()
    running_peak = close.cummax()
    drawdown = close / running_peak - 1.0
    max_drawdown = float(-drawdown.min())

    longest = 0
    current = 0
    for item in drawdown.fillna(0.0).tolist():
        if float(item) < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return {
        "ma5": float(ma5),
        "ema12": float(ema12),
        "ema26": float(ema26),
        "rsi14": float(rsi14),
        "atr14": float(atr14),
        "interval_return": float(cumulative_return),
        "volatility": float(daily_return.std(ddof=0)),
        "max_drawdown": float(max_drawdown),
        "max_drawdown_duration": float(longest),
    }


class TradingAnalysisRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_path = ARTIFACT_ROOT / f"case_{time.time_ns()}"
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_path / "analysis.sqlite3"
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
        os.environ["JWT_SECRET"] = "analysis-test-secret"
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

    def test_indicator_risk_and_anomaly_endpoints_return_expected_metrics(self) -> None:
        token = self._register_and_login("alice_user", "password123")
        primary_frame = build_primary_frame()
        run = self._upload_csv(
            token=token,
            dataset_name="analysis_primary",
            asset_class="stock",
            frame=primary_frame,
        )
        expected = build_expected_alpha_metrics(primary_frame)

        indicator_response = self.client.get(
            "/api/trading/analysis/indicators",
            params={"import_run_id": run["id"], "instrument_code": "ALPHA"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(indicator_response.status_code, 200, indicator_response.text)
        latest_point = indicator_response.json()["points"][-1]
        self.assertTrue(math.isclose(float(latest_point["ma5"]), expected["ma5"], abs_tol=1e-6))
        self.assertTrue(math.isclose(float(latest_point["ema12"]), expected["ema12"], abs_tol=1e-6))
        self.assertTrue(math.isclose(float(latest_point["ema26"]), expected["ema26"], abs_tol=1e-6))
        self.assertTrue(math.isclose(float(latest_point["rsi14"]), expected["rsi14"], abs_tol=1e-6))
        self.assertTrue(math.isclose(float(latest_point["atr14"]), expected["atr14"], abs_tol=1e-6))

        risk_response = self.client.get(
            "/api/trading/analysis/risk",
            params={"import_run_id": run["id"], "instrument_code": "ALPHA"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(risk_response.status_code, 200, risk_response.text)
        risk_body = risk_response.json()
        self.assertTrue(math.isclose(float(risk_body["interval_return"]), expected["interval_return"], abs_tol=1e-6))
        self.assertTrue(math.isclose(float(risk_body["volatility"]), expected["volatility"], abs_tol=1e-6))
        self.assertTrue(math.isclose(float(risk_body["max_drawdown"]), expected["max_drawdown"], abs_tol=1e-6))
        self.assertEqual(risk_body["max_drawdown_duration"], int(expected["max_drawdown_duration"]))

        anomaly_response = self.client.get(
            "/api/trading/analysis/anomalies",
            params={"import_run_id": run["id"], "instrument_code": "ALPHA"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(anomaly_response.status_code, 200, anomaly_response.text)
        anomaly_types = {item["anomaly_type"] for item in anomaly_response.json()["anomalies"]}
        self.assertIn("volume_spike", anomaly_types)
        self.assertIn("return_spike", anomaly_types)
        self.assertIn("amplitude_spike", anomaly_types)
        self.assertIn("breakout_new_low", anomaly_types)
        self.assertIn("breakout_new_high", anomaly_types)

    def test_quality_cross_section_correlation_and_compare_runs(self) -> None:
        token = self._register_and_login("alice_user", "password123")
        primary_frame = build_primary_frame()
        compare_frame = build_compare_frame()
        primary_run = self._upload_csv(
            token=token,
            dataset_name="analysis_primary",
            asset_class="stock",
            frame=primary_frame,
        )
        compare_run = self._upload_xlsx(
            token=token,
            dataset_name="analysis_compare",
            asset_class="commodity",
            frame=compare_frame,
        )

        quality_response = self.client.get(
            "/api/trading/analysis/quality",
            params={"import_run_id": primary_run["id"], "instrument_code": "BETA"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(quality_response.status_code, 200, quality_response.text)
        quality_body = quality_response.json()
        self.assertEqual(quality_body["missing_trade_date_count"], 1)
        self.assertEqual(quality_body["missing_trade_dates"], ["2026-01-08"])
        self.assertTrue(math.isclose(float(quality_body["coverage_ratio"]), 24 / 25, abs_tol=1e-6))

        cross_section_response = self.client.get(
            "/api/trading/analysis/cross-section",
            params={"import_run_id": primary_run["id"], "metric": "total_return", "top_n": 2},
            headers=self._auth_headers(token),
        )
        self.assertEqual(cross_section_response.status_code, 200, cross_section_response.text)
        cross_rows = cross_section_response.json()["rows"]
        self.assertEqual(len(cross_rows), 2)
        self.assertEqual(cross_rows[0]["instrument_code"], "ALPHA")

        correlation_response = self.client.get(
            "/api/trading/analysis/correlation",
            params={"import_run_id": primary_run["id"], "instrument_codes": "ALPHA,BETA,GAMMA"},
            headers=self._auth_headers(token),
        )
        self.assertEqual(correlation_response.status_code, 200, correlation_response.text)
        correlation_body = correlation_response.json()
        self.assertEqual(correlation_body["instrument_codes"], ["ALPHA", "BETA", "GAMMA"])
        self.assertEqual(len(correlation_body["matrix"]), 3)
        for index in range(3):
            self.assertTrue(math.isclose(float(correlation_body["matrix"][index][index]), 1.0, abs_tol=1e-6))

        compare_response = self.client.get(
            "/api/trading/analysis/compare-runs",
            params={"base_run_id": primary_run["id"], "target_run_id": compare_run["id"]},
            headers=self._auth_headers(token),
        )
        self.assertEqual(compare_response.status_code, 200, compare_response.text)
        compare_body = compare_response.json()
        self.assertEqual(compare_body["shared_instruments"], ["ALPHA", "GAMMA"])
        self.assertEqual(compare_body["added_instruments"], ["DELTA"])
        self.assertEqual(compare_body["removed_instruments"], ["BETA"])

    def test_analysis_endpoints_respect_visibility(self) -> None:
        alice_token = self._register_and_login("alice_user", "password123")
        bob_token = self._register_and_login("bob_user", "password123")
        admin_token = self._login("admin", "admin123456")

        run = self._upload_csv(
            token=alice_token,
            dataset_name="analysis_primary",
            asset_class="stock",
            frame=build_primary_frame(),
        )

        forbidden = self.client.get(
            "/api/trading/analysis/summary",
            params={"import_run_id": run["id"], "instrument_code": "ALPHA"},
            headers=self._auth_headers(bob_token),
        )
        self.assertEqual(forbidden.status_code, 404)

        allowed = self.client.get(
            "/api/trading/analysis/summary",
            params={"import_run_id": run["id"], "instrument_code": "ALPHA"},
            headers=self._auth_headers(admin_token),
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(allowed.json()["instrument_code"], "ALPHA")

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


if __name__ == "__main__":
    unittest.main()
