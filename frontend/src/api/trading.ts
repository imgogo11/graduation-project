import { getJson } from "@/api/http";
import type {
  TradingInstrumentRead,
  TradingRangeMaxAmountRead,
  TradingRecordRead,
} from "@/api/types";


export interface ListTradingRecordsParams {
  import_run_id: number;
  instrument_code?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export interface RangeMaxAmountParams {
  import_run_id: number;
  instrument_code: string;
  start_date: string;
  end_date: string;
}

export function fetchTradingInstruments(importRunId: number) {
  return getJson<TradingInstrumentRead[]>("/api/trading/instruments", {
    import_run_id: importRunId,
  });
}

export function fetchTradingRecords(params: ListTradingRecordsParams) {
  return getJson<TradingRecordRead[]>("/api/trading/records", params);
}

export function fetchTradingRangeMaxAmount(params: RangeMaxAmountParams) {
  return getJson<TradingRangeMaxAmountRead>("/api/algo/trading/range-max-amount", params);
}
