from __future__ import annotations

from bisect import bisect_right
from datetime import date
import math

from app.services.algo_indexes import (
    RISK_RADAR_EVENT_WINDOW_SIZES,
    RISK_RADAR_LOCAL_PEAK_RADIUS,
    AlgoIndexNotReadyError,
    StockAlgoIndex,
    RiskRadarIndexCache,
    algo_index_manager,
)
from app.algo_bridge.loaders.trading import unscale_amount
from app.schemas.trading import (
    TradingRangeMaxMatchRead,
    TradingRiskRadarAmountPeakRead,
    TradingRiskRadarCalendarRead,
    TradingRiskRadarDistributionChangeRead,
    TradingRiskRadarEventContextRead,
    TradingRiskRadarEventListRead,
    TradingRiskRadarEventRead,
    TradingRiskRadarStockListRead,
    TradingRiskRadarOverviewRead,
    TradingRiskRadarWindowRead,
    TradingRiskRadarWindowGroupRead,
)

STANDARD_SCORE_REF = "https://en.wikipedia.org/wiki/Standard_score"
ATR_REF = "https://en.wikipedia.org/wiki/Average_true_range"
VOLATILITY_REF = "https://en.wikipedia.org/wiki/Volatility_%28finance%29"
RVOL_REF = "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol"
DRAWDOWN_REF = "https://en.wikipedia.org/wiki/Drawdown_%28economics%29"


class RiskRadarValidationError(ValueError):
    """Raised when risk radar query parameters are invalid."""


class RiskRadarNotFoundError(LookupError):
    """Raised when a requested risk radar entity cannot be found."""


