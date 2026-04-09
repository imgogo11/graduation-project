from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class StockRangeMaxMatchRead(BaseModel):
    trade_date: date
    series_index: int


class StockRangeMaxAmountRead(BaseModel):
    symbol: str
    adjust: str
    start_date: date
    end_date: date
    max_amount: Decimal
    matches: list[StockRangeMaxMatchRead]
