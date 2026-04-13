import { getJson, postJson } from "@/api/http";
import type {
  AlgoIndexStatusRead,
  TradingRiskRadarCalendarRead,
  TradingRiskRadarEventContextRead,
  TradingRiskRadarEventListRead,
  TradingRiskRadarStockListRead,
  TradingRiskRadarOverviewRead,
} from "@/api/types";


export interface AlgoIndexParams {
  import_run_id: number;
}

export interface RiskRadarEventsParams extends AlgoIndexParams {
  start_date?: string;
  end_date?: string;
  stock_code?: string;
  severity?: string;
  top_n?: number;
}

export interface RiskRadarStockParams extends AlgoIndexParams {
  severity?: string;
  top_n?: number;
}

export interface RiskRadarCalendarParams extends AlgoIndexParams {
  start_date?: string;
  end_date?: string;
}

export interface RiskRadarEventContextParams extends AlgoIndexParams {
  stock_code: string;
  trade_date: string;
}

export function fetchAlgoIndexStatus(params: AlgoIndexParams) {
  return getJson<AlgoIndexStatusRead>("/api/algo/indexes/status", params);
}

export function rebuildAlgoIndex(importRunId: number) {
  return postJson<AlgoIndexStatusRead>(`/api/algo/indexes/rebuild?import_run_id=${importRunId}`);
}

export function fetchRiskRadarOverview(params: AlgoIndexParams) {
  return getJson<TradingRiskRadarOverviewRead>("/api/algo/risk-radar/overview", params);
}

export function fetchRiskRadarEvents(params: RiskRadarEventsParams) {
  return getJson<TradingRiskRadarEventListRead>("/api/algo/risk-radar/events", params);
}

export function fetchRiskRadarStocks(params: RiskRadarStockParams) {
  return getJson<TradingRiskRadarStockListRead>("/api/algo/risk-radar/stocks", params);
}

export function fetchRiskRadarCalendar(params: RiskRadarCalendarParams) {
  return getJson<TradingRiskRadarCalendarRead>("/api/algo/risk-radar/calendar", params);
}

export function fetchRiskRadarEventContext(params: RiskRadarEventContextParams) {
  return getJson<TradingRiskRadarEventContextRead>("/api/algo/risk-radar/event-context", params);
}


