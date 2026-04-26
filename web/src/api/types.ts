export type NumericLike = string | number | null;

export interface TradingDataContractRead {
  required_fields: string[];
  missing_fields: string[];
  data_frequency: string;
  evidence_refs: string[];
  benchmark_code: string | null;
  benchmark_source: string | null;
}

export interface HealthResponse {
  status: string;
  environment: string;
  database_ok: boolean;
  detail: string;
}

export interface UserRead {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthTokenRead {
  access_token: string;
  token_type: string;
  user: UserRead;
}

export interface AdminManagedUserRead {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  has_business_data: boolean;
}

export interface AdminManagedUserDeleteResponse {
  id: number;
  status: string;
}

export interface AuditLogRead {
  id: number;
  occurred_at: string;
  category: string;
  event_type: string;
  success: boolean;
  status_code: number | null;
  actor_user_id: number | null;
  actor_username_snapshot: string | null;
  actor_role: string | null;
  target_type: string | null;
  target_label: string | null;
  import_run_id: number | null;
  request_path: string | null;
  http_method: string | null;
  ip_address: string | null;
  user_agent: string | null;
  detail_json: Record<string, unknown>;
}

export interface AuditLogCategoryStatRead {
  category: string;
  total: number;
}

export interface AuditLogStatsRead {
  total_events: number;
  success_events: number;
  failed_events: number;
  unique_actor_count: number;
  today_events: number;
  category_breakdown: AuditLogCategoryStatRead[];
}

export interface AuditLogListRead {
  total: number;
  page: number;
  page_size: number;
  rows: AuditLogRead[];
}

export interface AdminRunMonitorRowRead {
  import_run_id: number;
  display_id: number;
  dataset_name: string;
  owner_user_id: number | null;
  owner_username: string | null;
  run_status: string;
  started_at: string;
  completed_at: string | null;
  record_count: number | null;
  algo_index_status: string;
  algo_index_ready: boolean;
  algo_build_duration_ms: number | null;
  algo_last_error: string | null;
}

export interface AdminRunMonitorRead {
  total_runs: number;
  ready_indexes: number;
  pending_indexes: number;
  failed_indexes: number;
  rows: AdminRunMonitorRowRead[];
}

export interface AdminAssetSummaryRead {
  owner_count: number;
  unique_stock_count: number;
  largest_dataset_records: number;
  median_dataset_records: number;
  first_trade_date: string | null;
  last_trade_date: string | null;
  latest_imported_at: string | null;
}

export interface AdminAssetGrowthPointRead {
  month: string;
  cumulative_datasets: number;
  cumulative_records: number;
}

export interface AdminAssetDailyGrowthPointRead {
  day: string;
  cumulative_datasets: number;
  cumulative_records: number;
}

export interface AdminAssetSizeBucketRead {
  bucket_label: string;
  dataset_count: number;
  record_count: number;
}

export interface AdminAssetOwnerRowRead {
  owner_user_id: number;
  owner_username: string | null;
  dataset_count: number;
  record_count: number;
  record_share_ratio: number;
  avg_records_per_dataset: number;
  latest_completed_at: string | null;
}

export interface AdminAssetTopDatasetRead {
  run_id: number;
  display_id: number;
  dataset_name: string;
  owner_username: string | null;
  record_count: number;
  completed_at: string | null;
}

export interface AdminAssetOverviewRead {
  summary: AdminAssetSummaryRead;
  growth: AdminAssetGrowthPointRead[];
  growth_daily: AdminAssetDailyGrowthPointRead[];
  size_buckets: AdminAssetSizeBucketRead[];
  owner_rows: AdminAssetOwnerRowRead[];
  top_datasets: AdminAssetTopDatasetRead[];
}

export interface ImportRunRead {
  id: number;
  display_id: number;
  owner_user_id: number | null;
  owner_username: string | null;
  dataset_name: string;
  source_type: string;
  source_name: string;
  original_file_name: string | null;
  file_format: string | null;
  status: string;
  started_at: string;
  completed_at: string | null;
  record_count: number | null;
  error_message: string | null;
  deleted_at: string | null;
}

export interface ImportMonthlyStatRead {
  month: string;
  runs: number;
  records: number;
}

export interface ImportOwnerSummaryRead {
  owner_user_id: number;
  owner_username: string | null;
  runs: number;
  records: number;
}

export interface ImportStatsRead {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  total_records: number;
  available_datasets: number;
  monthly_imports: ImportMonthlyStatRead[];
  owner_summaries: ImportOwnerSummaryRead[];
}

export interface DeleteImportRunResponse {
  id: number;
  status: string;
}

export interface ImportMappingCandidateRead {
  original_column: string;
  header_score: number;
  value_score: number;
  template_bonus: number;
  total_score: number;
  confidence: string;
  reasons: string[];
}

export interface ImportFieldSuggestionRead {
  canonical_column: string;
  required: boolean;
  selected_original_column: string | null;
  selected_score: number | null;
  selected_confidence: string;
  candidates: ImportMappingCandidateRead[];
}

export interface ImportMappingConflictRead {
  canonical_column: string;
  primary_original_column: string;
  secondary_original_column: string;
  gap: number;
  message: string;
}

export interface ImportPreviewRead {
  preview_id: string;
  expires_at: string;
  can_auto_commit: boolean;
  required_confirmation_needed: boolean;
  required_issue_columns: string[];
  matcher_engine: string;
  required_columns: string[];
  optional_columns: string[];
  original_columns: string[];
  ignored_columns: string[];
  suggested_mapping: Record<string, string>;
  missing_required: string[];
  conflicts: ImportMappingConflictRead[];
  field_suggestions: ImportFieldSuggestionRead[];
  action_hints: string[];
}

export interface TradingStockRead {
  stock_code: string;
  stock_name: string | null;
  first_trade_date: string | null;
  last_trade_date: string | null;
  record_count: number;
}

export interface TradingRecordRead {
  id: number;
  import_run_id: number;
  stock_code: string;
  stock_name: string | null;
  trade_date: string;
  open: NumericLike;
  high: NumericLike;
  low: NumericLike;
  close: NumericLike;
  volume: NumericLike;
  amount: NumericLike;
  turnover: NumericLike;
  benchmark_close: NumericLike;
  pe_ttm: NumericLike;
  pb: NumericLike;
  roe: NumericLike;
  asset_liability_ratio: NumericLike;
  revenue_yoy: NumericLike;
  net_profit_yoy: NumericLike;
  valuation_as_of: string | null;
  fundamental_report_date: string | null;
}

export interface TradingRangeMaxMatchRead {
  trade_date: string;
  series_index: number;
}

export interface TradingRangeMaxAmountRead {
  import_run_id: number;
  stock_code: string;
  start_date: string;
  end_date: string;
  max_amount: NumericLike;
  matches: TradingRangeMaxMatchRead[];
}

export interface TradingRangeKthVolumeRead {
  import_run_id: number;
  stock_code: string;
  start_date: string;
  end_date: string;
  k: number;
  value: NumericLike;
  method: string;
  is_approx: boolean;
  approximation_note: string | null;
  matches: TradingRangeMaxMatchRead[];
}

export interface TradingJointAnomalyRowRead {
  stock_code: string;
  stock_name: string | null;
  trade_date: string;
  daily_return: NumericLike;
  return_z20: NumericLike;
  volume_ratio20: NumericLike;
  historical_dominated_count: number;
  historical_sample_count: number;
  joint_percentile: NumericLike;
  severity: string;
}

export interface TradingJointAnomalyRankingRead extends TradingDataContractRead {
  import_run_id: number;
  lookback_window: number;
  rows: TradingJointAnomalyRowRead[];
}

export interface AlgoIndexStatusRead {
  import_run_id: number;
  status: string;
  is_ready: boolean;
  build_started_at: string | null;
  build_completed_at: string | null;
  build_duration_ms: number | null;
  stock_count: number | null;
  event_count: number | null;
  reuse_count: number;
  last_error: string | null;
}

export interface TradingRiskRadarEventRead {
  stock_code: string;
  stock_name: string | null;
  trade_date: string;
  daily_return: NumericLike;
  return_z20: NumericLike;
  volume_ratio20: NumericLike;
  amplitude_ratio20: NumericLike;
  return_shock: NumericLike;
  vol_regime: NumericLike;
  range_shock: NumericLike;
  rvol20: NumericLike;
  liquidity_shock: NumericLike;
  drawdown_pressure: NumericLike;
  score_return_shock: NumericLike;
  score_vol_regime: NumericLike;
  score_range_shock: NumericLike;
  score_rvol20: NumericLike;
  score_liquidity_shock: NumericLike;
  score_drawdown_pressure: NumericLike;
  historical_dominated_count: number;
  historical_sample_count: number;
  joint_percentile: NumericLike;
  severity: string;
  cause_label: string;
}

export interface TradingStockRiskProfileRead {
  stock_code: string;
  stock_name: string | null;
  event_count: number;
  medium_count: number;
  high_count: number;
  critical_count: number;
  max_joint_percentile: NumericLike;
  avg_joint_percentile: NumericLike;
  latest_event_date: string;
  top_event_date: string;
  top_event_severity: string;
}

export interface TradingRiskRadarCalendarDayRead {
  trade_date: string;
  event_count: number;
  impacted_stock_count: number;
  medium_count: number;
  high_count: number;
  critical_count: number;
  max_joint_percentile: NumericLike;
}

export interface TradingRiskRadarOverviewRead extends TradingDataContractRead {
  import_run_id: number;
  lookback_window: number;
  generated_at: string | null;
  total_events: number;
  impacted_stock_count: number;
  medium_count: number;
  high_count: number;
  critical_count: number;
  top_stocks: TradingStockRiskProfileRead[];
  busiest_dates: TradingRiskRadarCalendarDayRead[];
}

export interface TradingRiskRadarEventListRead extends TradingDataContractRead {
  import_run_id: number;
  rows: TradingRiskRadarEventRead[];
}

export interface TradingRiskRadarStockListRead extends TradingDataContractRead {
  import_run_id: number;
  rows: TradingStockRiskProfileRead[];
}

export interface TradingRiskRadarCalendarRead extends TradingDataContractRead {
  import_run_id: number;
  rows: TradingRiskRadarCalendarDayRead[];
}

export interface TradingRiskRadarWindowRead {
  window_days: number;
  current_value: NumericLike;
  exact_percentile: NumericLike;
  p50: NumericLike;
  p90: NumericLike;
  p95: NumericLike;
  top_1: NumericLike;
  top_3: NumericLike;
}

export interface TradingRiskRadarWindowGroupRead {
  metric: string;
  label: string;
  windows: TradingRiskRadarWindowRead[];
}

export interface TradingRiskRadarDistributionChangeRead {
  metric: string;
  window_days: number;
  before_median: NumericLike;
  before_p90: NumericLike;
  before_p95: NumericLike;
  after_median: NumericLike;
  after_p90: NumericLike;
  after_p95: NumericLike;
}

export interface TradingRiskRadarAmountPeakRead {
  start_date: string;
  end_date: string;
  peak_amount: NumericLike;
  peak_dates: TradingRangeMaxMatchRead[];
}

export interface TradingRiskRadarEventContextRead extends TradingDataContractRead {
  import_run_id: number;
  event: TradingRiskRadarEventRead;
  window_groups: TradingRiskRadarWindowGroupRead[];
  distribution_changes: TradingRiskRadarDistributionChangeRead[];
  local_amount_peak: TradingRiskRadarAmountPeakRead | null;
}

export interface TradingSummaryRead extends TradingDataContractRead {
  import_run_id: number;
  stock_code: string | null;
  stock_name: string | null;
  start_date: string;
  end_date: string;
  record_count: number;
  stock_count: number;
  high_price: NumericLike;
  low_price: NumericLike;
  average_close: NumericLike;
  latest_close: NumericLike;
  total_volume: NumericLike;
  total_amount: NumericLike;
  average_volume: NumericLike;
  average_amplitude: NumericLike;
}

export interface TradingQualityReportRead extends TradingDataContractRead {
  import_run_id: number;
  stock_code: string | null;
  stock_name: string | null;
  start_date: string;
  end_date: string;
  record_count: number;
  reference_date_count: number;
  missing_trade_date_count: number;
  missing_trade_dates: string[];
  invalid_ohlc_count: number;
  non_positive_price_count: number;
  non_positive_volume_count: number;
  non_positive_amount_count: number | null;
  flat_days_count: number;
  coverage_ratio: NumericLike;
}

export interface TradingIndicatorPointRead {
  trade_date: string;
  close: NumericLike;
  volume: NumericLike;
  amount: NumericLike;
  turnover: NumericLike;
  daily_return: NumericLike;
  log_return: NumericLike;
  cumulative_return: NumericLike;
  ma5: NumericLike;
  ma10: NumericLike;
  ma20: NumericLike;
  ma60: NumericLike;
  ema12: NumericLike;
  ema26: NumericLike;
  macd: NumericLike;
  macd_signal: NumericLike;
  macd_histogram: NumericLike;
  bias20: NumericLike;
  rsi14: NumericLike;
  roc20: NumericLike;
  obv: NumericLike;
  bollinger_mid: NumericLike;
  bollinger_upper: NumericLike;
  bollinger_lower: NumericLike;
  bandwidth: NumericLike;
  atr14: NumericLike;
  natr14: NumericLike;
  hv20: NumericLike;
  rvol20: NumericLike;
  turnover_z20: NumericLike;
  illiq20: NumericLike;
}

export interface TradingIndicatorSeriesRead extends TradingDataContractRead {
  import_run_id: number;
  stock_code: string;
  stock_name: string | null;
  start_date: string;
  end_date: string;
  points: TradingIndicatorPointRead[];
  notices: string[];
}

export interface TradingRiskMetricsRead extends TradingDataContractRead {
  import_run_id: number;
  stock_code: string;
  stock_name: string | null;
  start_date: string;
  end_date: string;
  record_count: number;
  interval_return: NumericLike;
  volatility: NumericLike;
  max_drawdown: NumericLike;
  max_drawdown_duration: number;
  up_day_ratio: NumericLike;
  average_amplitude: NumericLike;
  max_daily_gain: NumericLike;
  max_daily_loss: NumericLike;
  beta60: NumericLike;
  downside_volatility: NumericLike;
  hv20: NumericLike;
  rvol20: NumericLike;
  turnover_z20: NumericLike;
  illiq20: NumericLike;
  notices: string[];
}

export interface TradingAnomalyRead {
  trade_date: string;
  anomaly_type: string;
  severity: string;
  metric_value: NumericLike;
  baseline_value: NumericLike;
  threshold_value: NumericLike;
  description: string;
}

export interface TradingAnomalyReportRead extends TradingDataContractRead {
  import_run_id: number;
  stock_code: string;
  stock_name: string | null;
  start_date: string;
  end_date: string;
  anomalies: TradingAnomalyRead[];
}

export interface TradingCrossSectionRowRead {
  stock_code: string;
  stock_name: string | null;
  start_date: string;
  end_date: string;
  record_count: number;
  total_return: NumericLike;
  volatility: NumericLike;
  total_volume: NumericLike;
  total_amount: NumericLike;
  average_amplitude: NumericLike;
  latest_close: NumericLike;
}

export interface TradingCrossSectionRead extends TradingDataContractRead {
  import_run_id: number;
  metric: string;
  start_date: string;
  end_date: string;
  rows: TradingCrossSectionRowRead[];
}

export interface TradingCorrelationMatrixRead extends TradingDataContractRead {
  import_run_id: number;
  start_date: string;
  end_date: string;
  stock_codes: string[];
  matrix: Array<Array<number | null>>;
}

export interface TradingComparisonScopeRead {
  import_run_id: number;
  stock_code: string | null;
  stock_name: string | null;
  requested_start_date: string | null;
  requested_end_date: string | null;
  actual_start_date: string;
  actual_end_date: string;
  record_count: number;
  stock_count: number;
  total_volume: NumericLike;
  total_amount: NumericLike;
}

export interface TradingStockOverlapRead {
  shared_stocks: string[];
  base_only_stocks: string[];
  target_only_stocks: string[];
}

export interface TradingRecordOverlapRead {
  shared_trade_date_count: number;
  shared_record_count: number;
  base_only_record_count: number;
  target_only_record_count: number;
}

export interface TradingComparisonValueRead {
  open: NumericLike;
  high: NumericLike;
  low: NumericLike;
  close: NumericLike;
  volume: NumericLike;
  amount: NumericLike;
}

export interface TradingMismatchSummaryRead {
  matching_record_count: number;
  mismatched_record_count: number;
  open_mismatch_count: number;
  high_mismatch_count: number;
  low_mismatch_count: number;
  close_mismatch_count: number;
  volume_mismatch_count: number;
  amount_mismatch_count: number;
}

export interface TradingMismatchSampleRead {
  stock_code: string;
  trade_date: string;
  mismatched_fields: string[];
  base_values: TradingComparisonValueRead;
  target_values: TradingComparisonValueRead;
}

export interface TradingScopeComparisonRead extends TradingDataContractRead {
  base_scope: TradingComparisonScopeRead;
  target_scope: TradingComparisonScopeRead;
  stock_overlap: TradingStockOverlapRead;
  record_overlap: TradingRecordOverlapRead;
  mismatch_summary: TradingMismatchSummaryRead;
  mismatch_samples: TradingMismatchSampleRead[];
}

export interface TradingSnapshotRead extends TradingDataContractRead {
  import_run_id: number;
  stock_code: string;
  stock_name: string | null;
  valuation_as_of: string | null;
  fundamental_report_date: string | null;
  pe_ttm: NumericLike;
  pb: NumericLike;
  roe: NumericLike;
  asset_liability_ratio: NumericLike;
  revenue_yoy: NumericLike;
  net_profit_yoy: NumericLike;
}



