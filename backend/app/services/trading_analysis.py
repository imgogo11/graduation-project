from __future__ import annotations

from datetime import date
from decimal import Decimal
import math

import pandas as pd
from sqlalchemy.orm import Session

from app.repositories.trading import TradingRepository
from app.schemas.trading import (
    TradingAnomalyRead,
    TradingAnomalyReportRead,
    TradingComparisonScopeRead,
    TradingComparisonValueRead,
    TradingCorrelationMatrixRead,
    TradingCrossSectionRead,
    TradingCrossSectionRowRead,
    TradingIndicatorPointRead,
    TradingIndicatorSeriesRead,
    TradingInstrumentOverlapRead,
    TradingMismatchSampleRead,
    TradingMismatchSummaryRead,
    TradingQualityReportRead,
    TradingRiskMetricsRead,
    TradingRecordOverlapRead,
    TradingRunComparisonRead,
    TradingScopeComparisonRead,
    TradingSummaryRead,
)


VALID_CROSS_SECTION_METRICS = {
    "total_return",
    "volatility",
    "total_volume",
    "total_amount",
    "average_amplitude",
}
DATA_INSUFFICIENT_PREFIX = "数据不足分析"


class TradingAnalysisValidationError(ValueError):
    """Raised when analysis query parameters are invalid."""


class TradingAnalysisNotFoundError(LookupError):
    """Raised when no trading data matches the requested analysis scope."""


class TradingAnalysisDataUnavailableError(ValueError):
    """Raised when a panel-specific analysis does not have enough data to run."""


def build_data_unavailable_message(detail: str) -> str:
    return f"{DATA_INSUFFICIENT_PREFIX}：{detail}"


