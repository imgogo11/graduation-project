from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TradingDataContractRead(BaseModel):
    required_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    data_frequency: str = "daily"
    evidence_refs: list[str] = Field(default_factory=list)
    benchmark_code: str | None = None
    benchmark_source: str | None = None


class ImportRunRead(BaseModel):
    id: int
    display_id: int
    owner_user_id: int | None
    owner_username: str | None
    dataset_name: str
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
    available_datasets: int
    monthly_imports: list[ImportMonthlyStatRead]
    owner_summaries: list[ImportOwnerSummaryRead]


class DeleteImportRunResponse(BaseModel):
    id: int
    status: str


class ImportMappingCandidateRead(BaseModel):
    original_column: str
    header_score: float
    value_score: float
    template_bonus: float
    total_score: float
    confidence: str
    reasons: list[str]


class ImportFieldSuggestionRead(BaseModel):
    canonical_column: str
    required: bool
    selected_original_column: str | None
    selected_score: float | None
    selected_confidence: str
    candidates: list[ImportMappingCandidateRead]


class ImportMappingConflictRead(BaseModel):
    canonical_column: str
    primary_original_column: str
    secondary_original_column: str
    gap: float
    message: str


class ImportPreviewRead(BaseModel):
    preview_id: str
    expires_at: datetime
    can_auto_commit: bool
    required_confirmation_needed: bool
    required_issue_columns: list[str]
    matcher_engine: str
    required_columns: list[str]
    optional_columns: list[str]
    original_columns: list[str]
    ignored_columns: list[str]
    suggested_mapping: dict[str, str]
    missing_required: list[str]
    conflicts: list[ImportMappingConflictRead]
    field_suggestions: list[ImportFieldSuggestionRead]
    action_hints: list[str]


class ImportCommitRequest(BaseModel):
    preview_id: str
    required_confirmation_ack: bool = False
    mapping_overrides: dict[str, str | None] = Field(default_factory=dict)


class TradingStockRead(BaseModel):
    stock_code: str
    stock_name: str | None
    first_trade_date: date | None
    last_trade_date: date | None
    record_count: int


class TradingRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_run_id: int
    stock_code: str
    stock_name: str | None
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    amount: Decimal | None
    turnover: Decimal | None
    benchmark_close: Decimal | None
    pe_ttm: Decimal | None
    pb: Decimal | None
    roe: Decimal | None
    asset_liability_ratio: Decimal | None
    revenue_yoy: Decimal | None
    net_profit_yoy: Decimal | None
    valuation_as_of: datetime | None
    fundamental_report_date: date | None


class TradingRangeMaxMatchRead(BaseModel):
    trade_date: date
    series_index: int


class TradingRangeMaxAmountRead(BaseModel):
    import_run_id: int
    stock_code: str
    start_date: date
    end_date: date
    max_amount: Decimal
    matches: list[TradingRangeMaxMatchRead]


class TradingRangeKthVolumeRead(BaseModel):
    import_run_id: int
    stock_code: str
    start_date: date
    end_date: date
    k: int
    value: Decimal
    method: str
    is_approx: bool
    approximation_note: str | None
    matches: list[TradingRangeMaxMatchRead]


class TradingJointAnomalyRowRead(BaseModel):
    stock_code: str
    stock_name: str | None
    trade_date: date
    daily_return: float
    return_z20: float
    volume_ratio20: float
    historical_dominated_count: int
    historical_sample_count: int
    joint_percentile: float
    severity: str


class TradingJointAnomalyRankingRead(TradingDataContractRead):
    import_run_id: int
    lookback_window: int
    rows: list[TradingJointAnomalyRowRead]


class AlgoIndexStatusRead(BaseModel):
    import_run_id: int
    status: str
    is_ready: bool
    build_started_at: datetime | None
    build_completed_at: datetime | None
    build_duration_ms: int | None
    stock_count: int | None
    event_count: int | None
    reuse_count: int
    last_error: str | None


