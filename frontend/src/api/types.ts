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
