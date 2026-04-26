from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import math
from typing import Sequence

import numpy as np
import pandas as pd


NUMERIC_SCALE = Decimal("10000")
NUMERIC_QUANTUM = Decimal("0.0001")
SIGNAL_SCALE = Decimal("1000000")


@dataclass(frozen=True, slots=True)
class TradingAmountSeries:
    import_run_id: int
    stock_code: str
    trade_dates: list[date]
    amounts_scaled: list[int]


@dataclass(frozen=True, slots=True)
class TradingVolumeSeries:
    import_run_id: int
    stock_code: str
    trade_dates: list[date]
    volumes_scaled: list[int]


@dataclass(frozen=True, slots=True)
class TradingJointAnomalyEvent:
    import_run_id: int
    stock_code: str
    stock_name: str | None
    trade_date: date
    daily_return: float
    return_z20: float
    volume_ratio20: float
    return_z20_scaled: int
    volume_ratio20_scaled: int


@dataclass(frozen=True, slots=True)
class TradingRiskRadarEvent:
    import_run_id: int
    stock_code: str
    stock_name: str | None
    trade_date: date
    daily_return: float
    return_shock: float
    vol_regime: float | None
    range_shock: float
    rvol20: float
    liquidity_shock: float
    drawdown_pressure: float
    score_return_shock: float | None
    score_vol_regime: float | None
    score_range_shock: float | None
    score_rvol20: float | None
    score_liquidity_shock: float | None
    score_drawdown_pressure: float | None
    return_shock_scaled: int
    rvol20_scaled: int
    liquidity_shock_scaled: int
    range_shock_scaled: int


def _rolling_percentile_rank(series: pd.Series, lookback: int) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    output = np.full(len(values), np.nan, dtype=float)
    for index, current in enumerate(values):
        if not np.isfinite(current):
            continue
        left = max(0, index - lookback + 1)
        window = values[left : index + 1]
        window = window[np.isfinite(window)]
        if len(window) < lookback:
            continue
        output[index] = float((window <= current).sum()) / float(len(window))
    return pd.Series(output, index=series.index, dtype="float64")


def scale_amount(amount: Decimal) -> int:
    return int((amount * NUMERIC_SCALE).to_integral_value())


def unscale_amount(amount_scaled: int) -> Decimal:
    return (Decimal(amount_scaled) / NUMERIC_SCALE).quantize(NUMERIC_QUANTUM)


def scale_volume(volume: Decimal) -> int:
    return int((volume * NUMERIC_SCALE).to_integral_value())


def unscale_volume(volume_scaled: int) -> Decimal:
    return (Decimal(volume_scaled) / NUMERIC_SCALE).quantize(NUMERIC_QUANTUM)


def scale_signal_metric(metric_value: float) -> int:
    return int((Decimal(str(metric_value)) * SIGNAL_SCALE).to_integral_value())


def build_trading_amount_series(
    *,
    import_run_id: int,
    stock_code: str,
    rows: Sequence[tuple[date, Decimal]],
) -> TradingAmountSeries:
    trade_dates = [trade_date for trade_date, _ in rows]
    amounts_scaled = [scale_amount(amount) for _, amount in rows]
    return TradingAmountSeries(
        import_run_id=import_run_id,
        stock_code=stock_code,
        trade_dates=trade_dates,
        amounts_scaled=amounts_scaled,
    )


def build_trading_volume_series(
    *,
    import_run_id: int,
    stock_code: str,
    rows: Sequence[tuple[date, Decimal]],
) -> TradingVolumeSeries:
    trade_dates = [trade_date for trade_date, _ in rows]
    volumes_scaled = [scale_volume(volume) for _, volume in rows]
    return TradingVolumeSeries(
        import_run_id=import_run_id,
        stock_code=stock_code,
        trade_dates=trade_dates,
        volumes_scaled=volumes_scaled,
    )


