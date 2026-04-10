from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ImportRunRead(BaseModel):
    id: int
    display_id: int
    owner_user_id: int | None
    owner_username: str | None
    dataset_name: str
    asset_class: str | None
    source_type: str
    source_name: str
    original_file_name: str | None
    file_format: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    record_count: int | None
    error_message: str | None
    deleted_at: datetime | None


class ImportMonthlyStatRead(BaseModel):
    month: str
    runs: int
    records: int


class ImportOwnerSummaryRead(BaseModel):
    owner_user_id: int
    owner_username: str | None
    runs: int
    records: int


class ImportStatsRead(BaseModel):
    total_runs: int
    completed_runs: int
    failed_runs: int
    total_records: int
    active_datasets: int
    monthly_imports: list[ImportMonthlyStatRead]
    owner_summaries: list[ImportOwnerSummaryRead]


class DeleteImportRunResponse(BaseModel):
    id: int
    status: str


class TradingInstrumentRead(BaseModel):
    instrument_code: str
    instrument_name: str | None
    first_trade_date: date | None
    last_trade_date: date | None
    record_count: int


class TradingRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_run_id: int
    instrument_code: str
    instrument_name: str | None
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    amount: Decimal


class TradingRangeMaxMatchRead(BaseModel):
    trade_date: date
    series_index: int


class TradingRangeMaxAmountRead(BaseModel):
    import_run_id: int
    instrument_code: str
    start_date: date
    end_date: date
    max_amount: Decimal
    matches: list[TradingRangeMaxMatchRead]


class TradingRangeKthVolumeRead(BaseModel):
    import_run_id: int
    instrument_code: str
    start_date: date
    end_date: date
    k: int
    value: Decimal
    method: str
    is_approx: bool
    approximation_note: str | None
    matches: list[TradingRangeMaxMatchRead]


class TradingJointAnomalyRowRead(BaseModel):
    instrument_code: str
    instrument_name: str | None
    trade_date: date
    daily_return: float
    return_z20: float
    volume_ratio20: float
    historical_dominated_count: int
    historical_sample_count: int
    joint_percentile: float
    severity: str


class TradingJointAnomalyRankingRead(BaseModel):
    import_run_id: int
    lookback_window: int
    rows: list[TradingJointAnomalyRowRead]


class TradingSummaryRead(BaseModel):
    import_run_id: int
    instrument_code: str | None
    instrument_name: str | None
    start_date: date
    end_date: date
    record_count: int
    instrument_count: int
    high_price: float
    low_price: float
    average_close: float
    latest_close: float
    total_volume: float
    total_amount: float
    average_volume: float
    average_amplitude: float


class TradingQualityReportRead(BaseModel):
    import_run_id: int
    instrument_code: str | None
    instrument_name: str | None
    start_date: date
    end_date: date
    record_count: int
    reference_date_count: int
    missing_trade_date_count: int
    missing_trade_dates: list[date]
    invalid_ohlc_count: int
    non_positive_price_count: int
    non_positive_volume_count: int
    non_positive_amount_count: int
    flat_days_count: int
    coverage_ratio: float


class TradingIndicatorPointRead(BaseModel):
    trade_date: date
    close: float
    volume: float
    amount: float
    daily_return: float | None
    cumulative_return: float | None
    ma5: float | None
    ma10: float | None
    ma20: float | None
    ema12: float | None
    ema26: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    rsi14: float | None
    bollinger_mid: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    atr14: float | None


class TradingIndicatorSeriesRead(BaseModel):
    import_run_id: int
    instrument_code: str
    instrument_name: str | None
    start_date: date
    end_date: date
    points: list[TradingIndicatorPointRead]


class TradingRiskMetricsRead(BaseModel):
    import_run_id: int
    instrument_code: str
    instrument_name: str | None
    start_date: date
    end_date: date
    record_count: int
    interval_return: float | None
    volatility: float
    max_drawdown: float
    max_drawdown_duration: int
    up_day_ratio: float
    average_amplitude: float
    max_daily_gain: float | None
    max_daily_loss: float | None


class TradingAnomalyRead(BaseModel):
    trade_date: date
    anomaly_type: str
    severity: str
    metric_value: float
    baseline_value: float | None
    threshold_value: float | None
    description: str


class TradingAnomalyReportRead(BaseModel):
    import_run_id: int
    instrument_code: str
    instrument_name: str | None
    start_date: date
    end_date: date
    anomalies: list[TradingAnomalyRead]


class TradingCrossSectionRowRead(BaseModel):
    instrument_code: str
    instrument_name: str | None
    start_date: date
    end_date: date
    record_count: int
    total_return: float | None
    volatility: float
    total_volume: float
    total_amount: float
    average_amplitude: float
    latest_close: float


class TradingCrossSectionRead(BaseModel):
    import_run_id: int
    metric: str
    start_date: date
    end_date: date
    rows: list[TradingCrossSectionRowRead]


class TradingCorrelationMatrixRead(BaseModel):
    import_run_id: int
    start_date: date
    end_date: date
    instrument_codes: list[str]
    matrix: list[list[float | None]]


class TradingRunComparisonRead(BaseModel):
    base_run_id: int
    target_run_id: int
    base_record_count: int
    target_record_count: int
    base_instrument_count: int
    target_instrument_count: int
    base_total_volume: float
    target_total_volume: float
    base_total_amount: float
    target_total_amount: float
    base_start_date: date
    base_end_date: date
    target_start_date: date
    target_end_date: date
    shared_instruments: list[str]
    added_instruments: list[str]
    removed_instruments: list[str]
