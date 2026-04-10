export type NumericLike = string | number | null;

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

export interface ImportRunRead {
  id: number;
  display_id: number;
  owner_user_id: number | null;
  owner_username: string | null;
  dataset_name: string;
  asset_class: string | null;
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
  active_datasets: number;
  monthly_imports: ImportMonthlyStatRead[];
  owner_summaries: ImportOwnerSummaryRead[];
}

export interface DeleteImportRunResponse {
  id: number;
  status: string;
}

export interface TradingInstrumentRead {
  instrument_code: string;
  instrument_name: string | null;
  first_trade_date: string | null;
  last_trade_date: string | null;
  record_count: number;
}

export interface TradingRecordRead {
  id: number;
  import_run_id: number;
  instrument_code: string;
  instrument_name: string | null;
  trade_date: string;
  open: NumericLike;
  high: NumericLike;
  low: NumericLike;
  close: NumericLike;
  volume: NumericLike;
  amount: NumericLike;
}

export interface TradingRangeMaxMatchRead {
  trade_date: string;
  series_index: number;
}

export interface TradingRangeMaxAmountRead {
  import_run_id: number;
  instrument_code: string;
  start_date: string;
  end_date: string;
  max_amount: NumericLike;
  matches: TradingRangeMaxMatchRead[];
}

export interface TradingRangeKthVolumeRead {
  import_run_id: number;
  instrument_code: string;
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
  instrument_code: string;
  instrument_name: string | null;
  trade_date: string;
  daily_return: NumericLike;
  return_z20: NumericLike;
  volume_ratio20: NumericLike;
  historical_dominated_count: number;
  historical_sample_count: number;
  joint_percentile: NumericLike;
  severity: string;
}

export interface TradingJointAnomalyRankingRead {
  import_run_id: number;
  lookback_window: number;
  rows: TradingJointAnomalyRowRead[];
}

export interface TradingSummaryRead {
  import_run_id: number;
  instrument_code: string | null;
  instrument_name: string | null;
  start_date: string;
  end_date: string;
  record_count: number;
  instrument_count: number;
  high_price: NumericLike;
  low_price: NumericLike;
  average_close: NumericLike;
  latest_close: NumericLike;
  total_volume: NumericLike;
  total_amount: NumericLike;
  average_volume: NumericLike;
  average_amplitude: NumericLike;
}

export interface TradingQualityReportRead {
  import_run_id: number;
  instrument_code: string | null;
  instrument_name: string | null;
  start_date: string;
  end_date: string;
  record_count: number;
  reference_date_count: number;
  missing_trade_date_count: number;
  missing_trade_dates: string[];
  invalid_ohlc_count: number;
  non_positive_price_count: number;
  non_positive_volume_count: number;
  non_positive_amount_count: number;
  flat_days_count: number;
  coverage_ratio: NumericLike;
}

export interface TradingIndicatorPointRead {
  trade_date: string;
  close: NumericLike;
  volume: NumericLike;
  amount: NumericLike;
  daily_return: NumericLike;
  cumulative_return: NumericLike;
  ma5: NumericLike;
  ma10: NumericLike;
  ma20: NumericLike;
  ema12: NumericLike;
  ema26: NumericLike;
  macd: NumericLike;
  macd_signal: NumericLike;
  macd_histogram: NumericLike;
  rsi14: NumericLike;
  bollinger_mid: NumericLike;
  bollinger_upper: NumericLike;
  bollinger_lower: NumericLike;
  atr14: NumericLike;
}

export interface TradingIndicatorSeriesRead {
  import_run_id: number;
  instrument_code: string;
  instrument_name: string | null;
  start_date: string;
  end_date: string;
  points: TradingIndicatorPointRead[];
}

export interface TradingRiskMetricsRead {
  import_run_id: number;
  instrument_code: string;
  instrument_name: string | null;
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

export interface TradingAnomalyReportRead {
  import_run_id: number;
  instrument_code: string;
  instrument_name: string | null;
  start_date: string;
  end_date: string;
  anomalies: TradingAnomalyRead[];
}

export interface TradingCrossSectionRowRead {
  instrument_code: string;
  instrument_name: string | null;
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

export interface TradingCrossSectionRead {
  import_run_id: number;
  metric: string;
  start_date: string;
  end_date: string;
  rows: TradingCrossSectionRowRead[];
}

export interface TradingCorrelationMatrixRead {
  import_run_id: number;
  start_date: string;
  end_date: string;
  instrument_codes: string[];
  matrix: Array<Array<number | null>>;
}

export interface TradingRunComparisonRead {
  base_run_id: number;
  target_run_id: number;
  base_record_count: number;
  target_record_count: number;
  base_instrument_count: number;
  target_instrument_count: number;
  base_total_volume: NumericLike;
  target_total_volume: NumericLike;
  base_total_amount: NumericLike;
  target_total_amount: NumericLike;
  base_start_date: string;
  base_end_date: string;
  target_start_date: string;
  target_end_date: string;
  shared_instruments: string[];
  added_instruments: string[];
  removed_instruments: string[];
}
