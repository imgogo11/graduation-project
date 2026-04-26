# -*- coding: utf-8 -*-
"""
Fetch a complete one-table dataset for a single A-share stock using AkShare.

The script tries to collect the following fields into one CSV:
- stock daily fields
- benchmark index fields
- trading calendar field
- valuation fields
- fundamental fields

Notes
- The script uses real AkShare calls only.
- If a primary interface fails, it tries a real fallback interface.
- If some fields are still unavailable after retries, it writes a JSON report
  and a text file describing feasible alternative solutions.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import akshare as ak
import pandas as pd

DEFAULT_OUTPUT_DIR = Path(r"D:\graduation-project\data\row")
DEFAULT_START_DATE = "20240101"
DEFAULT_BENCHMARK_CODE = "sh000300"


@dataclass
class FetchContext:
    stock_source: Optional[str] = None
    benchmark_source: Optional[str] = None
    calendar_source: Optional[str] = None
    valuation_source: Optional[str] = None
    fundamental_source: Optional[str] = None
    field_sources: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}")


def normalize_stock_code(raw_value: Any) -> str:
    text = str(raw_value).strip()
    match = re.search(r"(\d{6})", text)
    if not match:
        raise ValueError(f"Invalid stock code: {raw_value}")
    return match.group(1)


def to_xq_symbol(stock_code: str) -> str:
    if stock_code.startswith(("5", "6", "9")):
        return f"SH{stock_code}"
    return f"SZ{stock_code}"


def to_sina_symbol(stock_code: str) -> str:
    if stock_code.startswith(("5", "6", "9")):
        return f"sh{stock_code}"
    return f"sz{stock_code}"


def safe_call(
    api_name: str,
    retries: int = 3,
    sleep_seconds: float = 0.8,
    **kwargs: Any,
) -> Optional[pd.DataFrame]:
    api_func = getattr(ak, api_name, None)
    if api_func is None:
        return None

    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            result = api_func(**kwargs)
            if isinstance(result, pd.DataFrame):
                return result
            return None
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)

    raise RuntimeError(f"{api_name} failed after retries: {last_error}")


def parse_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "false"}:
        return None

    multiplier = 1.0
    if text.endswith("%"):
        text = text[:-1]
    elif text.endswith("亿"):
        text = text[:-1]
        multiplier = 1e8
    elif text.endswith("万"):
        text = text[:-1]
        multiplier = 1e4

    text = text.replace(",", "")
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def series_from_item_value(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty or len(df.columns) < 2:
        return {}
    key_col = df.columns[0]
    value_col = df.columns[1]
    return {str(row[key_col]).strip(): row[value_col] for _, row in df.iterrows()}


def fetch_calendar(start_date: str, end_date: str, ctx: FetchContext) -> pd.DataFrame:
    calendar_df = safe_call("tool_trade_date_hist_sina")
    if calendar_df is None or calendar_df.empty:
        raise RuntimeError("Unable to fetch trading calendar from tool_trade_date_hist_sina")

    ctx.calendar_source = "tool_trade_date_hist_sina"
    calendar_df = calendar_df.rename(columns={calendar_df.columns[0]: "calendar_trade_date"}).copy()
    calendar_df["calendar_trade_date"] = pd.to_datetime(calendar_df["calendar_trade_date"], errors="coerce")
    calendar_df = calendar_df[calendar_df["calendar_trade_date"].notna()].copy()

    start_dt = pd.to_datetime(start_date, format="%Y%m%d")
    end_dt = pd.to_datetime(end_date, format="%Y%m%d")
    calendar_df = calendar_df[
        (calendar_df["calendar_trade_date"] >= start_dt)
        & (calendar_df["calendar_trade_date"] <= end_dt)
    ].copy()
    calendar_df.sort_values("calendar_trade_date", inplace=True)
    calendar_df.reset_index(drop=True, inplace=True)

    ctx.field_sources["calendar_trade_date"] = ctx.calendar_source
    return calendar_df


def fetch_stock_name(stock_code: str, ctx: FetchContext) -> Optional[str]:
    try:
        code_name_df = safe_call("stock_info_a_code_name")
        if code_name_df is not None and not code_name_df.empty:
            matched = code_name_df[code_name_df["code"].astype(str) == stock_code]
            if not matched.empty:
                ctx.field_sources["stock_name"] = "stock_info_a_code_name"
                return str(matched.iloc[0]["name"]).strip()
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_info_a_code_name failed for stock_name: {exc}")

    try:
        profile_df = safe_call("stock_profile_cninfo", symbol=stock_code)
        if profile_df is not None and not profile_df.empty:
            name_col = "A股简称" if "A股简称" in profile_df.columns else profile_df.columns[4]
            ctx.field_sources["stock_name"] = "stock_profile_cninfo"
            return str(profile_df.iloc[0][name_col]).strip()
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_profile_cninfo failed for stock_name: {exc}")

    return None


def fetch_stock_daily(stock_code: str, start_date: str, end_date: str, adjust: str, ctx: FetchContext) -> pd.DataFrame:
    used_adjust = "" if adjust == "none" else adjust

    try:
        hist_df = safe_call(
            "stock_zh_a_hist",
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=used_adjust,
        )
        if hist_df is not None and not hist_df.empty:
            renamed = hist_df.rename(
                columns={
                    "日期": "trade_date",
                    "股票代码": "stock_code",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                    "成交额": "amount",
                    "换手率": "turnover_rate",
                }
            ).copy()
            renamed["trade_date"] = pd.to_datetime(renamed["trade_date"], errors="coerce")
            renamed["stock_code"] = renamed["stock_code"].astype(str).map(normalize_stock_code)
            renamed["volume"] = pd.to_numeric(renamed["volume"], errors="coerce") * 100.0
            for col in ["open", "high", "low", "close", "amount", "turnover_rate"]:
                renamed[col] = pd.to_numeric(renamed[col], errors="coerce")
            renamed["adjust_type"] = adjust
            renamed["data_source"] = "stock_zh_a_hist"

            ctx.stock_source = "stock_zh_a_hist"
            for field_name in [
                "stock_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "turnover_rate",
                "adjust_type",
                "data_source",
            ]:
                ctx.field_sources[field_name] = ctx.stock_source
            return renamed[
                [
                    "stock_code",
                    "trade_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "amount",
                    "turnover_rate",
                    "adjust_type",
                    "data_source",
                ]
            ]
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_zh_a_hist unavailable, fallback to stock_zh_a_daily: {exc}")

    daily_df = safe_call(
        "stock_zh_a_daily",
        symbol=to_sina_symbol(stock_code),
        start_date=start_date,
        end_date=end_date,
    )
    if daily_df is None or daily_df.empty:
        raise RuntimeError("Unable to fetch stock daily data from both stock_zh_a_hist and stock_zh_a_daily")

    daily_df = daily_df.copy()
    daily_df["trade_date"] = pd.to_datetime(daily_df["date"], errors="coerce")
    daily_df["stock_code"] = stock_code
    for col in ["open", "high", "low", "close", "volume", "amount", "turnover"]:
        if col in daily_df.columns:
            daily_df[col] = pd.to_numeric(daily_df[col], errors="coerce")
    daily_df["turnover_rate"] = daily_df["turnover"] * 100.0
    daily_df["adjust_type"] = "none"
    daily_df["data_source"] = "stock_zh_a_daily"

    ctx.stock_source = "stock_zh_a_daily"
    if adjust != "none":
        ctx.warnings.append("Adjusted daily series was requested, but fallback source stock_zh_a_daily only provides non-adjusted prices.")
        ctx.alternatives.append(
            "If adjusted prices are mandatory, run the script in a network environment where stock_zh_a_hist is reachable, "
            "or fetch adjusted OHLC from an alternative provider and keep AkShare for the rest of the fields."
        )

    for field_name in [
        "stock_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover_rate",
        "adjust_type",
        "data_source",
    ]:
        ctx.field_sources[field_name] = ctx.stock_source

    return daily_df[
        [
            "stock_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "turnover_rate",
            "adjust_type",
            "data_source",
        ]
    ]


def fetch_benchmark_info(benchmark_code: str, ctx: FetchContext) -> tuple[str, pd.DataFrame]:
    benchmark_name = benchmark_code

    try:
        spot_df = safe_call("stock_zh_index_spot_sina")
        if spot_df is not None and not spot_df.empty:
            code_col = spot_df.columns[0]
            name_col = spot_df.columns[1]
            matched = spot_df[spot_df[code_col].astype(str) == benchmark_code]
            if not matched.empty:
                benchmark_name = str(matched.iloc[0][name_col]).strip()
                ctx.field_sources["benchmark_name"] = "stock_zh_index_spot_sina"
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_zh_index_spot_sina failed for benchmark_name: {exc}")

    try:
        benchmark_df = safe_call("stock_zh_index_daily_em", symbol=benchmark_code)
        if benchmark_df is not None and not benchmark_df.empty:
            renamed = benchmark_df.rename(
                columns={
                    "date": "benchmark_trade_date",
                    "日期": "benchmark_trade_date",
                    "close": "benchmark_close",
                    "收盘": "benchmark_close",
                }
            ).copy()
            renamed["benchmark_trade_date"] = pd.to_datetime(renamed["benchmark_trade_date"], errors="coerce")
            renamed["benchmark_code"] = benchmark_code
            renamed["benchmark_name"] = benchmark_name
            renamed["benchmark_close"] = pd.to_numeric(renamed["benchmark_close"], errors="coerce")

            ctx.benchmark_source = "stock_zh_index_daily_em"
            ctx.field_sources["benchmark_code"] = ctx.benchmark_source
            ctx.field_sources["benchmark_trade_date"] = ctx.benchmark_source
            ctx.field_sources["benchmark_close"] = ctx.benchmark_source
            return benchmark_name, renamed[["benchmark_code", "benchmark_name", "benchmark_trade_date", "benchmark_close"]]
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_zh_index_daily_em unavailable, fallback to stock_zh_index_daily: {exc}")

    benchmark_df = safe_call("stock_zh_index_daily", symbol=benchmark_code)
    if benchmark_df is None or benchmark_df.empty:
        raise RuntimeError("Unable to fetch benchmark data from stock_zh_index_daily_em or stock_zh_index_daily")

    benchmark_df = benchmark_df.copy()
    benchmark_df["benchmark_trade_date"] = pd.to_datetime(benchmark_df["date"], errors="coerce")
    benchmark_df["benchmark_close"] = pd.to_numeric(benchmark_df["close"], errors="coerce")
    benchmark_df["benchmark_code"] = benchmark_code
    benchmark_df["benchmark_name"] = benchmark_name

    ctx.benchmark_source = "stock_zh_index_daily"
    ctx.field_sources["benchmark_code"] = ctx.benchmark_source
    ctx.field_sources["benchmark_trade_date"] = ctx.benchmark_source
    ctx.field_sources["benchmark_close"] = ctx.benchmark_source
    return benchmark_name, benchmark_df[["benchmark_code", "benchmark_name", "benchmark_trade_date", "benchmark_close"]]


def fetch_valuation(stock_code: str, ctx: FetchContext) -> dict[str, Any]:
    valuation: dict[str, Any] = {
        "stock_name": None,
        "pe_ttm": None,
        "pb": None,
        "total_market_value": None,
        "circulating_market_value": None,
        "valuation_as_of": None,
    }

    try:
        xq_df = safe_call("stock_individual_spot_xq", symbol=to_xq_symbol(stock_code))
        if xq_df is not None and not xq_df.empty:
            item_map = series_from_item_value(xq_df)
            latest_price = parse_numeric(item_map.get("现价"))
            total_shares = parse_numeric(item_map.get("基金份额/总股本"))
            float_shares = parse_numeric(item_map.get("流通股"))
            explicit_total_mv = parse_numeric(item_map.get("资产净值/总市值"))
            explicit_float_mv = parse_numeric(item_map.get("流通值"))

            valuation["stock_name"] = item_map.get("名称")
            valuation["pe_ttm"] = parse_numeric(item_map.get("市盈率(TTM)"))
            if valuation["pe_ttm"] is None:
                valuation["pe_ttm"] = parse_numeric(item_map.get("市盈率(动)"))
            valuation["pb"] = parse_numeric(item_map.get("市净率"))
            valuation["total_market_value"] = (
                latest_price * total_shares if latest_price is not None and total_shares is not None else explicit_total_mv
            )
            valuation["circulating_market_value"] = (
                latest_price * float_shares if latest_price is not None and float_shares is not None else explicit_float_mv
            )
            valuation["valuation_as_of"] = item_map.get("时间")

            ctx.valuation_source = "stock_individual_spot_xq"
            for field_name in ["pe_ttm", "pb", "total_market_value", "circulating_market_value"]:
                ctx.field_sources[field_name] = ctx.valuation_source
            if valuation["stock_name"]:
                ctx.field_sources["stock_name"] = ctx.valuation_source
            return valuation
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_individual_spot_xq failed: {exc}")

    try:
        em_df = safe_call("stock_individual_info_em", symbol=stock_code)
        if em_df is not None and not em_df.empty:
            item_map = series_from_item_value(em_df)
            valuation["stock_name"] = item_map.get("股票简称")
            valuation["pe_ttm"] = parse_numeric(item_map.get("市盈率动态"))
            valuation["pb"] = parse_numeric(item_map.get("市净率"))
            valuation["total_market_value"] = parse_numeric(item_map.get("总市值"))
            valuation["circulating_market_value"] = parse_numeric(item_map.get("流通市值"))

            ctx.valuation_source = "stock_individual_info_em"
            for field_name in ["pe_ttm", "pb", "total_market_value", "circulating_market_value"]:
                ctx.field_sources[field_name] = ctx.valuation_source
            if valuation["stock_name"]:
                ctx.field_sources["stock_name"] = ctx.valuation_source
            return valuation
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_individual_info_em failed: {exc}")

    ctx.errors.append("Unable to fetch valuation fields from AkShare in the current network environment.")
    ctx.alternatives.append(
        "For valuation fields, the most stable real fallback is to keep stock_individual_spot_xq in use. "
        "If that endpoint also becomes unavailable, export the latest quote/valuation snapshot from a local browser session "
        "or another market data provider, then join it with the AkShare daily/history data by stock_code."
    )
    return valuation


def fetch_fundamentals(stock_code: str, ctx: FetchContext) -> dict[str, Any]:
    fundamentals: dict[str, Any] = {
        "roe": None,
        "asset_liability_ratio": None,
        "revenue_yoy": None,
        "net_profit_yoy": None,
        "fundamental_report_date": None,
    }

    try:
        ths_df = safe_call("stock_financial_abstract_ths", symbol=stock_code)
        if ths_df is not None and not ths_df.empty:
            date_col = ths_df.columns[0]
            latest_idx = pd.to_datetime(ths_df[date_col], errors="coerce").idxmax()
            latest_row = ths_df.loc[latest_idx]

            fundamentals["fundamental_report_date"] = latest_row[date_col]
            fundamentals["roe"] = parse_numeric(latest_row.get("净资产收益率")) or parse_numeric(latest_row.get("净资产收益率-摊薄"))
            fundamentals["asset_liability_ratio"] = parse_numeric(latest_row.get("资产负债率"))
            fundamentals["revenue_yoy"] = parse_numeric(latest_row.get("营业总收入同比增长率"))
            fundamentals["net_profit_yoy"] = parse_numeric(latest_row.get("净利润同比增长率"))

            ctx.fundamental_source = "stock_financial_abstract_ths"
            for field_name in ["roe", "asset_liability_ratio", "revenue_yoy", "net_profit_yoy"]:
                ctx.field_sources[field_name] = ctx.fundamental_source
            return fundamentals
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_financial_abstract_ths failed: {exc}")

    try:
        indicator_df = safe_call("stock_financial_analysis_indicator", symbol=stock_code)
        if indicator_df is not None and not indicator_df.empty:
            latest_row = indicator_df.iloc[-1]
            fundamentals["fundamental_report_date"] = latest_row.iloc[0]
            fundamentals["roe"] = parse_numeric(latest_row.get("净资产收益率(%)")) or parse_numeric(latest_row.get("加权净资产收益率(%)"))
            fundamentals["asset_liability_ratio"] = parse_numeric(latest_row.get("资产负债率(%)"))
            fundamentals["revenue_yoy"] = parse_numeric(latest_row.get("主营业务收入增长率(%)"))
            fundamentals["net_profit_yoy"] = parse_numeric(latest_row.get("净利润增长率(%)"))

            ctx.fundamental_source = "stock_financial_analysis_indicator"
            for field_name in ["roe", "asset_liability_ratio", "revenue_yoy", "net_profit_yoy"]:
                ctx.field_sources[field_name] = ctx.fundamental_source
            return fundamentals
    except Exception as exc:  # noqa: BLE001
        ctx.warnings.append(f"stock_financial_analysis_indicator failed: {exc}")

    ctx.errors.append("Unable to fetch fundamental fields from AkShare in the current network environment.")
    ctx.alternatives.append(
        "For fundamental fields, the most feasible real fallback is to keep stock_financial_abstract_ths as the primary source. "
        "If it fails too, export the latest quarterly report metrics from the listed-company disclosure site or another financial API, "
        "then join them by stock_code as a static snapshot layer."
    )
    return fundamentals


def build_output_table(
    calendar_df: pd.DataFrame,
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    stock_name: Optional[str],
    valuation: dict[str, Any],
    fundamentals: dict[str, Any],
) -> pd.DataFrame:
    output_df = calendar_df.copy()

    output_df = output_df.merge(
        stock_df,
        how="left",
        left_on="calendar_trade_date",
        right_on="trade_date",
    )
    output_df = output_df.merge(
        benchmark_df,
        how="left",
        left_on="calendar_trade_date",
        right_on="benchmark_trade_date",
    )

    resolved_stock_name = stock_name or valuation.get("stock_name")
    output_df["stock_name"] = resolved_stock_name
    output_df["pe_ttm"] = valuation.get("pe_ttm")
    output_df["pb"] = valuation.get("pb")
    output_df["total_market_value"] = valuation.get("total_market_value")
    output_df["circulating_market_value"] = valuation.get("circulating_market_value")
    output_df["roe"] = fundamentals.get("roe")
    output_df["asset_liability_ratio"] = fundamentals.get("asset_liability_ratio")
    output_df["revenue_yoy"] = fundamentals.get("revenue_yoy")
    output_df["net_profit_yoy"] = fundamentals.get("net_profit_yoy")

    output_df["valuation_as_of"] = valuation.get("valuation_as_of")
    output_df["fundamental_report_date"] = fundamentals.get("fundamental_report_date")

    ordered_cols = [
        "calendar_trade_date",
        "stock_code",
        "stock_name",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover_rate",
        "adjust_type",
        "data_source",
        "benchmark_code",
        "benchmark_name",
        "benchmark_trade_date",
        "benchmark_close",
        "pe_ttm",
        "pb",
        "total_market_value",
        "circulating_market_value",
        "roe",
        "asset_liability_ratio",
        "revenue_yoy",
        "net_profit_yoy",
        "valuation_as_of",
        "fundamental_report_date",
    ]

    for col in ordered_cols:
        if col not in output_df.columns:
            output_df[col] = pd.NA

    output_df = output_df[ordered_cols].copy()
    for col in ["calendar_trade_date", "trade_date", "benchmark_trade_date"]:
        output_df[col] = pd.to_datetime(output_df[col], errors="coerce").dt.strftime("%Y-%m-%d")
    return output_df


def build_report(output_df: pd.DataFrame, ctx: FetchContext, output_file: Path) -> dict[str, Any]:
    requested_fields = [
        "stock_code",
        "stock_name",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover_rate",
        "adjust_type",
        "data_source",
        "benchmark_code",
        "benchmark_name",
        "benchmark_trade_date",
        "benchmark_close",
        "calendar_trade_date",
        "pe_ttm",
        "pb",
        "total_market_value",
        "circulating_market_value",
        "roe",
        "asset_liability_ratio",
        "revenue_yoy",
        "net_profit_yoy",
    ]

    field_status: dict[str, dict[str, Any]] = {}
    missing_fields: list[str] = []

    for field_name in requested_fields:
        non_null_count = 0
        if field_name in output_df.columns:
            non_null_count = int(output_df[field_name].notna().sum())
        is_complete = non_null_count > 0
        if not is_complete:
            missing_fields.append(field_name)
        field_status[field_name] = {
            "source": ctx.field_sources.get(field_name),
            "non_null_count": non_null_count,
            "available": is_complete,
        }

    return {
        "generated_at": datetime.now().isoformat(),
        "output_csv": str(output_file),
        "row_count": int(len(output_df)),
        "column_count": int(len(output_df.columns)),
        "sources": {
            "stock_source": ctx.stock_source,
            "benchmark_source": ctx.benchmark_source,
            "calendar_source": ctx.calendar_source,
            "valuation_source": ctx.valuation_source,
            "fundamental_source": ctx.fundamental_source,
        },
        "field_status": field_status,
        "warnings": ctx.warnings,
        "errors": ctx.errors,
        "missing_fields": missing_fields,
        "alternative_solutions": ctx.alternatives,
    }


def write_alternative_note(note_path: Path, report: dict[str, Any]) -> None:
    lines = [
        "Alternative solutions for unresolved fields",
        "",
        "This file is generated only when some requested fields could not be fetched.",
        "",
        f"Missing fields: {', '.join(report['missing_fields']) or 'None'}",
        "",
        "Recommended fallback methods:",
    ]

    if report["alternative_solutions"]:
        for idx, item in enumerate(report["alternative_solutions"], start=1):
            lines.append(f"{idx}. {item}")
    else:
        lines.append("1. No alternative is required because all requested fields were fetched successfully.")

    note_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a complete one-table stock dataset with AkShare")
    parser.add_argument("--stock-code", default="000001", help="A-share stock code, e.g. 000001")
    parser.add_argument("--benchmark-code", default=DEFAULT_BENCHMARK_CODE, help="Benchmark index code, e.g. sh000300")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="Start date in YYYYMMDD")
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y%m%d"), help="End date in YYYYMMDD")
    parser.add_argument("--adjust", choices=["none", "qfq", "hfq"], default="none", help="Adjustment type for stock daily data")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for CSV/JSON files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stock_code = normalize_stock_code(args.stock_code)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ctx = FetchContext()
    log(f"Start fetching complete dataset for stock {stock_code}")

    calendar_df = fetch_calendar(args.start_date, args.end_date, ctx)
    stock_df = fetch_stock_daily(stock_code, args.start_date, args.end_date, args.adjust, ctx)
    stock_name = fetch_stock_name(stock_code, ctx)
    _, benchmark_df = fetch_benchmark_info(args.benchmark_code, ctx)
    valuation = fetch_valuation(stock_code, ctx)
    fundamentals = fetch_fundamentals(stock_code, ctx)

    if not stock_name and valuation.get("stock_name"):
        stock_name = str(valuation["stock_name"])

    output_df = build_output_table(calendar_df, stock_df, benchmark_df, stock_name, valuation, fundamentals)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"stock_complete_requirements_{stock_code}_{args.start_date}_{args.end_date}_{timestamp}.csv"
    latest_file = output_dir / f"stock_complete_requirements_{stock_code}_latest.csv"
    report_file = output_dir / f"stock_complete_requirements_{stock_code}_{args.start_date}_{args.end_date}_{timestamp}.json"
    latest_report_file = output_dir / f"stock_complete_requirements_{stock_code}_latest.json"
    alternative_note_file = output_dir / f"stock_complete_requirements_{stock_code}_{args.start_date}_{args.end_date}_{timestamp}_alternative.txt"

    output_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    output_df.to_csv(latest_file, index=False, encoding="utf-8-sig")

    report = build_report(output_df, ctx, output_file)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if report["missing_fields"]:
        write_alternative_note(alternative_note_file, report)
        log(f"Some fields are still missing after retries: {report['missing_fields']}")
        log(f"Alternative solution note written to: {alternative_note_file}")
    else:
        log("All requested fields were fetched successfully.")

    log(f"CSV written to: {output_file}")
    log(f"Report written to: {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