class TradingRiskRadarEventRead(BaseModel):
    stock_code: str
    stock_name: str | None
    trade_date: date
    daily_return: float
    return_z20: float
    volume_ratio20: float
    amplitude_ratio20: float
    return_shock: float
    vol_regime: float | None
    range_shock: float
    rvol20: float
    liquidity_shock: float
    drawdown_pressure: float
    score_return_shock: float | None
    score_vol_regime: float | None
    score_range_shock: float | None
    score_rvol20: float | None
    score_liquidity_shock: float | None
    score_drawdown_pressure: float | None
    historical_dominated_count: int
    historical_sample_count: int
    joint_percentile: float
    severity: str
    cause_label: str


class TradingStockRiskProfileRead(BaseModel):
    stock_code: str
    stock_name: str | None
    event_count: int
    medium_count: int
    high_count: int
    critical_count: int
    max_joint_percentile: float
    avg_joint_percentile: float
    latest_event_date: date
    top_event_date: date
    top_event_severity: str


class TradingRiskRadarCalendarDayRead(BaseModel):
    trade_date: date
    event_count: int
    impacted_stock_count: int
    medium_count: int
    high_count: int
    critical_count: int
    max_joint_percentile: float


class TradingRiskRadarOverviewRead(TradingDataContractRead):
    import_run_id: int
    lookback_window: int
    generated_at: datetime | None
    total_events: int
    impacted_stock_count: int
    medium_count: int
    high_count: int
    critical_count: int
    top_stocks: list[TradingStockRiskProfileRead]
    busiest_dates: list[TradingRiskRadarCalendarDayRead]


class TradingRiskRadarEventListRead(TradingDataContractRead):
    import_run_id: int
    rows: list[TradingRiskRadarEventRead]


class TradingRiskRadarStockListRead(TradingDataContractRead):
    import_run_id: int
    rows: list[TradingStockRiskProfileRead]


class TradingRiskRadarCalendarRead(TradingDataContractRead):
    import_run_id: int
    rows: list[TradingRiskRadarCalendarDayRead]


class TradingRiskRadarWindowRead(BaseModel):
    window_days: int
    current_value: float
    exact_percentile: float
    p50: float
    p90: float
    p95: float
    top_1: float
    top_3: float | None


class TradingRiskRadarWindowGroupRead(BaseModel):
    metric: str
    label: str
    windows: list[TradingRiskRadarWindowRead]


class TradingRiskRadarDistributionChangeRead(BaseModel):
    metric: str
    window_days: int
    before_median: float
    before_p90: float
    before_p95: float
    after_median: float
    after_p90: float
    after_p95: float


class TradingRiskRadarAmountPeakRead(BaseModel):
    start_date: date
    end_date: date
    peak_amount: float
    peak_dates: list[TradingRangeMaxMatchRead]


class TradingRiskRadarEventContextRead(TradingDataContractRead):
    import_run_id: int
    event: TradingRiskRadarEventRead
    window_groups: list[TradingRiskRadarWindowGroupRead]
    distribution_changes: list[TradingRiskRadarDistributionChangeRead]
    local_amount_peak: TradingRiskRadarAmountPeakRead | None


class TradingSummaryRead(TradingDataContractRead):
    import_run_id: int
    stock_code: str | None
    stock_name: str | None
    start_date: date
    end_date: date
    record_count: int
    stock_count: int
    high_price: float
    low_price: float
    average_close: float
    latest_close: float
    total_volume: float
    total_amount: float | None
    average_volume: float
    average_amplitude: float


class TradingQualityReportRead(TradingDataContractRead):
    import_run_id: int
    stock_code: str | None
    stock_name: str | None
    start_date: date
    end_date: date
    record_count: int
    reference_date_count: int
    missing_trade_date_count: int
    missing_trade_dates: list[date]
    invalid_ohlc_count: int
    non_positive_price_count: int
    non_positive_volume_count: int
    non_positive_amount_count: int | None
    flat_days_count: int
    coverage_ratio: float


