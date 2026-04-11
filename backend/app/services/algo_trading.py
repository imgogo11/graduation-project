from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date

from sqlalchemy.orm import Session

from app.engine_bridge.adapters.trading import (
    query_historical_dominance,
    query_range_kth,
    query_range_kth_tdigest,
    query_range_max,
)
from app.engine_bridge.loaders.trading import (
    build_trading_joint_anomaly_events,
    build_trading_amount_series,
    build_trading_volume_series,
    unscale_amount,
    unscale_volume,
)
from app.repositories.trading import TradingRepository
from app.schemas.trading import (
    TradingJointAnomalyRankingRead,
    TradingJointAnomalyRowRead,
    TradingRangeKthVolumeRead,
    TradingRangeMaxAmountRead,
    TradingRangeMaxMatchRead,
)


PERSISTENT_SEGMENT_TREE_METHOD = "persistent_segment_tree"
TDIGEST_METHOD = "t_digest"
SUPPORTED_RANGE_KTH_METHODS = frozenset({PERSISTENT_SEGMENT_TREE_METHOD, TDIGEST_METHOD})
JOINT_ANOMALY_LOOKBACK_WINDOW = 20
JOINT_ANOMALY_DEFAULT_TOP_N = 50
DATA_INSUFFICIENT_PREFIX = "数据不足分析"


class TradingAlgoQueryValidationError(ValueError):
    """Raised when algo query parameters are invalid."""


class TradingAlgoQueryNotFoundError(LookupError):
    """Raised when no trading data exists for the requested range."""


class TradingAlgoQueryDataUnavailableError(ValueError):
    """Raised when a query cannot run because the input dataset lacks the required data."""


def build_algo_data_unavailable_message(detail: str) -> str:
    return f"{DATA_INSUFFICIENT_PREFIX}：{detail}"


