from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence


AMOUNT_SCALE = Decimal("10000")
AMOUNT_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class StockAmountSeries:
    symbol: str
    adjust: str
    trade_dates: list[date]
    amounts_scaled: list[int]


def scale_amount(amount: Decimal) -> int:
    return int((amount * AMOUNT_SCALE).to_integral_value())


def unscale_amount(amount_scaled: int) -> Decimal:
    return (Decimal(amount_scaled) / AMOUNT_SCALE).quantize(AMOUNT_QUANTUM)


def build_stock_amount_series(
    *,
    symbol: str,
    adjust: str,
    rows: Sequence[tuple[date, Decimal]],
) -> StockAmountSeries:
    trade_dates = [trade_date for trade_date, _ in rows]
    amounts_scaled = [scale_amount(amount) for _, amount in rows]
    return StockAmountSeries(
        symbol=symbol,
        adjust=adjust,
        trade_dates=trade_dates,
        amounts_scaled=amounts_scaled,
    )
