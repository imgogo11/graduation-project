import { getJson } from "@/api/http";
import type {
  TradingAnomalyReportRead,
  TradingCorrelationMatrixRead,
  TradingCrossSectionRead,
  TradingIndicatorSeriesRead,
  TradingJointAnomalyRankingRead,
  TradingQualityReportRead,
  TradingRiskMetricsRead,
  TradingRunComparisonRead,
  TradingSummaryRead,
} from "@/api/types";


export interface AnalysisScopeParams {
  import_run_id: number;
  instrument_code?: string;
  start_date?: string;
  end_date?: string;
}

export interface CrossSectionParams {
  import_run_id: number;
  start_date?: string;
  end_date?: string;
  metric?: string;
  top_n?: number;
}

export interface CorrelationParams {
  import_run_id: number;
  start_date?: string;
  end_date?: string;
  instrument_codes?: string;
}

export interface CompareRunsParams {
  base_run_id: number;
  target_run_id: number;
}

export interface JointAnomalyRankingParams {
  import_run_id: number;
  start_date?: string;
  end_date?: string;
  top_n?: number;
}

export function fetchTradingSummary(params: AnalysisScopeParams) {
  return getJson<TradingSummaryRead>("/api/trading/analysis/summary", params);
}

export function fetchTradingQuality(params: AnalysisScopeParams) {
  return getJson<TradingQualityReportRead>("/api/trading/analysis/quality", params);
}

export function fetchTradingIndicators(params: AnalysisScopeParams & { instrument_code: string }) {
  return getJson<TradingIndicatorSeriesRead>("/api/trading/analysis/indicators", params);
}

export function fetchTradingRisk(params: AnalysisScopeParams & { instrument_code: string }) {
  return getJson<TradingRiskMetricsRead>("/api/trading/analysis/risk", params);
}

export function fetchTradingAnomalies(params: AnalysisScopeParams & { instrument_code: string }) {
  return getJson<TradingAnomalyReportRead>("/api/trading/analysis/anomalies", params);
}

export function fetchTradingJointAnomalyRanking(params: JointAnomalyRankingParams) {
  return getJson<TradingJointAnomalyRankingRead>("/api/algo/trading/joint-anomaly-ranking", params);
}

export function fetchTradingCrossSection(params: CrossSectionParams) {
  return getJson<TradingCrossSectionRead>("/api/trading/analysis/cross-section", params);
}

export function fetchTradingCorrelation(params: CorrelationParams) {
  return getJson<TradingCorrelationMatrixRead>("/api/trading/analysis/correlation", params);
}

export function fetchTradingRunComparison(params: CompareRunsParams) {
  return getJson<TradingRunComparisonRead>("/api/trading/analysis/compare-runs", params);
}