class TradingIndicatorPointRead(BaseModel):
    trade_date: date
    close: float
    volume: float
    amount: float | None
    turnover: float | None
    daily_return: float | None
    log_return: float | None
    cumulative_return: float | None
    ma5: float | None
    ma10: float | None
    ma20: float | None
    ma60: float | None
    ema12: float | None
    ema26: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bias20: float | None
    rsi14: float | None
    roc20: float | None
    obv: float | None
    bollinger_mid: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    bandwidth: float | None
    atr14: float | None
    natr14: float | None
    hv20: float | None
    rvol20: float | None
    turnover_z20: float | None
    illiq20: float | None


class TradingIndicatorSeriesRead(TradingDataContractRead):
    import_run_id: int
    stock_code: str
    stock_name: str | None
    start_date: date
    end_date: date
    points: list[TradingIndicatorPointRead]
    notices: list[str] = Field(default_factory=list)


class TradingRiskMetricsRead(TradingDataContractRead):
    import_run_id: int
    stock_code: str
    stock_name: str | None
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
    beta60: float | None
    downside_volatility: float | None
    hv20: float | None
    rvol20: float | None
    turnover_z20: float | None
    illiq20: float | None
    notices: list[str] = Field(default_factory=list)


class TradingAnomalyRead(BaseModel):
    trade_date: date
    anomaly_type: str
    severity: str
    metric_value: float
    baseline_value: float | None
    threshold_value: float | None
    description: str


class TradingAnomalyReportRead(TradingDataContractRead):
    import_run_id: int
    stock_code: str
    stock_name: str | None
    start_date: date
    end_date: date
    anomalies: list[TradingAnomalyRead]


class TradingCrossSectionRowRead(BaseModel):
    stock_code: str
    stock_name: str | None
    start_date: date
    end_date: date
    record_count: int
    total_return: float | None
    volatility: float
    total_volume: float
    total_amount: float | None
    average_amplitude: float
    latest_close: float


class TradingCrossSectionRead(TradingDataContractRead):
    import_run_id: int
    metric: str
    start_date: date
    end_date: date
    rows: list[TradingCrossSectionRowRead]


class TradingCorrelationMatrixRead(TradingDataContractRead):
    import_run_id: int
    start_date: date
    end_date: date
    stock_codes: list[str]
    matrix: list[list[float | None]]


class TradingComparisonScopeRead(BaseModel):
    import_run_id: int
    stock_code: str | None
    stock_name: str | None
    requested_start_date: date | None
    requested_end_date: date | None
    actual_start_date: date
    actual_end_date: date
    record_count: int
    stock_count: int
    total_volume: float
    total_amount: float | None


class TradingStockOverlapRead(BaseModel):
    shared_stocks: list[str]
    base_only_stocks: list[str]
    target_only_stocks: list[str]


class TradingRecordOverlapRead(BaseModel):
    shared_trade_date_count: int
    shared_record_count: int
    base_only_record_count: int
    target_only_record_count: int


class TradingComparisonValueRead(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float | None


class TradingMismatchSummaryRead(BaseModel):
    matching_record_count: int
    mismatched_record_count: int
    open_mismatch_count: int
    high_mismatch_count: int
    low_mismatch_count: int
    close_mismatch_count: int
    volume_mismatch_count: int
    amount_mismatch_count: int


class TradingMismatchSampleRead(BaseModel):
    stock_code: str
    trade_date: date
    mismatched_fields: list[str]
    base_values: TradingComparisonValueRead
    target_values: TradingComparisonValueRead


class TradingScopeComparisonRead(TradingDataContractRead):
    base_scope: TradingComparisonScopeRead
    target_scope: TradingComparisonScopeRead
    stock_overlap: TradingStockOverlapRead
    record_overlap: TradingRecordOverlapRead
    mismatch_summary: TradingMismatchSummaryRead
    mismatch_samples: list[TradingMismatchSampleRead]


class TradingSnapshotRead(TradingDataContractRead):
    import_run_id: int
    stock_code: str
    stock_name: str | None
    valuation_as_of: datetime | None
    fundamental_report_date: date | None
    pe_ttm: float | None
    pb: float | None
    roe: float | None
    asset_liability_ratio: float | None
    revenue_yoy: float | None
    net_profit_yoy: float | None