def build_trading_joint_anomaly_events(
    *,
    import_run_id: int,
    rows: Sequence[tuple[str, str | None, date, Decimal, Decimal]],
    lookback_window: int = 20,
) -> list[TradingJointAnomalyEvent]:
    if not rows:
        return []

    frame = pd.DataFrame(
        [
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "trade_date": pd.Timestamp(trade_date),
                "close": float(close_value),
                "volume": float(volume_value),
            }
            for stock_code, stock_name, trade_date, close_value, volume_value in rows
        ]
    )
    frame = frame.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)

    event_frames: list[pd.DataFrame] = []
    for stock_code, group in frame.groupby("stock_code", sort=True):
        enriched = group.sort_values("trade_date").reset_index(drop=True).copy()
        enriched["daily_return"] = enriched["close"].pct_change(fill_method=None)
        enriched["previous_return_std20"] = (
            enriched["daily_return"]
            .shift(1)
            .rolling(window=lookback_window, min_periods=lookback_window)
            .std(ddof=0)
        )
        enriched["previous_volume_mean20"] = (
            enriched["volume"]
            .shift(1)
            .rolling(window=lookback_window, min_periods=lookback_window)
            .mean()
        )
        enriched["return_z20"] = enriched["daily_return"].abs() / enriched["previous_return_std20"].replace(0.0, pd.NA)
        enriched["volume_ratio20"] = enriched["volume"] / enriched["previous_volume_mean20"].replace(0.0, pd.NA)

        valid_rows = enriched[
            enriched["daily_return"].notna()
            & enriched["previous_return_std20"].notna()
            & enriched["previous_volume_mean20"].notna()
            & (enriched["previous_return_std20"] > 0)
            & (enriched["previous_volume_mean20"] > 0)
            & enriched["return_z20"].notna()
            & enriched["volume_ratio20"].notna()
        ].copy()

        valid_rows = valid_rows[
            valid_rows["return_z20"].map(lambda value: math.isfinite(float(value)) and float(value) >= 0.0)
            & valid_rows["volume_ratio20"].map(lambda value: math.isfinite(float(value)) and float(value) >= 0.0)
        ]

        if valid_rows.empty:
            continue

        valid_rows["stock_code"] = stock_code
        event_frames.append(valid_rows)

    if not event_frames:
        return []

    combined = (
        pd.concat(event_frames, ignore_index=True)
        .sort_values(["trade_date", "stock_code"])
        .reset_index(drop=True)
    )

    return [
        TradingJointAnomalyEvent(
            import_run_id=import_run_id,
            stock_code=str(row.stock_code),
            stock_name=str(row.stock_name) if pd.notna(row.stock_name) and row.stock_name else None,
            trade_date=row.trade_date.date(),
            daily_return=float(row.daily_return),
            return_z20=float(row.return_z20),
            volume_ratio20=float(row.volume_ratio20),
            return_z20_scaled=scale_signal_metric(float(row.return_z20)),
            volume_ratio20_scaled=scale_signal_metric(float(row.volume_ratio20)),
        )
        for row in combined.itertuples(index=False)
    ]


