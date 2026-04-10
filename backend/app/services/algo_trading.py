from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date

from sqlalchemy.orm import Session

from app.engine_bridge.adapters.trading import query_range_max
from app.engine_bridge.loaders.trading import build_trading_amount_series, unscale_amount
from app.repositories.trading import TradingRepository
from app.schemas.trading import TradingRangeMaxAmountRead, TradingRangeMaxMatchRead


class TradingAlgoQueryValidationError(ValueError):
    """Raised when algo query parameters are invalid."""


class TradingAlgoQueryNotFoundError(LookupError):
    """Raised when no trading data exists for the requested range."""


class TradingAlgoService:
    def query_range_max_amount(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str,
        start_date: date,
        end_date: date,
    ) -> TradingRangeMaxAmountRead:
        if start_date > end_date:
            raise TradingAlgoQueryValidationError("start_date must be less than or equal to end_date")

        rows = TradingRepository.list_amount_series(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
        )
        if not rows:
            raise TradingAlgoQueryNotFoundError(
                f"No amount series found for import_run_id={import_run_id} instrument_code={instrument_code}"
            )

        series = build_trading_amount_series(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            rows=rows,
        )
        left = bisect_left(series.trade_dates, start_date)
        right_exclusive = bisect_right(series.trade_dates, end_date)
        if left >= right_exclusive:
            raise TradingAlgoQueryNotFoundError("No trading amount data found in the requested date range")

        result = query_range_max(series.amounts_scaled, left, right_exclusive - 1)
        if not result.matched_indices:
            raise TradingAlgoQueryNotFoundError("No trading amount maxima found in the requested date range")

        matches = [
            TradingRangeMaxMatchRead(trade_date=series.trade_dates[index], series_index=index)
            for index in result.matched_indices
        ]
        return TradingRangeMaxAmountRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
            max_amount=unscale_amount(result.max_value_scaled),
            matches=matches,
        )
