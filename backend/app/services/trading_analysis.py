from __future__ import annotations

from datetime import date
from decimal import Decimal
import math

import numpy as np
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
    TradingStockOverlapRead,
    TradingMismatchSampleRead,
    TradingMismatchSummaryRead,
    TradingQualityReportRead,
    TradingRiskMetricsRead,
    TradingRecordOverlapRead,
    TradingSnapshotRead,
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
UNADJUSTED_PRICE_NOTICE = "当前指标基于导入价格序列计算，未校验复权状态。"
DATASET_BENCHMARK_SOURCE = "dataset-column"

STANDARD_SCORE_REF = "https://en.wikipedia.org/wiki/Standard_score"
MOVING_AVERAGE_REF = "https://en.wikipedia.org/wiki/Moving_average"
MACD_REF = "https://en.wikipedia.org/wiki/MACD"
RSI_REF = "https://en.wikipedia.org/wiki/Relative_strength_index"
ATR_REF = "https://en.wikipedia.org/wiki/Average_true_range"
BOLLINGER_REF = "https://en.wikipedia.org/wiki/Bollinger_Bands"
OBV_REF = "https://en.wikipedia.org/wiki/On-balance_volume"
VOLATILITY_REF = "https://en.wikipedia.org/wiki/Volatility_%28finance%29"
DRAWDOWN_REF = "https://en.wikipedia.org/wiki/Drawdown_%28economics%29"
BETA_REF = "https://en.wikipedia.org/wiki/Beta_%28finance%29"
RVOL_REF = "https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol"
ILLIQ_REF = "https://www.cis.upenn.edu/~mkearns/finread/amihud.pdf"
MOMENTUM_REF = "https://moneytothemasses.com/wp-content/uploads/2014/08/Jegadeesh_Titman_1993.pdf"
SNAPSHOT_REFS = [
    "https://akshare-hh.readthedocs.io/en/latest/data/stock/stock.html",
    "https://pypi.org/project/baostock/",
]


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
        stock_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingSummaryRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
        )
        enriched = self._enrich_frame(frame)

        return TradingSummaryRead(
            import_run_id=import_run_id,
            stock_code=stock_code,
            stock_name=self._stock_name(enriched) if stock_code else None,
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            record_count=int(len(enriched)),
            stock_count=int(enriched["stock_code"].nunique()),
            high_price=self._float(enriched["high"].max()),
            low_price=self._float(enriched["low"].min()),
            average_close=self._float(enriched["close"].mean()),
            latest_close=self._float(enriched["close"].iloc[-1]),
            total_volume=self._float(enriched["volume"].sum()),
            total_amount=self._series_sum_or_none(enriched["amount"]),
            average_volume=self._float(enriched["volume"].mean()),
            average_amplitude=self._float(enriched["amplitude"].mean()),
            **self._build_contract(
                frame=enriched,
                required_fields=["open", "high", "low", "close", "volume", "amount"],
                data_frequency="daily",
                evidence_refs=[MOVING_AVERAGE_REF, VOLATILITY_REF],
            ),
        )

    def build_quality_report(
        self,
        session: Session,
        *,
        import_run_id: int,
        stock_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingQualityReportRead:
        scope_frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
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
            stock_code=stock_code,
            stock_name=self._stock_name(scope_frame) if stock_code else None,
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
            **self._build_contract(
                frame=scope_frame,
                required_fields=["open", "high", "low", "close", "volume", "amount"],
                data_frequency="daily",
                evidence_refs=[VOLATILITY_REF],
            ),
        )

    def build_indicator_series(
        self,
        session: Session,
        *,
        import_run_id: int,
        stock_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingIndicatorSeriesRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
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
                turnover=self._optional_float(row.turnover),
                daily_return=self._optional_float(row.daily_return),
                log_return=self._optional_float(row.log_return),
                cumulative_return=self._optional_float(row.cumulative_return),
                ma5=self._optional_float(row.ma5),
                ma10=self._optional_float(row.ma10),
                ma20=self._optional_float(row.ma20),
                ma60=self._optional_float(row.ma60),
                ema12=self._optional_float(row.ema12),
                ema26=self._optional_float(row.ema26),
                macd=self._optional_float(row.macd),
                macd_signal=self._optional_float(row.macd_signal),
                macd_histogram=self._optional_float(row.macd_histogram),
                bias20=self._optional_float(row.bias20),
                rsi14=self._optional_float(row.rsi14),
                roc20=self._optional_float(row.roc20),
                obv=self._optional_float(row.obv),
                bollinger_mid=self._optional_float(row.bollinger_mid),
                bollinger_upper=self._optional_float(row.bollinger_upper),
                bollinger_lower=self._optional_float(row.bollinger_lower),
                bandwidth=self._optional_float(row.bandwidth),
                atr14=self._optional_float(row.atr14),
                natr14=self._optional_float(row.natr14),
                hv20=self._optional_float(row.hv20),
                rvol20=self._optional_float(row.rvol20),
                turnover_z20=self._optional_float(row.turnover_z20),
                illiq20=self._optional_float(row.illiq20),
            )
            for row in enriched.itertuples(index=False)
        ]

        return TradingIndicatorSeriesRead(
            import_run_id=import_run_id,
            stock_code=stock_code,
            stock_name=self._stock_name(enriched),
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            points=points,
            notices=self._optional_metric_notices(enriched),
            **self._build_contract(
                frame=enriched,
                required_fields=["close", "high", "low", "volume", "amount", "turnover"],
                data_frequency="daily",
                evidence_refs=[
                    MOVING_AVERAGE_REF,
                    MACD_REF,
                    RSI_REF,
                    ATR_REF,
                    BOLLINGER_REF,
                    OBV_REF,
                    VOLATILITY_REF,
                    RVOL_REF,
                    ILLIQ_REF,
                    MOMENTUM_REF,
                ],
            ),
        )

    def build_risk_metrics(
        self,
        session: Session,
        *,
        import_run_id: int,
        stock_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingRiskMetricsRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
        )
        enriched = self._enrich_frame(frame)
        daily_returns = enriched["daily_return"].dropna()
        log_returns = enriched["log_return"].dropna()
        drawdown = enriched["drawdown"].dropna()
        max_drawdown = 0.0 if drawdown.empty else float(-drawdown.min())
        latest_row = enriched.iloc[-1]
        beta60 = self._compute_beta60(enriched)
        downside_volatility = self._downside_volatility(log_returns)

        return TradingRiskMetricsRead(
            import_run_id=import_run_id,
            stock_code=stock_code,
            stock_name=self._stock_name(enriched),
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            record_count=int(len(enriched)),
            interval_return=self._optional_float(enriched["cumulative_return"].iloc[-1]),
            volatility=self._float(log_returns.std(ddof=0) * math.sqrt(252.0) if not log_returns.empty else 0.0),
            max_drawdown=self._float(max_drawdown),
            max_drawdown_duration=self._drawdown_duration(enriched["drawdown"]),
            up_day_ratio=self._float((daily_returns > 0).mean() if not daily_returns.empty else 0.0),
            average_amplitude=self._float(enriched["amplitude"].mean()),
            max_daily_gain=self._optional_float(daily_returns.max() if not daily_returns.empty else None),
            max_daily_loss=self._optional_float(daily_returns.min() if not daily_returns.empty else None),
            beta60=self._optional_float(beta60),
            downside_volatility=self._optional_float(downside_volatility),
            hv20=self._optional_float(latest_row.hv20),
            rvol20=self._optional_float(latest_row.rvol20),
            turnover_z20=self._optional_float(latest_row.turnover_z20),
            illiq20=self._optional_float(latest_row.illiq20),
            notices=self._optional_metric_notices(enriched),
            **self._build_contract(
                frame=enriched,
                required_fields=["close", "high", "low", "amount", "turnover", "benchmark_close"],
                data_frequency="daily",
                evidence_refs=[VOLATILITY_REF, DRAWDOWN_REF, BETA_REF, RVOL_REF, ILLIQ_REF, ATR_REF],
                benchmark_source=DATASET_BENCHMARK_SOURCE,
            ),
        )

    def list_anomalies(
        self,
        session: Session,
        *,
        import_run_id: int,
        stock_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingAnomalyReportRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
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
                            description="成交量超过滚动基线的 2 倍。",
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
                            description="日收益率绝对值超过可解释阈值。",
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
                            description="日内振幅相对滚动基线异常放大。",
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
                        description="收盘价突破前 20 期滚动高点。",
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
                        description="收盘价跌破前 20 期滚动低点。",
                    )
                )

        return TradingAnomalyReportRead(
            import_run_id=import_run_id,
            stock_code=stock_code,
            stock_name=self._stock_name(enriched),
            start_date=self._first_trade_date(enriched),
            end_date=self._last_trade_date(enriched),
            anomalies=anomalies,
            **self._build_contract(
                frame=enriched,
                required_fields=["open", "high", "low", "close", "volume"],
                data_frequency="daily",
                evidence_refs=[STANDARD_SCORE_REF, ATR_REF],
            ),
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
        for stock_key, group in frame.groupby("stock_code", sort=True):
            enriched = self._enrich_frame(group.reset_index(drop=True))
            returns = enriched["daily_return"].dropna()
            rows.append(
                TradingCrossSectionRowRead(
                    stock_code=str(stock_key),
                    stock_name=self._stock_name(enriched),
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
            **self._build_contract(
                frame=frame,
                required_fields=["open", "high", "low", "close", "volume", "amount"],
                data_frequency="daily",
                evidence_refs=[VOLATILITY_REF, MOMENTUM_REF],
            ),
        )

    def build_correlation_matrix(
        self,
        session: Session,
        *,
        import_run_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        stock_codes: list[str] | None = None,
    ) -> TradingCorrelationMatrixRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            start_date=start_date,
            end_date=end_date,
        )
        if stock_codes:
            frame = frame[frame["stock_code"].isin(stock_codes)].reset_index(drop=True)
            if frame.empty:
                raise TradingAnalysisDataUnavailableError(
                    build_data_unavailable_message("所选股票没有可用于相关性分析的收盘价数据")
                )

        if frame["stock_code"].nunique() < 1:
            raise TradingAnalysisDataUnavailableError(build_data_unavailable_message("相关性分析至少需要 1 只股票"))

        pivot = (
            frame.pivot_table(index="trade_date", columns="stock_code", values="close", aggfunc="last")
            .sort_index()
            .pct_change(fill_method=None)
            .dropna(how="all")
        )
        if pivot.empty:
            raise TradingAnalysisDataUnavailableError(build_data_unavailable_message("缺少重叠收益率样本"))

        corr = pivot.corr(min_periods=2)
        codes = [str(code) for code in corr.columns.tolist()]
        if not codes:
            raise TradingAnalysisDataUnavailableError(build_data_unavailable_message("缺少足够的重叠收益率样本"))

        matrix: list[list[float | None]] = []
        for row_code in codes:
            row: list[float | None] = []
            for column_code in codes:
                value = self._optional_float(corr.loc[row_code, column_code])
                if value is None and row_code == column_code:
                    # 单股票范围或样本不足时，自相关对角线默认展示为 1.0，避免前端出现无意义空值。
                    value = 1.0
                row.append(value)
            matrix.append(row)

        return TradingCorrelationMatrixRead(
            import_run_id=import_run_id,
            start_date=frame["trade_date"].min().date(),
            end_date=frame["trade_date"].max().date(),
            stock_codes=codes,
            matrix=matrix,
            **self._build_contract(
                frame=frame,
                required_fields=["close"],
                data_frequency="daily",
                evidence_refs=[VOLATILITY_REF],
            ),
        )

    def compare_scopes(
        self,
        session: Session,
        *,
        base_run_id: int,
        target_run_id: int,
        base_stock_code: str | None = None,
        target_stock_code: str | None = None,
        base_start_date: date | None = None,
        base_end_date: date | None = None,
        target_start_date: date | None = None,
        target_end_date: date | None = None,
    ) -> TradingScopeComparisonRead:
        base_rows = self._load_scope_rows(
            session,
            import_run_id=base_run_id,
            stock_code=base_stock_code,
            start_date=base_start_date,
            end_date=base_end_date,
            scope_label="当前范围",
        )
        target_rows = self._load_scope_rows(
            session,
            import_run_id=target_run_id,
            stock_code=target_stock_code,
            start_date=target_start_date,
            end_date=target_end_date,
            scope_label="对比范围",
        )

        base_frame = self._rows_to_frame(base_rows)
        target_frame = self._rows_to_frame(target_rows)
        base_codes = {str(item) for item in base_frame["stock_code"].unique().tolist()}
        target_codes = {str(item) for item in target_frame["stock_code"].unique().tolist()}

        base_lookup = {(str(item.stock_code), item.trade_date): item for item in base_rows}
        target_lookup = {(str(item.stock_code), item.trade_date): item for item in target_rows}
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

        for stock_code, trade_day in shared_keys:
            base_row = base_lookup[(stock_code, trade_day)]
            target_row = target_lookup[(stock_code, trade_day)]
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
                        stock_code=stock_code,
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
                stock_code=base_stock_code,
                requested_start_date=base_start_date,
                requested_end_date=base_end_date,
            ),
            target_scope=self._build_scope_summary(
                target_frame,
                import_run_id=target_run_id,
                stock_code=target_stock_code,
                requested_start_date=target_start_date,
                requested_end_date=target_end_date,
            ),
            stock_overlap=TradingStockOverlapRead(
                shared_stocks=sorted(base_codes & target_codes),
                base_only_stocks=sorted(base_codes - target_codes),
                target_only_stocks=sorted(target_codes - base_codes),
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
            **self._build_contract(
                frame=pd.concat([base_frame, target_frame], ignore_index=True),
                required_fields=["open", "high", "low", "close", "volume", "amount"],
                data_frequency="daily",
                evidence_refs=[VOLATILITY_REF],
            ),
        )

    def build_snapshot(
        self,
        session: Session,
        *,
        import_run_id: int,
        stock_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradingSnapshotRead:
        frame = self._load_frame(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
        )

        return TradingSnapshotRead(
            import_run_id=import_run_id,
            stock_code=stock_code,
            stock_name=self._stock_name(frame),
            valuation_as_of=self._optional_datetime(self._latest_value(frame, "valuation_as_of")),
            fundamental_report_date=self._optional_date(self._latest_value(frame, "fundamental_report_date")),
            pe_ttm=self._optional_float(self._latest_value(frame, "pe_ttm")),
            pb=self._optional_float(self._latest_value(frame, "pb")),
            roe=self._optional_float(self._latest_value(frame, "roe")),
            asset_liability_ratio=self._optional_float(self._latest_value(frame, "asset_liability_ratio")),
            revenue_yoy=self._optional_float(self._latest_value(frame, "revenue_yoy")),
            net_profit_yoy=self._optional_float(self._latest_value(frame, "net_profit_yoy")),
            **self._build_contract(
                frame=frame,
                required_fields=[
                    "pe_ttm",
                    "pb",
                    "roe",
                    "asset_liability_ratio",
                    "revenue_yoy",
                    "net_profit_yoy",
                    "valuation_as_of",
                    "fundamental_report_date",
                ],
                data_frequency="snapshot/report",
                evidence_refs=SNAPSHOT_REFS,
            ),
        )

    def _load_frame(
        self,
        session: Session,
        *,
        import_run_id: int,
        stock_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        rows = self._load_scope_rows(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            scope_label=stock_code or "当前批次",
        )
        return self._rows_to_frame(rows)

    def _load_scope_rows(
        self,
        session: Session,
        *,
        import_run_id: int,
        stock_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        scope_label: str,
    ) -> list[object]:
        if start_date and end_date and start_date > end_date:
            raise TradingAnalysisValidationError("start_date must be less than or equal to end_date")

        rows = TradingRepository.list_records(
            session,
            import_run_id=import_run_id,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
        )
        if rows:
            return rows

        if stock_code:
            detail = f"{scope_label}中的 {stock_code} 在当前筛选条件下没有交易记录"
        else:
            detail = f"{scope_label} 在当前筛选条件下没有交易记录"
        raise TradingAnalysisDataUnavailableError(build_data_unavailable_message(detail))

    def _rows_to_frame(self, rows: list[object]) -> pd.DataFrame:
        frame = pd.DataFrame(
            [
                {
                    "stock_code": item.stock_code,
                    "stock_name": item.stock_name,
                    "trade_date": pd.Timestamp(item.trade_date),
                    "open": float(item.open),
                    "high": float(item.high),
                    "low": float(item.low),
                    "close": float(item.close),
                    "volume": float(item.volume),
                    "amount": float(item.amount) if item.amount is not None else None,
                    "turnover": float(item.turnover) if item.turnover is not None else None,
                    "benchmark_close": self._optional_to_float(getattr(item, "benchmark_close", None)),
                    "pe_ttm": self._optional_to_float(getattr(item, "pe_ttm", None)),
                    "pb": self._optional_to_float(getattr(item, "pb", None)),
                    "roe": self._optional_to_float(getattr(item, "roe", None)),
                    "asset_liability_ratio": self._optional_to_float(getattr(item, "asset_liability_ratio", None)),
                    "revenue_yoy": self._optional_to_float(getattr(item, "revenue_yoy", None)),
                    "net_profit_yoy": self._optional_to_float(getattr(item, "net_profit_yoy", None)),
                    "valuation_as_of": pd.Timestamp(getattr(item, "valuation_as_of", None))
                    if getattr(item, "valuation_as_of", None) is not None
                    else pd.NaT,
                    "fundamental_report_date": pd.Timestamp(getattr(item, "fundamental_report_date", None))
                    if getattr(item, "fundamental_report_date", None) is not None
                    else pd.NaT,
                }
                for item in rows
            ]
        )
        return frame.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)

    def _build_scope_summary(
        self,
        frame: pd.DataFrame,
        *,
        import_run_id: int,
        stock_code: str | None,
        requested_start_date: date | None,
        requested_end_date: date | None,
    ) -> TradingComparisonScopeRead:
        return TradingComparisonScopeRead(
            import_run_id=import_run_id,
            stock_code=stock_code,
            stock_name=self._stock_name(frame) if stock_code else None,
            requested_start_date=requested_start_date,
            requested_end_date=requested_end_date,
            actual_start_date=self._first_trade_date(frame),
            actual_end_date=self._last_trade_date(frame),
            record_count=int(len(frame)),
            stock_count=int(frame["stock_code"].nunique()),
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

        enriched = frame.sort_values(["stock_code", "trade_date"]).reset_index(drop=True).copy()
        grouped = enriched.groupby("stock_code", sort=False)

        enriched["amplitude"] = (enriched["high"] - enriched["low"]) / enriched["open"].replace(0, pd.NA)
        enriched["daily_return"] = grouped["close"].pct_change(fill_method=None)
        enriched["log_return"] = np.log(enriched["close"] / grouped["close"].shift(1))
        first_close = grouped["close"].transform("first")
        enriched["cumulative_return"] = enriched["close"] / first_close - 1.0

        enriched["ma5"] = grouped["close"].transform(lambda series: series.rolling(window=5, min_periods=1).mean())
        enriched["ma10"] = grouped["close"].transform(lambda series: series.rolling(window=10, min_periods=1).mean())
        enriched["ma20"] = grouped["close"].transform(lambda series: series.rolling(window=20, min_periods=1).mean())
        enriched["ma60"] = grouped["close"].transform(lambda series: series.rolling(window=60, min_periods=1).mean())
        enriched["ema12"] = grouped["close"].transform(lambda series: series.ewm(span=12, adjust=False).mean())
        enriched["ema26"] = grouped["close"].transform(lambda series: series.ewm(span=26, adjust=False).mean())
        enriched["macd"] = enriched["ema12"] - enriched["ema26"]
        enriched["macd_signal"] = grouped["macd"].transform(lambda series: series.ewm(span=9, adjust=False).mean())
        enriched["macd_histogram"] = (enriched["macd"] - enriched["macd_signal"]) * 2.0
        enriched["bias20"] = enriched["close"] / enriched["ma20"].replace(0.0, pd.NA) - 1.0

        close_delta = grouped["close"].diff()
        gains = close_delta.clip(lower=0)
        losses = -close_delta.clip(upper=0)
        avg_gain = gains.groupby(enriched["stock_code"]).transform(
            lambda series: series.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        )
        avg_loss = losses.groupby(enriched["stock_code"]).transform(
            lambda series: series.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        )
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        enriched["rsi14"] = 100 - (100 / (1 + rs))
        enriched.loc[avg_loss == 0, "rsi14"] = 100.0
        enriched["roc20"] = enriched["close"] / grouped["close"].shift(20) - 1.0

        direction = np.sign(close_delta).fillna(0.0)
        enriched["obv"] = (direction * enriched["volume"]).groupby(enriched["stock_code"]).cumsum()

        enriched["bollinger_mid"] = grouped["close"].transform(lambda series: series.rolling(window=20, min_periods=1).mean())
        bollinger_std = grouped["close"].transform(lambda series: series.rolling(window=20, min_periods=1).std(ddof=0))
        enriched["bollinger_upper"] = enriched["bollinger_mid"] + bollinger_std * 2.0
        enriched["bollinger_lower"] = enriched["bollinger_mid"] - bollinger_std * 2.0
        enriched["bandwidth"] = (
            (enriched["bollinger_upper"] - enriched["bollinger_lower"]) / enriched["bollinger_mid"].replace(0.0, pd.NA)
        )

        previous_close = grouped["close"].shift(1)
        true_range = pd.concat(
            [
                enriched["high"] - enriched["low"],
                (enriched["high"] - previous_close).abs(),
                (enriched["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        enriched["atr14"] = true_range.groupby(enriched["stock_code"]).transform(
            lambda series: series.rolling(window=14, min_periods=1).mean()
        )
        enriched["natr14"] = enriched["atr14"] / enriched["close"].replace(0.0, pd.NA)
        enriched["hv20"] = grouped["log_return"].transform(
            lambda series: series.rolling(window=20, min_periods=20).std(ddof=0) * math.sqrt(252.0)
        )

        running_peak = grouped["close"].cummax()
        enriched["drawdown"] = enriched["close"] / running_peak - 1.0

        volume_ma20 = grouped["volume"].transform(lambda series: series.rolling(window=20, min_periods=20).mean())
        enriched["rvol20"] = enriched["volume"] / volume_ma20.replace(0.0, pd.NA)

        if "turnover" in enriched.columns:
            turnover_mean20 = grouped["turnover"].transform(lambda series: series.rolling(window=20, min_periods=20).mean())
            turnover_std20 = grouped["turnover"].transform(lambda series: series.rolling(window=20, min_periods=20).std(ddof=0))
            enriched["turnover_z20"] = (enriched["turnover"] - turnover_mean20) / turnover_std20.replace(0.0, pd.NA)
        else:
            enriched["turnover_z20"] = math.nan

        amount_for_impact = enriched["amount"].where(enriched["amount"] > 0)
        illiq_component = enriched["log_return"].abs() / amount_for_impact
        enriched["illiq20"] = illiq_component.groupby(enriched["stock_code"]).transform(
            lambda series: series.rolling(window=20, min_periods=20).mean()
        )

        enriched["volume_baseline"] = grouped["volume"].transform(
            lambda series: series.rolling(window=20, min_periods=5).mean().shift(1)
        )
        enriched["return_volatility"] = grouped["daily_return"].transform(
            lambda series: series.abs().rolling(window=20, min_periods=5).std(ddof=0).shift(1)
        )
        enriched["return_threshold"] = enriched["return_volatility"].apply(
            lambda value: max(float(value) * 3.0, 0.05) if self._valid_number(value) else math.nan
        )
        enriched["amplitude_baseline"] = grouped["amplitude"].transform(
            lambda series: series.rolling(window=20, min_periods=5).mean().shift(1)
        )
        enriched["amplitude_threshold"] = enriched["amplitude_baseline"].apply(
            lambda value: max(float(value) * 2.0, 0.04) if self._valid_number(value) else math.nan
        )
        enriched["previous_rolling_high"] = grouped["close"].transform(
            lambda series: series.rolling(window=20, min_periods=5).max().shift(1)
        )
        enriched["previous_rolling_low"] = grouped["close"].transform(
            lambda series: series.rolling(window=20, min_periods=5).min().shift(1)
        )

        return enriched

    def _compute_beta60(self, stock_frame: pd.DataFrame) -> float | None:
        if "benchmark_close" not in stock_frame.columns:
            return None

        benchmark_close = stock_frame.sort_values("trade_date").set_index("trade_date")["benchmark_close"]
        if benchmark_close.dropna().empty:
            return None

        market_log_return = np.log(benchmark_close / benchmark_close.shift(1))

        stock_series = (
            stock_frame.sort_values("trade_date")
            .set_index("trade_date")["log_return"]
            .rename("stock_log_return")
        )
        market_series = market_log_return.rename("market_log_return")
        merged = pd.concat([stock_series, market_series], axis=1).dropna()
        if len(merged) < 60:
            return None

        window = merged.tail(60)
        market_variance = float(window["market_log_return"].var(ddof=0))
        if market_variance <= 0:
            return None

        covariance = float(
            (
                (window["stock_log_return"] - window["stock_log_return"].mean())
                * (window["market_log_return"] - window["market_log_return"].mean())
            ).mean()
        )
        return covariance / market_variance

    def _downside_volatility(self, log_returns: pd.Series) -> float | None:
        if log_returns.empty:
            return None
        downside = np.minimum(log_returns.to_numpy(dtype=float), 0.0)
        return float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(252.0))

    def _optional_metric_notices(self, frame: pd.DataFrame) -> list[str]:
        notices: list[str] = []
        has_turnover = "turnover" in frame.columns and frame["turnover"].notna().any()
        has_amount = "amount" in frame.columns and frame["amount"].notna().any()
        has_benchmark_close = "benchmark_close" in frame.columns and frame["benchmark_close"].notna().any()
        notices.append(UNADJUSTED_PRICE_NOTICE)
        if not has_turnover:
            notices.append("缺少可选列 turnover（换手率），相关增强指标（换手率 Z20）已置空。")
        if not has_amount:
            notices.append("缺少可选列 amount（成交额），相关增强指标（ILLIQ20）已置空。")
        if not has_benchmark_close:
            notices.append("缺少 benchmark_close（基准收盘价），Beta60 已置空。")
        return notices

    def _build_contract(
        self,
        *,
        frame: pd.DataFrame,
        required_fields: list[str],
        data_frequency: str,
        evidence_refs: list[str],
        benchmark_code: str | None = None,
        benchmark_source: str | None = None,
    ) -> dict[str, object]:
        missing_fields = [field_name for field_name in required_fields if not self._has_field_data(frame, field_name)]
        return {
            "required_fields": required_fields,
            "missing_fields": missing_fields,
            "data_frequency": data_frequency,
            "evidence_refs": evidence_refs,
            "benchmark_code": benchmark_code,
            "benchmark_source": benchmark_source,
        }

    def _has_field_data(self, frame: pd.DataFrame, field_name: str) -> bool:
        return field_name in frame.columns and frame[field_name].notna().any()

    def _latest_value(self, frame: pd.DataFrame, field_name: str) -> object:
        if field_name not in frame.columns:
            return None
        series = frame[field_name].dropna()
        if series.empty:
            return None
        return series.iloc[-1]

    def _first_trade_date(self, frame: pd.DataFrame) -> date:
        return frame["trade_date"].min().date()

    def _last_trade_date(self, frame: pd.DataFrame) -> date:
        return frame["trade_date"].max().date()

    def _stock_name(self, frame: pd.DataFrame) -> str | None:
        values = [item for item in frame["stock_name"].dropna().tolist() if item]
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

    def _optional_to_float(self, value: object) -> float | None:
        if not self._valid_number(value):
            return None
        return float(value)

    def _optional_datetime(self, value: object) -> pd.Timestamp | None:
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        if isinstance(value, date):
            return pd.Timestamp(value).to_pydatetime()
        try:
            return pd.Timestamp(value).to_pydatetime()
        except (TypeError, ValueError):
            return None

    def _optional_date(self, value: object) -> date | None:
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return pd.Timestamp(value).date()
        except (TypeError, ValueError):
            return None

    def _valid_number(self, value: object) -> bool:
        if value is None:
            return False
        try:
            return not pd.isna(value)
        except TypeError:
            return True