class TradingAnalysisService:
    def build_summary(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingSummaryRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
        enriched = self._enrich_frame(frame)

        return TradingSummaryRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            instrument_name=self._instrument_name(enriched) if instrument_code else None,
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            record_count=int(len(enriched)),
            instrument_count=int(enriched["instrument_code"].nunique()),
            high_price=self._float(enriched["high"].max()),
            low_price=self._float(enriched["low"].min()),
            average_close=self._float(enriched["close"].mean()),
            latest_close=self._float(enriched["close"].iloc[-1]),
            total_volume=self._float(enriched["volume"].sum()),
            total_amount=self._series_sum_or_none(enriched["amount"]),
            average_volume=self._float(enriched["volume"].mean()),
            average_amplitude=self._float(enriched["amplitude"].mean()),
        )

    def build_quality_report(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingQualityReportRead:
        scope_frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
        scope_frame = self._enrich_frame(scope_frame)
        reference_frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            start_date=start_date,
            end_date=end_date,
        )
        reference_dates = sorted(reference_frame["trade_date"].dt.date.unique().tolist())
        scope_dates = set(scope_frame["trade_date"].dt.date.tolist())
        missing_dates = [item for item in reference_dates if item not in scope_dates]

        invalid_ohlc_mask = (
            (scope_frame["high"] < scope_frame[["open", "close", "low"]].max(axis=1))
            | (scope_frame["low"] > scope_frame[["open", "close", "high"]].min(axis=1))
            | (scope_frame["high"] < scope_frame["low"])
        )
        non_positive_price_mask = (
            (scope_frame["open"] <= 0)
            | (scope_frame["high"] <= 0)
            | (scope_frame["low"] <= 0)
            | (scope_frame["close"] <= 0)
        )
        non_positive_volume_mask = scope_frame["volume"] <= 0
        has_amount_data = self._has_series_data(scope_frame["amount"])
        non_positive_amount_mask = scope_frame["amount"] <= 0
        flat_days_mask = (
            (scope_frame["open"] == scope_frame["close"])
            & (scope_frame["close"] == scope_frame["high"])
            & (scope_frame["high"] == scope_frame["low"])
        )

        coverage_ratio = 1.0
        if reference_dates:
            coverage_ratio = len(scope_dates) / len(reference_dates)

        return TradingQualityReportRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            instrument_name=self._instrument_name(scope_frame) if instrument_code else None,
            start_date=self._first_trade_date(scope_frame),
            end_date=self._last_trade_date(scope_frame),
            record_count=int(len(scope_frame)),
            reference_date_count=len(reference_dates),
            missing_trade_date_count=len(missing_dates),
            missing_trade_dates=missing_dates,
            invalid_ohlc_count=int(invalid_ohlc_mask.sum()),
            non_positive_price_count=int(non_positive_price_mask.sum()),
            non_positive_volume_count=int(non_positive_volume_mask.sum()),
            non_positive_amount_count=int(non_positive_amount_mask.sum()) if has_amount_data else None,
            flat_days_count=int(flat_days_mask.sum()),
            coverage_ratio=self._float(coverage_ratio),
        )

    def build_indicator_series(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingIndicatorSeriesRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
        enriched = self._enrich_frame(frame)

        points = [
            TradingIndicatorPointRead(
                trade_date=row.trade_date.date(),
                close=self._float(row.close),
                volume=self._float(row.volume),
                amount=self._optional_float(row.amount),
                daily_return=self._optional_float(row.daily_return),
                cumulative_return=self._optional_float(row.cumulative_return),
                ma5=self._optional_float(row.ma5),
                ma10=self._optional_float(row.ma10),
                ma20=self._optional_float(row.ma20),
                ema12=self._optional_float(row.ema12),
                ema26=self._optional_float(row.ema26),
                macd=self._optional_float(row.macd),
                macd_signal=self._optional_float(row.macd_signal),
                macd_histogram=self._optional_float(row.macd_histogram),
                rsi14=self._optional_float(row.rsi14),
                bollinger_mid=self._optional_float(row.bollinger_mid),
                bollinger_upper=self._optional_float(row.bollinger_upper),
                bollinger_lower=self._optional_float(row.bollinger_lower),
                atr14=self._optional_float(row.atr14),
            )
            for row in enriched.itertuples(index=False)
        ]

        return TradingIndicatorSeriesRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            instrument_name=self._instrument_name(enriched),
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            points=points,
        )

    def build_risk_metrics(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingRiskMetricsRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
        enriched = self._enrich_frame(frame)
        daily_returns = enriched["daily_return"].dropna()
        drawdown = enriched["drawdown"].dropna()
        max_drawdown = 0.0 if drawdown.empty else float(-drawdown.min())

        return TradingRiskMetricsRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            instrument_name=self._instrument_name(enriched),
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            record_count=int(len(enriched)),
            interval_return=self._optional_float(enriched["cumulative_return"].iloc[-1]),
            volatility=self._float(daily_returns.std(ddof=0) if not daily_returns.empty else 0.0),
            max_drawdown=self._float(max_drawdown),
            max_drawdown_duration=self._drawdown_duration(enriched["drawdown"]),
            up_day_ratio=self._float((daily_returns > 0).mean() if not daily_returns.empty else 0.0),
            average_amplitude=self._float(enriched["amplitude"].mean()),
            max_daily_gain=self._optional_float(daily_returns.max() if not daily_returns.empty else None),
            max_daily_loss=self._optional_float(daily_returns.min() if not daily_returns.empty else None),
        )

    def list_anomalies(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingAnomalyReportRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
        enriched = self._enrich_frame(frame)
        anomalies: list[TradingAnomalyRead] = []

        for row in enriched.itertuples(index=False):
            trade_day = row.trade_date.date()

            if self._valid_number(row.volume_baseline):
                threshold = max(float(row.volume_baseline) * 2.0, 1.0)
                if float(row.volume) > threshold:
                    anomalies.append(
                        TradingAnomalyRead(
                            trade_date=trade_day,
                            anomaly_type="volume_spike",
                            severity=self._severity(float(row.volume), threshold),
                            metric_value=self._float(row.volume),
                            baseline_value=self._float(row.volume_baseline),
                            threshold_value=self._float(threshold),
                            description="Volume exceeds 2x the rolling baseline.",
                        )
                    )

            if self._valid_number(row.return_threshold) and self._valid_number(row.daily_return):
                if abs(float(row.daily_return)) > float(row.return_threshold):
                    anomalies.append(
                        TradingAnomalyRead(
                            trade_date=trade_day,
                            anomaly_type="return_spike",
                            severity=self._severity(abs(float(row.daily_return)), float(row.return_threshold)),
                            metric_value=self._float(row.daily_return),
                            baseline_value=self._float(row.return_volatility),
                            threshold_value=self._float(row.return_threshold),
                            description="Absolute daily return exceeds the explainable threshold.",
                        )
                    )

            if self._valid_number(row.amplitude_threshold):
                if float(row.amplitude) > float(row.amplitude_threshold):
                    anomalies.append(
                        TradingAnomalyRead(
                            trade_date=trade_day,
                            anomaly_type="amplitude_spike",
                            severity=self._severity(float(row.amplitude), float(row.amplitude_threshold)),
                            metric_value=self._float(row.amplitude),
                            baseline_value=self._float(row.amplitude_baseline),
                            threshold_value=self._float(row.amplitude_threshold),
                            description="Daily amplitude is unusually wide versus the rolling baseline.",
                        )
                    )

            if self._valid_number(row.previous_rolling_high) and float(row.close) > float(row.previous_rolling_high):
                anomalies.append(
                    TradingAnomalyRead(
                        trade_date=trade_day,
                        anomaly_type="breakout_new_high",
                        severity="high",
                        metric_value=self._float(row.close),
                        baseline_value=self._float(row.previous_rolling_high),
                        threshold_value=self._float(row.previous_rolling_high),
                        description="Close breaks above the previous 20-period rolling high.",
                    )
                )

            if self._valid_number(row.previous_rolling_low) and float(row.close) < float(row.previous_rolling_low):
                anomalies.append(
                    TradingAnomalyRead(
                        trade_date=trade_day,
                        anomaly_type="breakout_new_low",
                        severity="high",
                        metric_value=self._float(row.close),
                        baseline_value=self._float(row.previous_rolling_low),
                        threshold_value=self._float(row.previous_rolling_low),
                        description="Close breaks below the previous 20-period rolling low.",
                    )
                )

        return TradingAnomalyReportRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            instrument_name=self._instrument_name(enriched),
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            anomalies=anomalies,
        )

    def build_cross_section(
        self,
        session: Session,
        *,
        import_run_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        metric: str = "total_return",
        top_n: int | None = None,
    ) -> TradingCrossSectionRead:
        if metric not in VALID_CROSS_SECTION_METRICS:
            raise TradingAnalysisValidationError(
                f"metric must be one of: {', '.join(sorted(VALID_CROSS_SECTION_METRICS))}"
            )
        if top_n is not None and top_n <= 0:
            raise TradingAnalysisValidationError("top_n must be a positive integer")

        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            start_date=start_date,
            end_date=end_date,
        )
        rows: list[TradingCrossSectionRowRead] = []
        for instrument_key, group in frame.groupby("instrument_code", sort=True):
            enriched = self._enrich_frame(group.reset_index(drop=True))
            returns = enriched["daily_return"].dropna()
            rows.append(
                TradingCrossSectionRowRead(
                    instrument_code=str(instrument_key),
                    instrument_name=self._instrument_name(enriched),
                    start_date=self._first_trade_date(enriched),
                    end_date=self._last_trade_date(enriched),
                    record_count=int(len(enriched)),
                    total_return=self._optional_float(enriched["cumulative_return"].iloc[-1]),
                    volatility=self._float(returns.std(ddof=0) if not returns.empty else 0.0),
                    total_volume=self._float(enriched["volume"].sum()),
                    total_amount=self._series_sum_or_none(enriched["amount"]),
                    average_amplitude=self._float(enriched["amplitude"].mean()),
                    latest_close=self._float(enriched["close"].iloc[-1]),
                )
            )

        rows.sort(
            key=lambda item: getattr(item, metric) if getattr(item, metric) is not None else float("-inf"),
            reverse=True,
        )
        if top_n is not None:
            rows = rows[:top_n]

        return TradingCrossSectionRead(
            import_run_id=import_run_id,
            metric=metric,
            start_date=min(item.start_date for item in rows) if rows else self._first_trade_date(frame),
            end_date=max(item.end_date for item in rows) if rows else self._last_trade_date(frame),
            rows=rows,
        )

    def build_correlation_matrix(
        self,
        session: Session,
        *,
        import_run_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        instrument_codes: list[str] | None = None,
    ) -> TradingCorrelationMatrixRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            start_date=start_date,
            end_date=end_date,
        )
        if instrument_codes:
            frame = frame[frame["instrument_code"].isin(instrument_codes)].reset_index(drop=True)
            if frame.empty:
                raise TradingAnalysisDataUnavailableError(
                    build_data_unavailable_message("所选标的没有可用于相关性分析的收盘价数据")
                )

        if frame["instrument_code"].nunique() < 2:
            raise TradingAnalysisDataUnavailableError(build_data_unavailable_message("相关性分析至少需要 2 个标的"))

        pivot = (
            frame.pivot_table(index="trade_date", columns="instrument_code", values="close", aggfunc="last")
            .sort_index()
            .pct_change(fill_method=None)
            .dropna(how="all")
        )
        if pivot.empty:
            raise TradingAnalysisDataUnavailableError(build_data_unavailable_message("缺少重叠收益率样本"))

        corr = pivot.corr(min_periods=2)
        codes = [str(code) for code in corr.columns.tolist()]
        if len(codes) < 2:
            raise TradingAnalysisDataUnavailableError(build_data_unavailable_message("缺少足够的重叠收益率样本"))

        matrix = [
            [self._optional_float(corr.loc[row_code, column_code]) for column_code in codes]
            for row_code in codes
        ]

        return TradingCorrelationMatrixRead(
            import_run_id=import_run_id,
            start_date=frame["trade_date"].min().date(),
            end_date=frame["trade_date"].max().date(),
            instrument_codes=codes,
            matrix=matrix,
        )

    def compare_runs(
        self,
        session: Session,
        *,
        base_run_id: int,
        target_run_id: int,
    ) -> TradingRunComparisonRead:
        scope_comparison = self.compare_scopes(
            session,
            base_run_id=base_run_id,
            target_run_id=target_run_id,
        )

        return TradingRunComparisonRead(
            base_run_id=base_run_id,
            target_run_id=target_run_id,
            base_record_count=scope_comparison.base_scope.record_count,
            target_record_count=scope_comparison.target_scope.record_count,
            base_instrument_count=scope_comparison.base_scope.instrument_count,
            target_instrument_count=scope_comparison.target_scope.instrument_count,
            base_total_volume=scope_comparison.base_scope.total_volume,
            target_total_volume=scope_comparison.target_scope.total_volume,
            base_total_amount=scope_comparison.base_scope.total_amount,
            target_total_amount=scope_comparison.target_scope.total_amount,
            base_start_date=scope_comparison.base_scope.actual_start_date,
            base_end_date=scope_comparison.base_scope.actual_end_date,
            target_start_date=scope_comparison.target_scope.actual_start_date,
            target_end_date=scope_comparison.target_scope.actual_end_date,
            shared_instruments=scope_comparison.instrument_overlap.shared_instruments,
            added_instruments=scope_comparison.instrument_overlap.target_only_instruments,
            removed_instruments=scope_comparison.instrument_overlap.base_only_instruments,
        )

    def compare_scopes(
        self,
        session: Session,
        *,
        base_run_id: int,
        target_run_id: int,
        base_instrument_code: str | None = None,
        target_instrument_code: str | None = None,
        base_start_date: date | None = None,
        base_end_date: date | None = None,
        target_start_date: date | None = None,
        target_end_date: date | None = None,
    ) -> TradingScopeComparisonRead:
        base_rows = self._load_scope_rows(
            session,
            import_run_id=base_run_id,
            instrument_code=base_instrument_code,
            start_date=base_start_date,
            end_date=base_end_date,
            scope_label="当前范围",
        )
        target_rows = self._load_scope_rows(
            session,
            import_run_id=target_run_id,
            instrument_code=target_instrument_code,
            start_date=target_start_date,
            end_date=target_end_date,
            scope_label="对比范围",
        )

        base_frame = self._rows_to_frame(base_rows)
        target_frame = self._rows_to_frame(target_rows)
        base_codes = {str(item) for item in base_frame["instrument_code"].unique().tolist()}
        target_codes = {str(item) for item in target_frame["instrument_code"].unique().tolist()}

        base_lookup = {(str(item.instrument_code), item.trade_date): item for item in base_rows}
        target_lookup = {(str(item.instrument_code), item.trade_date): item for item in target_rows}
        shared_keys = sorted(base_lookup.keys() & target_lookup.keys(), key=lambda item: (item[0], item[1]))

        mismatch_field_counts = {
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "volume": 0,
            "amount": 0,
        }
        mismatch_samples: list[TradingMismatchSampleRead] = []
        mismatched_record_count = 0

        for instrument_code, trade_day in shared_keys:
            base_row = base_lookup[(instrument_code, trade_day)]
            target_row = target_lookup[(instrument_code, trade_day)]
            mismatched_fields = [
                field_name
                for field_name in mismatch_field_counts
                if getattr(base_row, field_name) != getattr(target_row, field_name)
            ]
            if not mismatched_fields:
                continue

            mismatched_record_count += 1
            for field_name in mismatched_fields:
                mismatch_field_counts[field_name] += 1
            if len(mismatch_samples) < 20:
                mismatch_samples.append(
                    TradingMismatchSampleRead(
                        instrument_code=instrument_code,
                        trade_date=trade_day,
                        mismatched_fields=mismatched_fields,
                        base_values=self._build_comparison_value(base_row),
                        target_values=self._build_comparison_value(target_row),
                    )
                )

        return TradingScopeComparisonRead(
            base_scope=self._build_scope_summary(
                base_frame,
                import_run_id=base_run_id,
                instrument_code=base_instrument_code,
                requested_start_date=base_start_date,
                requested_end_date=base_end_date,
            ),
            target_scope=self._build_scope_summary(
                target_frame,
                import_run_id=target_run_id,
                instrument_code=target_instrument_code,
                requested_start_date=target_start_date,
                requested_end_date=target_end_date,
            ),
            instrument_overlap=TradingInstrumentOverlapRead(
                shared_instruments=sorted(base_codes & target_codes),
                base_only_instruments=sorted(base_codes - target_codes),
                target_only_instruments=sorted(target_codes - base_codes),
            ),
            record_overlap=TradingRecordOverlapRead(
                shared_trade_date_count=len({trade_day for _, trade_day in shared_keys}),
                shared_record_count=len(shared_keys),
                base_only_record_count=len(base_lookup) - len(shared_keys),
                target_only_record_count=len(target_lookup) - len(shared_keys),
            ),
            mismatch_summary=TradingMismatchSummaryRead(
                matching_record_count=len(shared_keys) - mismatched_record_count,
                mismatched_record_count=mismatched_record_count,
                open_mismatch_count=mismatch_field_counts["open"],
                high_mismatch_count=mismatch_field_counts["high"],
                low_mismatch_count=mismatch_field_counts["low"],
                close_mismatch_count=mismatch_field_counts["close"],
                volume_mismatch_count=mismatch_field_counts["volume"],
                amount_mismatch_count=mismatch_field_counts["amount"],
            ),
            mismatch_samples=mismatch_samples,
        )

    def _load_frame(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        rows = self._load_scope_rows(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
            scope_label=instrument_code or "当前批次",
        )
        return self._rows_to_frame(rows)

    def _load_scope_rows(
        self,
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        scope_label: str,
    ) -> list[object]:
        if start_date and end_date and start_date > end_date:
            raise TradingAnalysisValidationError("start_date must be less than or equal to end_date")

        rows = TradingRepository.list_records(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
        if rows:
            return rows

        if instrument_code:
            detail = f"{scope_label}中的 {instrument_code} 在当前筛选条件下没有交易记录"
        else:
            detail = f"{scope_label} 在当前筛选条件下没有交易记录"
        raise TradingAnalysisDataUnavailableError(build_data_unavailable_message(detail))

    def _rows_to_frame(self, rows: list[object]) -> pd.DataFrame:
        frame = pd.DataFrame(
            [
                {
                    "instrument_code": item.instrument_code,
                    "instrument_name": item.instrument_name,
                    "trade_date": pd.Timestamp(item.trade_date),
                    "open": float(item.open),
                    "high": float(item.high),
                    "low": float(item.low),
                    "close": float(item.close),
                    "volume": float(item.volume),
                    "amount": float(item.amount) if item.amount is not None else None,
                }
                for item in rows
            ]
        )
        return frame.sort_values(["instrument_code", "trade_date"]).reset_index(drop=True)

    def _build_scope_summary(
        self,
        frame: pd.DataFrame,
        *,
        import_run_id: int,
        instrument_code: str | None,
        requested_start_date: date | None,
        requested_end_date: date | None,
    ) -> TradingComparisonScopeRead:
        return TradingComparisonScopeRead(
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            instrument_name=self._instrument_name(frame) if instrument_code else None,
            requested_start_date=requested_start_date,
            requested_end_date=requested_end_date,
            actual_start_date=self._first_trade_date(frame),
            actual_end_date=self._last_trade_date(frame),
            record_count=int(len(frame)),
            instrument_count=int(frame["instrument_code"].nunique()),
            total_volume=self._float(frame["volume"].sum()),
            total_amount=self._series_sum_or_none(frame["amount"]),
        )

    def _build_comparison_value(self, row: object) -> TradingComparisonValueRead:
        return TradingComparisonValueRead(
            open=self._float(row.open),
            high=self._float(row.high),
            low=self._float(row.low),
            close=self._float(row.close),
            volume=self._float(row.volume),
            amount=self._optional_decimal_to_float(row.amount),
        )

    def _enrich_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            raise TradingAnalysisDataUnavailableError(build_data_unavailable_message("缺少可分析的交易记录"))

        enriched = frame.sort_values("trade_date").reset_index(drop=True).copy()
        enriched["amplitude"] = (enriched["high"] - enriched["low"]) / enriched["open"].replace(0, pd.NA)
        enriched["daily_return"] = enriched["close"].pct_change(fill_method=None)
        first_close = enriched["close"].iloc[0]
        enriched["cumulative_return"] = enriched["close"] / first_close - 1.0
        enriched["ma5"] = enriched["close"].rolling(window=5, min_periods=1).mean()
        enriched["ma10"] = enriched["close"].rolling(window=10, min_periods=1).mean()
        enriched["ma20"] = enriched["close"].rolling(window=20, min_periods=1).mean()
        enriched["ema12"] = enriched["close"].ewm(span=12, adjust=False).mean()
        enriched["ema26"] = enriched["close"].ewm(span=26, adjust=False).mean()
        enriched["macd"] = enriched["ema12"] - enriched["ema26"]
        enriched["macd_signal"] = enriched["macd"].ewm(span=9, adjust=False).mean()
        enriched["macd_histogram"] = (enriched["macd"] - enriched["macd_signal"]) * 2.0

        close_delta = enriched["close"].diff()
        gains = close_delta.clip(lower=0)
        losses = -close_delta.clip(upper=0)
        avg_gain = gains.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        avg_loss = losses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        enriched["rsi14"] = 100 - (100 / (1 + rs))
        enriched.loc[avg_loss == 0, "rsi14"] = 100.0

        enriched["bollinger_mid"] = enriched["close"].rolling(window=20, min_periods=1).mean()
        bollinger_std = enriched["close"].rolling(window=20, min_periods=1).std(ddof=0)
        enriched["bollinger_upper"] = enriched["bollinger_mid"] + bollinger_std * 2.0
        enriched["bollinger_lower"] = enriched["bollinger_mid"] - bollinger_std * 2.0

        previous_close = enriched["close"].shift(1)
        true_range = pd.concat(
            [
                enriched["high"] - enriched["low"],
                (enriched["high"] - previous_close).abs(),
                (enriched["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        enriched["atr14"] = true_range.rolling(window=14, min_periods=1).mean()

        running_peak = enriched["close"].cummax()
        enriched["drawdown"] = enriched["close"] / running_peak - 1.0

        enriched["volume_baseline"] = enriched["volume"].rolling(window=20, min_periods=5).mean().shift(1)
        enriched["return_volatility"] = (
            enriched["daily_return"].abs().rolling(window=20, min_periods=5).std(ddof=0).shift(1)
        )
        enriched["return_threshold"] = enriched["return_volatility"].apply(
            lambda value: max(float(value) * 3.0, 0.05) if self._valid_number(value) else math.nan
        )
        enriched["amplitude_baseline"] = enriched["amplitude"].rolling(window=20, min_periods=5).mean().shift(1)
        enriched["amplitude_threshold"] = enriched["amplitude_baseline"].apply(
            lambda value: max(float(value) * 2.0, 0.04) if self._valid_number(value) else math.nan
        )
        enriched["previous_rolling_high"] = enriched["close"].rolling(window=20, min_periods=5).max().shift(1)
        enriched["previous_rolling_low"] = enriched["close"].rolling(window=20, min_periods=5).min().shift(1)

        return enriched

    def _first_trade_date(self, frame: pd.DataFrame) -> date:
        return frame["trade_date"].min().date()

    def _last_trade_date(self, frame: pd.DataFrame) -> date:
        return frame["trade_date"].max().date()

    def _instrument_name(self, frame: pd.DataFrame) -> str | None:
        values = [item for item in frame["instrument_name"].dropna().tolist() if item]
        return str(values[0]) if values else None

    def _drawdown_duration(self, drawdown: pd.Series) -> int:
        longest = 0
        current = 0
        for value in drawdown.fillna(0.0).tolist():
            if float(value) < 0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    def _severity(self, metric_value: float, threshold_value: float) -> str:
        if threshold_value <= 0:
            return "medium"
        if metric_value >= threshold_value * 1.8:
            return "high"
        return "medium"

    def _has_series_data(self, series: pd.Series) -> bool:
        return series.notna().any()

    def _series_sum_or_none(self, series: pd.Series) -> float | None:
        if not self._has_series_data(series):
            return None
        return self._float(series.sum())

    def _float(self, value: object) -> float:
        return round(float(value), 6)

    def _optional_float(self, value: object) -> float | None:
        if not self._valid_number(value):
            return None
        return round(float(value), 6)

    def _optional_decimal_to_float(self, value: Decimal | None) -> float | None:
        if value is None:
            return None
        return round(float(value), 6)

    def _valid_number(self, value: object) -> bool:
        if value is None:
            return False
        try:
            return not pd.isna(value)
        except TypeError:
            return True
