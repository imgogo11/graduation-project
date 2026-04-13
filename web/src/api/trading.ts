import { getJson } from "@/api/http";
import type {
  TradingStockRead,
  TradingRangeKthVolumeRead,
  TradingRangeMaxAmountRead,
  TradingRecordRead,
} from "@/api/types";


export interface ListTradingRecordsParams {
  import_run_id: number;
  stock_code?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export interface RangeMaxAmountParams {
  import_run_id: number;
  stock_code: string;
  start_date: string;
  end_date: string;
}

export interface RangeKthVolumeParams {
  import_run_id: number;
  stock_code: string;
  start_date: string;
  end_date: string;
  k: number;
  method?: "persistent_segment_tree" | "t_digest";
}

export function fetchTradingStocks(importRunId: number) {
  return getJson<TradingStockRead[]>("/api/trading/stocks", {
    import_run_id: importRunId,
  });
}

export function fetchTradingRecords(params: ListTradingRecordsParams) {
  return getJson<TradingRecordRead[]>("/api/trading/records", params);
}

export function fetchTradingRangeMaxAmount(params: RangeMaxAmountParams) {
  return getJson<TradingRangeMaxAmountRead>("/api/algo/trading/range-max-amount", params);
}

export function fetchTradingRangeKthVolume(params: RangeKthVolumeParams) {
  return getJson<TradingRangeKthVolumeRead>("/api/algo/trading/range-kth-volume", params);
}