def build_trading_risk_radar_events(
    *,
    import_run_id: int,
    rows: Sequence[tuple[str, str | None, date, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal | None, Decimal | None]],
    lookback_window: int = 20,
) -> list[TradingRiskRadarEvent]:
    if not rows:
        return []

    frame = pd.DataFrame(
        [
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "trade_date": pd.Timestamp(trade_date),
                "open": float(open_value),
                "high": float(high_value),
                "low": float(low_value),
                "close": float(close_value),
                "volume": float(volume_value),
                "amount": float(amount_value) if amount_value is not None else math.nan,
                "turnover": float(turnover_value) if turnover_value is not None else math.nan,
            }
            for (
                stock_code,
                stock_name,
                trade_date,
                open_value,
                high_value,
                low_value,
                close_value,
                volume_value,
                amount_value,
                turnover_value,
            ) in rows
        ]
    )
    frame = frame.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)

    event_frames: list[pd.DataFrame] = []
    for stock_code, group in frame.groupby("stock_code", sort=True):
        enriched = group.sort_values("trade_date").reset_index(drop=True).copy()
        enriched["daily_return"] = enriched["close"].pct_change(fill_method=None)
        enriched["log_return"] = np.log(enriched["close"] / enriched["close"].shift(1))

        enriched["previous_log_return_mean20"] = (
            enriched["log_return"]
            .shift(1)
            .rolling(window=lookback_window, min_periods=lookback_window)
            .mean()
        )
        enriched["previous_log_return_std20"] = (
            enriched["log_return"]
            .shift(1)
            .rolling(window=lookback_window, min_periods=lookback_window)
            .std(ddof=0)
        )
        enriched["return_shock"] = (enriched["log_return"] - enriched["previous_log_return_mean20"]).abs() / enriched[
            "previous_log_return_std20"
        ].replace(0.0, pd.NA)

        sigma20 = enriched["log_return"].rolling(window=20, min_periods=20).std(ddof=0)
        sigma120 = enriched["log_return"].rolling(window=120, min_periods=120).std(ddof=0)
        enriched["vol_regime"] = sigma20 / sigma120.replace(0.0, pd.NA)

        previous_close = enriched["close"].shift(1)
        true_range = pd.concat(
            [
                enriched["high"] - enriched["low"],
                (enriched["high"] - previous_close).abs(),
                (enriched["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr20 = true_range.rolling(window=20, min_periods=20).mean()
        enriched["range_shock"] = true_range / atr20.replace(0.0, pd.NA)

        volume_ma20 = enriched["volume"].rolling(window=20, min_periods=20).mean()
        enriched["rvol20"] = enriched["volume"] / volume_ma20.replace(0.0, pd.NA)

        # Keep liquidity_shock as a compatibility alias while the canonical radar axis is RVOL20.
        enriched["liquidity_shock"] = enriched["rvol20"]

        rolling_peak252 = enriched["close"].rolling(window=252, min_periods=1).max()
        enriched["drawdown_pressure"] = 1.0 - enriched["close"] / rolling_peak252.replace(0.0, pd.NA)

        enriched["score_return_shock"] = _rolling_percentile_rank(enriched["return_shock"], 252) * 100.0
        enriched["score_vol_regime"] = _rolling_percentile_rank(enriched["vol_regime"], 252) * 100.0
        enriched["score_range_shock"] = _rolling_percentile_rank(enriched["range_shock"], 252) * 100.0
        enriched["score_rvol20"] = _rolling_percentile_rank(enriched["rvol20"], 252) * 100.0
        enriched["score_liquidity_shock"] = _rolling_percentile_rank(enriched["liquidity_shock"], 252) * 100.0
        enriched["score_drawdown_pressure"] = _rolling_percentile_rank(enriched["drawdown_pressure"], 252) * 100.0

        valid_rows = enriched[
            enriched["daily_return"].notna()
            & enriched["return_shock"].notna()
            & enriched["rvol20"].notna()
            & enriched["range_shock"].notna()
            & enriched["drawdown_pressure"].notna()
        ].copy()

        valid_rows = valid_rows[
            valid_rows["return_shock"].map(lambda value: math.isfinite(float(value)) and float(value) >= 0.0)
            & valid_rows["rvol20"].map(lambda value: math.isfinite(float(value)) and float(value) >= 0.0)
            & valid_rows["range_shock"].map(lambda value: math.isfinite(float(value)) and float(value) >= 0.0)
            & valid_rows["drawdown_pressure"].map(lambda value: math.isfinite(float(value)) and float(value) >= 0.0)
        ]

        if valid_rows.empty:
            continue

        valid_rows["stock_code"] = stock_code
        event_frames.append(valid_rows)

    if not event_frames:
        return []

    combined = (
        pd.concat(event_frames, ignore_index=True)
        .sort_values(["trade_date", "stock_code"])
        .reset_index(drop=True)
    )

    return [
        TradingRiskRadarEvent(
            import_run_id=import_run_id,
            stock_code=str(row.stock_code),
            stock_name=str(row.stock_name) if pd.notna(row.stock_name) and row.stock_name else None,
            trade_date=row.trade_date.date(),
            daily_return=float(row.daily_return),
            return_shock=float(row.return_shock),
            vol_regime=float(row.vol_regime) if pd.notna(row.vol_regime) else None,
            range_shock=float(row.range_shock),
            rvol20=float(row.rvol20),
            liquidity_shock=float(row.liquidity_shock),
            drawdown_pressure=float(row.drawdown_pressure),
            score_return_shock=float(row.score_return_shock) if pd.notna(row.score_return_shock) else None,
            score_vol_regime=float(row.score_vol_regime) if pd.notna(row.score_vol_regime) else None,
            score_range_shock=float(row.score_range_shock) if pd.notna(row.score_range_shock) else None,
            score_rvol20=float(row.score_rvol20) if pd.notna(row.score_rvol20) else None,
            score_liquidity_shock=float(row.score_liquidity_shock) if pd.notna(row.score_liquidity_shock) else None,
            score_drawdown_pressure=float(row.score_drawdown_pressure) if pd.notna(row.score_drawdown_pressure) else None,
            return_shock_scaled=scale_signal_metric(float(row.return_shock)),
            rvol20_scaled=scale_signal_metric(float(row.rvol20)),
            liquidity_shock_scaled=scale_signal_metric(float(row.liquidity_shock)),
            range_shock_scaled=scale_signal_metric(float(row.range_shock)),
        )
        for row in combined.itertuples(index=False)
    ]

