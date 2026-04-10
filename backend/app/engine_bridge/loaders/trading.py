from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import math
from typing import Sequence

import pandas as pd


NUMERIC_SCALE = Decimal("10000")
NUMERIC_QUANTUM = Decimal("0.0001")
SIGNAL_SCALE = Decimal("1000000")


@dataclass(frozen=True, slots=True)
class TradingAmountSeries:
    import_run_id: int
    instrument_code: str
    trade_dates: list[date]
    amounts_scaled: list[int]


@dataclass(frozen=True, slots=True)
class TradingVolumeSeries:
    import_run_id: int
    instrument_code: str
    trade_dates: list[date]
    volumes_scaled: list[int]


@dataclass(frozen=True, slots=True)
class TradingJointAnomalyEvent:
    import_run_id: int
    instrument_code: str
    instrument_name: str | None
    trade_date: date
    daily_return: float
    return_z20: float
    volume_ratio20: float
    return_z20_scaled: int
    volume_ratio20_scaled: int


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
    instrument_code: str,
    rows: Sequence[tuple[date, Decimal]],
) -> TradingAmountSeries:
    trade_dates = [trade_date for trade_date, _ in rows]
    amounts_scaled = [scale_amount(amount) for _, amount in rows]
    return TradingAmountSeries(
        import_run_id=import_run_id,
        instrument_code=instrument_code,
        trade_dates=trade_dates,
        amounts_scaled=amounts_scaled,
    )


def build_trading_volume_series(
    *,
    import_run_id: int,
    instrument_code: str,
    rows: Sequence[tuple[date, Decimal]],
) -> TradingVolumeSeries:
    trade_dates = [trade_date for trade_date, _ in rows]
    volumes_scaled = [scale_volume(volume) for _, volume in rows]
    return TradingVolumeSeries(
        import_run_id=import_run_id,
        instrument_code=instrument_code,
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
                "instrument_code": instrument_code,
                "instrument_name": instrument_name,
                "trade_date": pd.Timestamp(trade_date),
                "close": float(close_value),
                "volume": float(volume_value),
            }
            for instrument_code, instrument_name, trade_date, close_value, volume_value in rows
        ]
    )
    frame = frame.sort_values(["instrument_code", "trade_date"]).reset_index(drop=True)

    event_frames: list[pd.DataFrame] = []
    for instrument_code, group in frame.groupby("instrument_code", sort=True):
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

        valid_rows["instrument_code"] = instrument_code
        event_frames.append(valid_rows)

    if not event_frames:
        return []

    combined = (
        pd.concat(event_frames, ignore_index=True)
        .sort_values(["trade_date", "instrument_code"])
        .reset_index(drop=True)
    )

    return [
        TradingJointAnomalyEvent(
            import_run_id=import_run_id,
            instrument_code=str(row.instrument_code),
            instrument_name=str(row.instrument_name) if pd.notna(row.instrument_name) and row.instrument_name else None,
            trade_date=row.trade_date.date(),
            daily_return=float(row.daily_return),
            return_z20=float(row.return_z20),
            volume_ratio20=float(row.volume_ratio20),
            return_z20_scaled=scale_signal_metric(float(row.return_z20)),
            volume_ratio20_scaled=scale_signal_metric(float(row.volume_ratio20)),
        )
        for row in combined.itertuples(index=False)
    ]
