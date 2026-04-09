from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date

from sqlalchemy.orm import Session

from app.engine_bridge.adapters.stocks import query_range_max
from app.engine_bridge.loaders.stocks import build_stock_amount_series, unscale_amount
from app.repositories.stocks import StockRepository
from app.schemas.algo import StockRangeMaxAmountRead, StockRangeMaxMatchRead


class StockAlgoQueryValidationError(ValueError):
    """Raised when algo query parameters are invalid."""


class StockAlgoQueryNotFoundError(LookupError):
    """Raised when no stock series data exists for the requested range."""


class StockAlgoService:
    def query_range_max_amount(
        self,
        session: Session,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
        adjust: str = "qfq",
    ) -> StockRangeMaxAmountRead:
        if start_date > end_date:
            raise StockAlgoQueryValidationError("start_date must be less than or equal to end_date")

        rows = StockRepository.list_amount_series(session, symbol=symbol, adjust=adjust)
        if not rows:
            raise StockAlgoQueryNotFoundError(f"No stock amount series found for symbol={symbol} adjust={adjust}")

        series = build_stock_amount_series(symbol=symbol, adjust=adjust, rows=rows)
        left = bisect_left(series.trade_dates, start_date)
        right_exclusive = bisect_right(series.trade_dates, end_date)
        if left >= right_exclusive:
            raise StockAlgoQueryNotFoundError("No stock amount data found in the requested date range")

        result = query_range_max(series.amounts_scaled, left, right_exclusive - 1)
        if not result.matched_indices:
            raise StockAlgoQueryNotFoundError("No stock amount maxima found in the requested date range")

        matches = [
            StockRangeMaxMatchRead(trade_date=series.trade_dates[index], series_index=index)
            for index in result.matched_indices
        ]
        return StockRangeMaxAmountRead(
            symbol=symbol,
            adjust=adjust,
            start_date=start_date,
            end_date=end_date,
            max_amount=unscale_amount(result.max_value_scaled),
            matches=matches,
        )