class RiskRadarService:
    def get_overview(self, import_run_id: int) -> TradingRiskRadarOverviewRead:
        cache = algo_index_manager.get_cache(import_run_id)
        return cache.overview.model_copy(
            update=self._build_contract(
                required_fields=["open", "high", "low", "close", "volume"],
                data_frequency="daily",
                evidence_refs=[STANDARD_SCORE_REF, ATR_REF, VOLATILITY_REF, RVOL_REF, DRAWDOWN_REF],
            ),
        )

    def list_events(
        self,
        import_run_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        stock_code: str | None = None,
        severity: str | None = None,
        top_n: int | None = None,
    ) -> TradingRiskRadarEventListRead:
        if start_date and end_date and start_date > end_date:
            raise RiskRadarValidationError("start_date must be less than or equal to end_date")
        if top_n is not None and top_n <= 0:
            raise RiskRadarValidationError("top_n must be a positive integer")
        cache = algo_index_manager.get_cache(import_run_id)
        rows = self._filter_events(
            cache.events,
            start_date=start_date,
            end_date=end_date,
            stock_code=stock_code,
            severity=severity,
        )
        if top_n is not None:
            rows = rows[:top_n]
        return TradingRiskRadarEventListRead(
            import_run_id=import_run_id,
            rows=rows,
            **self._build_contract(
                required_fields=["open", "high", "low", "close", "volume"],
                data_frequency="daily",
                evidence_refs=[STANDARD_SCORE_REF, ATR_REF, VOLATILITY_REF, RVOL_REF, DRAWDOWN_REF],
            ),
        )

    def list_stocks(
        self,
        import_run_id: int,
        *,
        severity: str | None = None,
        top_n: int | None = None,
    ) -> TradingRiskRadarStockListRead:
        if top_n is not None and top_n <= 0:
            raise RiskRadarValidationError("top_n must be a positive integer")
        cache = algo_index_manager.get_cache(import_run_id)
        if severity is None:
            rows = cache.stock_profiles
        else:
            filtered_codes = {item.stock_code for item in cache.events if item.severity == severity}
            rows = [item for item in cache.stock_profiles if item.stock_code in filtered_codes]
        if top_n is not None:
            rows = rows[:top_n]
        return TradingRiskRadarStockListRead(
            import_run_id=import_run_id,
            rows=rows,
            **self._build_contract(
                required_fields=["open", "high", "low", "close", "volume"],
                data_frequency="daily",
                evidence_refs=[STANDARD_SCORE_REF, ATR_REF, VOLATILITY_REF, RVOL_REF, DRAWDOWN_REF],
            ),
        )

    def list_calendar(
        self,
        import_run_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingRiskRadarCalendarRead:
        if start_date and end_date and start_date > end_date:
            raise RiskRadarValidationError("start_date must be less than or equal to end_date")
        cache = algo_index_manager.get_cache(import_run_id)
        rows = cache.calendar_rows
        if start_date:
            rows = [item for item in rows if item.trade_date >= start_date]
        if end_date:
            rows = [item for item in rows if item.trade_date <= end_date]
        return TradingRiskRadarCalendarRead(
            import_run_id=import_run_id,
            rows=rows,
            **self._build_contract(
                required_fields=["open", "high", "low", "close", "volume"],
                data_frequency="daily",
                evidence_refs=[STANDARD_SCORE_REF, ATR_REF, VOLATILITY_REF, RVOL_REF, DRAWDOWN_REF],
            ),
        )

    def get_event_context(
        self,
        import_run_id: int,
        *,
        stock_code: str,
        trade_date: date,
    ) -> TradingRiskRadarEventContextRead:
        cache = algo_index_manager.get_cache(import_run_id)
        event = self._find_event(cache, stock_code=stock_code, trade_date=trade_date)
        stock_index = cache.stocks.get(stock_code)
        if stock_index is None:
            raise RiskRadarNotFoundError("Stock index not found for the requested event")
        event_index = stock_index.date_to_index.get(trade_date)
        if event_index is None:
            raise RiskRadarNotFoundError("Trade date not found for the requested stock")

        window_groups = [
            TradingRiskRadarWindowGroupRead(
                metric="volume",
                label="成交量",
                windows=[
                    self._build_window_read(
                        stock_index.volume_values,
                        stock_index.volume_tree,
                        event_index,
                        window_days,
                        scale_divisor=stock_index.volume_scale_divisor,
                    )
                    for window_days in RISK_RADAR_EVENT_WINDOW_SIZES
                ],
            ),
            TradingRiskRadarWindowGroupRead(
                metric="rvol20",
                label="RVOL20",
                windows=[
                    self._build_window_read(
                        stock_index.rvol20_values,
                        stock_index.rvol20_tree,
                        event_index,
                        window_days,
                        scale_divisor=stock_index.signal_scale_divisor,
                    )
                    for window_days in RISK_RADAR_EVENT_WINDOW_SIZES
                ],
            ),
            TradingRiskRadarWindowGroupRead(
                metric="range_shock",
                label="RangeShock",
                windows=[
                    self._build_window_read(
                        stock_index.range_shock_values,
                        stock_index.range_shock_tree,
                        event_index,
                        window_days,
                        scale_divisor=stock_index.signal_scale_divisor,
                    )
                    for window_days in RISK_RADAR_EVENT_WINDOW_SIZES
                ],
            ),
        ]
        distribution_changes = [
            self._build_distribution_change("volume", stock_index.volume_values, event_index, 20),
            self._build_distribution_change("rvol20", stock_index.rvol20_values, event_index, 20),
            self._build_distribution_change("range_shock", stock_index.range_shock_values, event_index, 20),
        ]
        local_amount_peak = self._build_local_amount_peak(stock_index, event_index)

        return TradingRiskRadarEventContextRead(
            import_run_id=import_run_id,
            event=event,
            window_groups=window_groups,
            distribution_changes=distribution_changes,
            local_amount_peak=local_amount_peak,
            **self._build_contract(
                required_fields=["open", "high", "low", "close", "volume", "amount"],
                missing_fields=[] if local_amount_peak is not None else ["amount"],
                data_frequency="daily",
                evidence_refs=[STANDARD_SCORE_REF, ATR_REF, VOLATILITY_REF, RVOL_REF, DRAWDOWN_REF],
            ),
        )

    def _filter_events(
        self,
        events: list[TradingRiskRadarEventRead],
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        stock_code: str | None = None,
        severity: str | None = None,
    ) -> list[TradingRiskRadarEventRead]:
        rows = events
        if start_date:
            rows = [item for item in rows if item.trade_date >= start_date]
        if end_date:
            rows = [item for item in rows if item.trade_date <= end_date]
        if stock_code:
            rows = [item for item in rows if item.stock_code == stock_code]
        if severity:
            rows = [item for item in rows if item.severity == severity]
        return rows

    def _find_event(self, cache: RiskRadarIndexCache, *, stock_code: str, trade_date: date) -> TradingRiskRadarEventRead:
        for event in cache.events:
            if event.stock_code == stock_code and event.trade_date == trade_date:
                return event
        raise RiskRadarNotFoundError("Risk radar event not found")

    def _build_window_read(
        self,
        values: list[float],
        tree: object,
        event_index: int,
        window_days: int,
        *,
        scale_divisor: float,
    ) -> TradingRiskRadarWindowRead:
        left = max(0, event_index - window_days + 1)
        right = event_index
        window_values = values[left : right + 1]
        current_value = float(values[event_index])
        sorted_values = sorted(window_values)
        exact_percentile = bisect_right(sorted_values, current_value) / float(len(sorted_values))
        p50 = self._query_percentile(tree, left, right, 0.50, scale_divisor=scale_divisor)
        p90 = self._query_percentile(tree, left, right, 0.90, scale_divisor=scale_divisor)
        p95 = self._query_percentile(tree, left, right, 0.95, scale_divisor=scale_divisor)
        top_1 = self._query_kth(tree, left, right, 1, scale_divisor=scale_divisor)
        top_3 = self._query_kth(tree, left, right, 3, scale_divisor=scale_divisor) if len(window_values) >= 3 else None
        return TradingRiskRadarWindowRead(
            window_days=len(window_values),
            current_value=round(current_value, 6),
            exact_percentile=round(exact_percentile, 6),
            p50=round(p50, 6),
            p90=round(p90, 6),
            p95=round(p95, 6),
            top_1=round(top_1, 6),
            top_3=round(top_3, 6) if top_3 is not None else None,
        )

    def _build_distribution_change(
        self,
        metric: str,
        values: list[float],
        event_index: int,
        window_days: int,
    ) -> TradingRiskRadarDistributionChangeRead:
        before_values = values[max(0, event_index - window_days) : event_index] or [values[event_index]]
        after_values = values[event_index : min(len(values), event_index + window_days)] or [values[event_index]]
        return TradingRiskRadarDistributionChangeRead(
            metric=metric,
            window_days=window_days,
            before_median=round(self._nearest_rank_percentile(before_values, 0.50), 6),
            before_p90=round(self._nearest_rank_percentile(before_values, 0.90), 6),
            before_p95=round(self._nearest_rank_percentile(before_values, 0.95), 6),
            after_median=round(self._nearest_rank_percentile(after_values, 0.50), 6),
            after_p90=round(self._nearest_rank_percentile(after_values, 0.90), 6),
            after_p95=round(self._nearest_rank_percentile(after_values, 0.95), 6),
        )

    def _build_local_amount_peak(
        self,
        stock_index: StockAlgoIndex,
        event_index: int,
    ) -> TradingRiskRadarAmountPeakRead | None:
        if stock_index.amount_tree is None:
            return None
        left = max(0, event_index - RISK_RADAR_LOCAL_PEAK_RADIUS)
        right = min(len(stock_index.trade_dates) - 1, event_index + RISK_RADAR_LOCAL_PEAK_RADIUS)
        result = stock_index.amount_tree.query_inclusive(left, right)
        return TradingRiskRadarAmountPeakRead(
            start_date=stock_index.trade_dates[left],
            end_date=stock_index.trade_dates[right],
            peak_amount=round(float(unscale_amount(result.max_value_scaled)), 4),
            peak_dates=[
                TradingRangeMaxMatchRead(trade_date=stock_index.trade_dates[index], series_index=index)
                for index in list(result.matched_indices)
            ],
        )

    def _query_percentile(self, tree: object, left: int, right: int, percentile: float, *, scale_divisor: float) -> float:
        interval_length = right - left + 1
        kth = max(1, interval_length - math.ceil(percentile * interval_length) + 1)
        return self._query_kth(tree, left, right, kth, scale_divisor=scale_divisor)

    def _query_kth(self, tree: object, left: int, right: int, kth: int, *, scale_divisor: float) -> float:
        result = tree.query_inclusive(left, right, kth)
        return float(result.kth_value_scaled) / scale_divisor

    def _nearest_rank_percentile(self, values: list[float], percentile: float) -> float:
        sorted_values = sorted(values)
        rank = max(1, min(len(sorted_values), math.ceil(percentile * len(sorted_values))))
        return float(sorted_values[rank - 1])

    def _build_contract(
        self,
        *,
        required_fields: list[str],
        data_frequency: str,
        evidence_refs: list[str],
        missing_fields: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "required_fields": required_fields,
            "missing_fields": missing_fields or [],
            "data_frequency": data_frequency,
            "evidence_refs": evidence_refs,
            "benchmark_code": None,
            "benchmark_source": None,
        }


risk_radar_service = RiskRadarService()


__all__ = [
    "AlgoIndexNotReadyError",
    "RiskRadarNotFoundError",
    "RiskRadarValidationError",
    "risk_radar_service",
]


