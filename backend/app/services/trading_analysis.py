from __future__ import annotations

from datetime import date
import math

import pandas as pd
from sqlalchemy.orm import Session

from app.repositories.trading import TradingRepository
from app.schemas.trading import (
    TradingAnomalyRead,
    TradingAnomalyReportRead,
    TradingCorrelationMatrixRead,
    TradingCrossSectionRead,
    TradingCrossSectionRowRead,
    TradingIndicatorPointRead,
    TradingIndicatorSeriesRead,
    TradingQualityReportRead,
    TradingRiskMetricsRead,
    TradingRunComparisonRead,
    TradingSummaryRead,
)


VALID_CROSS_SECTION_METRICS = {
    "total_return",
    "volatility",
    "total_volume",
    "total_amount",
    "average_amplitude",
}


class TradingAnalysisValidationError(ValueError):
    """Raised when analysis query parameters are invalid."""


class TradingAnalysisNotFoundError(LookupError):
    """Raised when no trading data matches the requested analysis scope."""


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
            total_amount=self._float(enriched["amount"].sum()),
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
            non_positive_amount_count=int(non_positive_amount_mask.sum()),
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
                amount=self._float(row.amount),
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
                    total_amount=self._float(enriched["amount"].sum()),
                    average_amplitude=self._float(enriched["amplitude"].mean()),
                    latest_close=self._float(enriched["close"].iloc[-1]),
                )
            )

        reverse = True
        rows.sort(key=lambda item: getattr(item, metric) if getattr(item, metric) is not None else float("-inf"), reverse=reverse)
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
                raise TradingAnalysisNotFoundError("No correlation data found for the selected instruments")

        pivot = (
            frame.pivot_table(index="trade_date", columns="instrument_code", values="close", aggfunc="last")
            .sort_index()
            .pct_change(fill_method=None)
            .dropna(how="all")
        )
        if pivot.empty:
            raise TradingAnalysisNotFoundError("Not enough overlapping rows to calculate correlation")

        corr = pivot.corr(min_periods=2)
        codes = [str(code) for code in corr.columns.tolist()]
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
        base_frame = self._load_frame(session, import_run_id=base_run_id)
        target_frame = self._load_frame(session, import_run_id=target_run_id)
        base_codes = {str(item) for item in base_frame["instrument_code"].unique().tolist()}
        target_codes = {str(item) for item in target_frame["instrument_code"].unique().tolist()}

        return TradingRunComparisonRead(
            base_run_id=base_run_id,
            target_run_id=target_run_id,
            base_record_count=int(len(base_frame)),
            target_record_count=int(len(target_frame)),
            base_instrument_count=len(base_codes),
            target_instrument_count=len(target_codes),
            base_total_volume=self._float(base_frame["volume"].sum()),
            target_total_volume=self._float(target_frame["volume"].sum()),
            base_total_amount=self._float(base_frame["amount"].sum()),
            target_total_amount=self._float(target_frame["amount"].sum()),
            base_start_date=self._first_trade_date(base_frame),
            base_end_date=self._last_trade_date(base_frame),
            target_start_date=self._first_trade_date(target_frame),
            target_end_date=self._last_trade_date(target_frame),
            shared_instruments=sorted(base_codes & target_codes),
            added_instruments=sorted(target_codes - base_codes),
            removed_instruments=sorted(base_codes - target_codes),
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
        if start_date and end_date and start_date > end_date:
            raise TradingAnalysisValidationError("start_date must be less than or equal to end_date")

        rows = TradingRepository.list_records(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
        if not rows:
            target = instrument_code or "run"
            raise TradingAnalysisNotFoundError(f"No trading records found for {target}")

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
                    "amount": float(item.amount),
                }
                for item in rows
            ]
        )
        return frame.sort_values(["instrument_code", "trade_date"]).reset_index(drop=True)

    def _enrich_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            raise TradingAnalysisNotFoundError("No trading records found for analysis")

        enriched = frame.sort_values("trade_date").reset_index(drop=True).copy()
        enriched["amplitude"] = (enriched["high"] - enriched["low"]) / enriched["open"].replace(0, pd.NA)
        enriched["daily_return"] = enriched["close"].pct_change()
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

    def _float(self, value: object) -> float:
        return round(float(value), 6)

    def _optional_float(self, value: object) -> float | None:
        if not self._valid_number(value):
            return None
        return round(float(value), 6)

    def _valid_number(self, value: object) -> bool:
        if value is None:
            return False
        try:
            return not pd.isna(value)
        except TypeError:
            return True