class TradingAlgoService:
    @staticmethod
    def _resolve_interval(
        trade_dates: list[date],
        *,
        start_date: date,
        end_date: date,
        not_found_message: str,
    ) -> tuple[int, int]:
        left = bisect_left(trade_dates, start_date)
        right_exclusive = bisect_right(trade_dates, end_date)
        if left >= right_exclusive:
            raise TradingAlgoQueryNotFoundError(not_found_message)
        return left, right_exclusive

    @staticmethod
    def _build_matches(trade_dates: list[date], matched_indices: list[int]) -> list[TradingRangeMaxMatchRead]:
        return [
            TradingRangeMaxMatchRead(trade_date=trade_dates[index], series_index=index)
            for index in matched_indices
        ]

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
            raise TradingAlgoQueryDataUnavailableError(
                build_algo_data_unavailable_message(f"{instrument_code} 缺少成交额列或成交额数据")
            )

        series = build_trading_amount_series(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            rows=rows,
        )
        left, right_exclusive = self._resolve_interval(
            series.trade_dates,
            start_date=start_date,
            end_date=end_date,
            not_found_message="No trading amount data found in the requested date range",
        )

        result = query_range_max(series.amounts_scaled, left, right_exclusive - 1)
        if not result.matched_indices:
            raise TradingAlgoQueryNotFoundError("No trading amount maxima found in the requested date range")

        return TradingRangeMaxAmountRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
            max_amount=unscale_amount(result.max_value_scaled),
            matches=self._build_matches(series.trade_dates, result.matched_indices),
        )

    def query_range_kth_volume(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str,
        start_date: date,
        end_date: date,
        k: int,
        method: str = PERSISTENT_SEGMENT_TREE_METHOD,
    ) -> TradingRangeKthVolumeRead:
        if start_date > end_date:
            raise TradingAlgoQueryValidationError("start_date must be less than or equal to end_date")
        if k < 1:
            raise TradingAlgoQueryValidationError("k must be greater than or equal to 1")
        if method not in SUPPORTED_RANGE_KTH_METHODS:
            raise TradingAlgoQueryValidationError(
                "method must be one of persistent_segment_tree, t_digest"
            )

        rows = TradingRepository.list_volume_series(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
        )
        if not rows:
            raise TradingAlgoQueryNotFoundError(
                f"No volume series found for import_run_id={import_run_id} instrument_code={instrument_code}"
            )

        series = build_trading_volume_series(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            rows=rows,
        )
        left, right_exclusive = self._resolve_interval(
            series.trade_dates,
            start_date=start_date,
            end_date=end_date,
            not_found_message="No trading volume data found in the requested date range",
        )

        interval_length = right_exclusive - left
        if k > interval_length:
            raise TradingAlgoQueryValidationError("k must be less than or equal to the number of records in the requested date range")

        if method == PERSISTENT_SEGMENT_TREE_METHOD:
            result = query_range_kth(series.volumes_scaled, left, right_exclusive - 1, k)
            if not result.matched_indices:
                raise TradingAlgoQueryNotFoundError("No trading volume result found in the requested date range")
            is_approx = False
            approximation_note = None
            matches = self._build_matches(series.trade_dates, result.matched_indices)
        else:
            result = query_range_kth_tdigest(series.volumes_scaled, left, right_exclusive - 1, k)
            is_approx = True
            approximation_note = result.approximation_note
            matches = []

        return TradingRangeKthVolumeRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
            k=k,
            value=unscale_volume(result.kth_value_scaled),
            method=method,
            is_approx=is_approx,
            approximation_note=approximation_note,
            matches=matches,
        )

    def query_joint_anomaly_ranking(
        self,
        session: Session,
        *,
        import_run_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        top_n: int = JOINT_ANOMALY_DEFAULT_TOP_N,
    ) -> TradingJointAnomalyRankingRead:
        if start_date and end_date and start_date > end_date:
            raise TradingAlgoQueryValidationError("start_date must be less than or equal to end_date")
        if top_n <= 0:
            raise TradingAlgoQueryValidationError("top_n must be a positive integer")

        rows = TradingRepository.list_joint_anomaly_rows(session, import_run_id=import_run_id)
        if not rows:
            raise TradingAlgoQueryNotFoundError(f"No trading rows found for import_run_id={import_run_id}")

        events = build_trading_joint_anomaly_events(
            import_run_id=import_run_id,
            rows=rows,
            lookback_window=JOINT_ANOMALY_LOOKBACK_WINDOW,
        )
        if not events:
            raise TradingAlgoQueryDataUnavailableError(
                build_algo_data_unavailable_message(
                    f"联合异常分析至少需要 {JOINT_ANOMALY_LOOKBACK_WINDOW} 日历史窗口和有效样本"
                )
            )

        dominance_result = query_historical_dominance(
            [event.return_z20_scaled for event in events],
            [event.volume_ratio20_scaled for event in events],
        )

        ranked_rows: list[TradingJointAnomalyRowRead] = []
        for historical_sample_count, (event, dominated_count) in enumerate(
            zip(events, dominance_result.dominated_counts, strict=True)
        ):
            if start_date and event.trade_date < start_date:
                continue
            if end_date and event.trade_date > end_date:
                continue

            joint_percentile = 0.0
            if historical_sample_count > 0:
                joint_percentile = float(dominated_count) / float(historical_sample_count)

            severity = self._joint_anomaly_severity(joint_percentile)
            if severity is None:
                continue

            ranked_rows.append(
                TradingJointAnomalyRowRead(
                    instrument_code=event.instrument_code,
                    instrument_name=event.instrument_name,
                    trade_date=event.trade_date,
                    daily_return=round(event.daily_return, 6),
                    return_z20=round(event.return_z20, 6),
                    volume_ratio20=round(event.volume_ratio20, 6),
                    historical_dominated_count=int(dominated_count),
                    historical_sample_count=historical_sample_count,
                    joint_percentile=round(joint_percentile, 6),
                    severity=severity,
                )
            )

        ranked_rows.sort(
            key=lambda item: (
                item.joint_percentile,
                item.historical_dominated_count,
                item.return_z20,
                item.volume_ratio20,
                item.trade_date.toordinal(),
            ),
            reverse=True,
        )

        return TradingJointAnomalyRankingRead(
            import_run_id=import_run_id,
            lookback_window=JOINT_ANOMALY_LOOKBACK_WINDOW,
            rows=ranked_rows[:top_n],
        )

    def _joint_anomaly_severity(self, joint_percentile: float) -> str | None:
        if joint_percentile >= 0.99:
            return "critical"
        if joint_percentile >= 0.95:
            return "high"
        if joint_percentile >= 0.90:
            return "medium"
        return None
