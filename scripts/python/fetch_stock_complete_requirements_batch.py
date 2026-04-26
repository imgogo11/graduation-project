# -*- coding: utf-8 -*-
"""
Fetch batched complete A-share datasets with AkShare and BaoStock.

Daily history fields use real daily values first. Share-capital columns use
real daily float shares plus true total-share change events carried forward by
trading day. Market-value fields are then calculated daily from close * share.
Non-daily financial fields are written only on real announcement dates mapped
to the next trading day. Snapshot-style backfilling is disabled.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import akshare as ak
import baostock as bs
import pandas as pd

DEFAULT_OUTPUT_DIR = Path(r"D:\graduation-project\data\row")
DEFAULT_START_DATE = "20160101"
DEFAULT_BENCHMARK_CODE = "sh000300"
MAX_DATA_ROWS_PER_FILE = 1_048_575
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
MARKET_CLOSE_BUFFER = dt_time(16, 0)

BASE_COLUMNS = [
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
    "total_share",
    "outstanding_share",
    "total_market_value",
    "circulating_market_value",
    "roe",
    "asset_liability_ratio",
    "revenue_yoy",
    "net_profit_yoy",
    "valuation_as_of",
    "fundamental_report_date",
]

BS_EXTENSION_COLUMNS = [
    "bs_code",
    "bs_preclose",
    "bs_adjustflag",
    "bs_turn",
    "bs_tradestatus",
    "bs_pct_chg",
    "bs_pe_ttm",
    "bs_pb_mrq",
    "bs_ps_ttm",
    "bs_pcf_ncf_ttm",
    "bs_ipo_date",
    "bs_out_date",
    "bs_status",
]

ALL_COLUMNS = BASE_COLUMNS + BS_EXTENSION_COLUMNS

THS_REPORT_DATE = "\u62a5\u544a\u671f"
THS_REVENUE_YOY = "\u8425\u4e1a\u603b\u6536\u5165\u540c\u6bd4\u589e\u957f\u7387"
GBJG_CHANGE_DATE = "\u53d8\u66f4\u65e5\u671f"
GBJG_TOTAL_SHARE = "\u603b\u80a1\u672c"
YJBB_STOCK_CODE = "\u80a1\u7968\u4ee3\u7801"
YJBB_NOTICE_DATE = "\u6700\u65b0\u516c\u544a\u65e5\u671f"
YJBB_ROE = "\u51c0\u8d44\u4ea7\u6536\u76ca\u7387"
YJBB_REVENUE_YOY = "\u8425\u4e1a\u603b\u6536\u5165-\u540c\u6bd4\u589e\u957f"
YJBB_NET_PROFIT_YOY = "\u51c0\u5229\u6da6-\u540c\u6bd4\u589e\u957f"
ZCFZ_STOCK_CODE = "\u80a1\u7968\u4ee3\u7801"
ZCFZ_NOTICE_DATE = "\u516c\u544a\u65e5\u671f"
ZCFZ_ASSET_LIABILITY_RATIO = "\u8d44\u4ea7\u8d1f\u503a\u7387"


@dataclass(slots=True)
class StockProfile:
    stock_code: str
    bs_code: str
    stock_name: str | None
    ipo_date: str | None
    out_date: str | None
    status: str | None


@dataclass(slots=True)
class StockFetchResult:
    profile: StockProfile
    frame: pd.DataFrame
    daily_source: str
    market_value_source: str | None
    financial_source: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PartAccumulator:
    frames: list[pd.DataFrame] = field(default_factory=list)
    stock_codes: list[str] = field(default_factory=list)
    row_count: int = 0
    daily_source_counts: Counter[str] = field(default_factory=Counter)
    market_value_source_counts: Counter[str] = field(default_factory=Counter)
    financial_source_counts: Counter[str] = field(default_factory=Counter)
    failed_stocks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return self.row_count == 0

    def add_result(self, result: StockFetchResult) -> None:
        self.frames.append(result.frame)
        self.stock_codes.append(result.profile.stock_code)
        self.row_count += len(result.frame)
        self.daily_source_counts[result.daily_source] += 1
        self.market_value_source_counts[result.market_value_source or "unavailable"] += 1
        self.financial_source_counts[result.financial_source or "unavailable"] += 1
        self.warnings.extend(result.warnings)

    def add_failed_stock(self, failed_item: dict[str, Any]) -> None:
        self.failed_stocks.append(failed_item)


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


def normalize_stock_code(raw_value: Any) -> str:
    text = str(raw_value).strip()
    match = re.search(r"(\d{6})", text)
    if not match:
        raise ValueError(f"Invalid stock code: {raw_value}")
    return match.group(1)


def to_sina_symbol(stock_code: str) -> str:
    if stock_code.startswith(("5", "6", "9")):
        return f"sh{stock_code}"
    if stock_code.startswith(("4", "8")) or stock_code.startswith("92"):
        return f"bj{stock_code}"
    return f"sz{stock_code}"


def to_em_symbol(stock_code: str) -> str:
    if stock_code.startswith(("5", "6", "9")):
        return f"{stock_code}.SH"
    if stock_code.startswith(("4", "8")) or stock_code.startswith("92"):
        return f"{stock_code}.BJ"
    return f"{stock_code}.SZ"


def safe_call(
    api_name: str,
    retries: int = 3,
    sleep_seconds: float = 0.8,
    **kwargs: Any,
) -> pd.DataFrame | None:
    api_func = getattr(ak, api_name, None)
    if api_func is None:
        return None

    last_error: Exception | None = None
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


def parse_numeric(value: Any) -> float | None:
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
    elif text.endswith("\u4ebf"):
        text = text[:-1]
        multiplier = 1e8
    elif text.endswith("\u4e07"):
        text = text[:-1]
        multiplier = 1e4

    text = text.replace(",", "")
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def normalize_ratio_to_percentage_points(value: Any) -> float | None:
    numeric = parse_numeric(value)
    if numeric is None:
        return None
    if abs(numeric) <= 1:
        return numeric * 100.0
    return numeric


def normalize_balance_ratio(liability_to_asset: Any, asset_to_equity: Any) -> float | None:
    liability_raw = parse_numeric(liability_to_asset)
    asset_to_equity_raw = parse_numeric(asset_to_equity)
    if liability_raw is None or asset_to_equity_raw is None or asset_to_equity_raw <= 0:
        return None

    expected = (1.0 - (1.0 / asset_to_equity_raw)) * 100.0
    candidates = [liability_raw, liability_raw * 100.0, liability_raw * 10000.0]
    best = min(candidates, key=lambda candidate: abs(candidate - expected))
    if abs(best - expected) <= 1.0:
        return best
    return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def format_date_value(value: Any) -> str | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return clean_text(value)
    return parsed.strftime("%Y-%m-%d")


def to_datetime_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def to_mixed_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce").dt.normalize()
    numeric = pd.to_numeric(series, errors="coerce")

    millisecond_mask = numeric.notna() & numeric.abs().gt(10_000_000_000)
    if millisecond_mask.any():
        parsed.loc[millisecond_mask] = pd.to_datetime(
            numeric.loc[millisecond_mask],
            unit="ms",
            errors="coerce",
        ).dt.normalize()

    second_mask = numeric.notna() & numeric.abs().between(100_000_000, 10_000_000_000, inclusive="left")
    if second_mask.any():
        parsed.loc[second_mask] = pd.to_datetime(
            numeric.loc[second_mask],
            unit="s",
            errors="coerce",
        ).dt.normalize()

    return parsed


def iter_report_dates(start_date: str, end_date: str) -> list[str]:
    start_dt = datetime.strptime(start_date, "%Y%m%d").date()
    end_dt = datetime.strptime(end_date, "%Y%m%d").date()
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    report_dates: list[str] = []

    for year in range(start_dt.year - 1, end_dt.year + 1):
        for month, day in quarter_ends:
            report_dt = date(year, month, day)
            if report_dt <= end_dt:
                report_dates.append(report_dt.strftime("%Y%m%d"))

    return report_dates


def fetch_trade_calendar() -> pd.DataFrame:
    calendar_df = safe_call("tool_trade_date_hist_sina")
    if calendar_df is None or calendar_df.empty:
        raise RuntimeError("Unable to fetch trading calendar from akshare.tool_trade_date_hist_sina")

    calendar_df = calendar_df.rename(columns={calendar_df.columns[0]: "trade_date"}).copy()
    calendar_df["trade_date"] = to_datetime_series(calendar_df["trade_date"])
    calendar_df = calendar_df[calendar_df["trade_date"].notna()].copy()
    calendar_df.sort_values("trade_date", inplace=True)
    calendar_df.reset_index(drop=True, inplace=True)
    return calendar_df


def resolve_latest_completed_trade_date(calendar_df: pd.DataFrame) -> date:
    now = datetime.now(tz=SHANGHAI_TZ)
    trade_days = calendar_df["trade_date"].dt.date.tolist()
    eligible_days = [item for item in trade_days if item <= now.date()]
    if not eligible_days:
        raise RuntimeError("Trading calendar does not contain any completed trade day on or before today")

    latest_trade_day = eligible_days[-1]
    if latest_trade_day == now.date() and now.timetz().replace(tzinfo=None) < MARKET_CLOSE_BUFFER:
        if len(eligible_days) < 2:
            raise RuntimeError("Unable to determine a completed trade day before market close")
        return eligible_days[-2]
    return latest_trade_day


def resolve_date_range(
    *,
    start_date_text: str,
    end_date_text: str | None,
    calendar_df: pd.DataFrame,
) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    start_dt = datetime.strptime(start_date_text, "%Y%m%d").date()
    latest_completed = resolve_latest_completed_trade_date(calendar_df)

    if end_date_text:
        requested_end = datetime.strptime(end_date_text, "%Y%m%d").date()
        if requested_end > latest_completed:
            warnings.append(
                f"Requested end date {requested_end.isoformat()} exceeds the latest completed trade day "
                f"{latest_completed.isoformat()} and was clamped."
            )
        resolved_end = min(requested_end, latest_completed)
    else:
        resolved_end = latest_completed

    if start_dt > resolved_end:
        raise ValueError(
            f"Start date {start_dt.isoformat()} is later than resolved end date {resolved_end.isoformat()}"
        )

    return start_dt.strftime("%Y%m%d"), resolved_end.strftime("%Y%m%d"), warnings


def fetch_code_name_map() -> dict[str, str]:
    code_name_df = safe_call("stock_info_a_code_name")
    if code_name_df is None or code_name_df.empty:
        raise RuntimeError("Unable to fetch A-share code-name table from akshare.stock_info_a_code_name")

    result: dict[str, str] = {}
    for row in code_name_df.itertuples(index=False):
        code = normalize_stock_code(getattr(row, "code"))
        name = clean_text(getattr(row, "name"))
        if name:
            result[code] = name
    return result


def read_bs_result_set(result_set: Any) -> pd.DataFrame:
    if result_set.error_code != "0":
        raise RuntimeError(f"BaoStock query failed: {result_set.error_code} {result_set.error_msg}")

    rows: list[list[str]] = []
    while result_set.error_code == "0" and result_set.next():
        rows.append(result_set.get_row_data())
    return pd.DataFrame(rows, columns=result_set.fields)


def execute_bs_query(query_factory: Callable[[], Any]) -> pd.DataFrame:
    result_set = query_factory()
    if result_set.error_code == "10001001":
        login_result = bs.login()
        if login_result.error_code != "0":
            raise RuntimeError(
                f"BaoStock relogin failed: {login_result.error_code} {login_result.error_msg}"
            )
        result_set = query_factory()
    return read_bs_result_set(result_set)


def fetch_stock_pool(code_name_map: dict[str, str]) -> list[StockProfile]:
    basic_df = execute_bs_query(lambda: bs.query_stock_basic())
    if basic_df.empty:
        raise RuntimeError("BaoStock query_stock_basic returned no rows")

    filtered = basic_df[
        (basic_df["type"].astype(str) == "1")
        & (basic_df["status"].astype(str) == "1")
        & basic_df["code"].astype(str).str.match(r"^(sh|sz|bj)\.\d{6}$")
    ].copy()

    profiles: list[StockProfile] = []
    for row in filtered.itertuples(index=False):
        bs_code = str(row.code).strip()
        stock_code = normalize_stock_code(bs_code)
        if stock_code not in code_name_map:
            continue
        stock_name = clean_text(code_name_map.get(stock_code)) or clean_text(getattr(row, "code_name", None))
        profiles.append(
            StockProfile(
                stock_code=stock_code,
                bs_code=bs_code,
                stock_name=stock_name,
                ipo_date=format_date_value(getattr(row, "ipoDate", None)),
                out_date=format_date_value(getattr(row, "outDate", None)),
                status=clean_text(getattr(row, "status", None)),
            )
        )

    profiles.sort(key=lambda item: item.stock_code)
    return profiles


def fetch_benchmark_frame(benchmark_code: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, str, str]:
    benchmark_name = benchmark_code
    name_source = "akshare.stock_zh_index_spot_sina"
    try:
        spot_df = safe_call("stock_zh_index_spot_sina")
        if spot_df is not None and not spot_df.empty:
            code_col = spot_df.columns[0]
            name_col = spot_df.columns[1]
            matched = spot_df[spot_df[code_col].astype(str) == benchmark_code]
            if not matched.empty:
                benchmark_name = clean_text(matched.iloc[0][name_col]) or benchmark_name
    except Exception:  # noqa: BLE001
        name_source = "unavailable"

    start_dt = pd.to_datetime(start_date, format="%Y%m%d")
    end_dt = pd.to_datetime(end_date, format="%Y%m%d")

    source_name = "akshare.stock_zh_index_daily_em"
    try:
        benchmark_df = safe_call("stock_zh_index_daily_em", symbol=benchmark_code)
        if benchmark_df is None or benchmark_df.empty:
            raise RuntimeError("akshare.stock_zh_index_daily_em returned empty data")
        benchmark_df = benchmark_df.rename(
            columns={
                "date": "trade_date",
                "\u65e5\u671f": "trade_date",
                "close": "benchmark_close",
                "\u6536\u76d8": "benchmark_close",
            }
        ).copy()
    except Exception:
        source_name = "akshare.stock_zh_index_daily"
        benchmark_df = safe_call("stock_zh_index_daily", symbol=benchmark_code)
        if benchmark_df is None or benchmark_df.empty:
            raise RuntimeError(
                "Unable to fetch benchmark data from akshare.stock_zh_index_daily_em or akshare.stock_zh_index_daily"
            )
        benchmark_df = benchmark_df.rename(columns={"date": "trade_date", "close": "benchmark_close"}).copy()

    benchmark_df["trade_date"] = to_datetime_series(benchmark_df["trade_date"])
    benchmark_df["benchmark_close"] = pd.to_numeric(benchmark_df["benchmark_close"], errors="coerce")
    benchmark_df = benchmark_df[
        benchmark_df["trade_date"].notna()
        & (benchmark_df["trade_date"] >= start_dt)
        & (benchmark_df["trade_date"] <= end_dt)
    ].copy()
    benchmark_df.sort_values("trade_date", inplace=True)
    benchmark_df["benchmark_code"] = benchmark_code
    benchmark_df["benchmark_name"] = benchmark_name
    benchmark_df["benchmark_trade_date"] = benchmark_df["trade_date"].dt.strftime("%Y-%m-%d")
    return benchmark_df[
        ["trade_date", "benchmark_code", "benchmark_name", "benchmark_trade_date", "benchmark_close"]
    ], source_name, name_source


def fetch_baostock_daily(profile: StockProfile, start_date: str, end_date: str) -> pd.DataFrame:
    fields = ",".join(
        [
            "date",
            "code",
            "open",
            "high",
            "low",
            "close",
            "preclose",
            "volume",
            "amount",
            "adjustflag",
            "turn",
            "tradestatus",
            "pctChg",
            "peTTM",
            "pbMRQ",
            "psTTM",
            "pcfNcfTTM",
        ]
    )
    result_df = execute_bs_query(
        lambda: bs.query_history_k_data_plus(
            profile.bs_code,
            fields,
            start_date=datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d"),
            end_date=datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d"),
            frequency="d",
            adjustflag="3",
        )
    )
    if result_df.empty:
        raise RuntimeError(f"BaoStock returned empty daily data for {profile.bs_code}")

    result_df["trade_date"] = to_datetime_series(result_df["date"])
    result_df = result_df[result_df["trade_date"].notna()].copy()
    for column in [
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "volume",
        "amount",
        "turn",
        "pctChg",
        "peTTM",
        "pbMRQ",
        "psTTM",
        "pcfNcfTTM",
    ]:
        result_df[column] = pd.to_numeric(result_df[column], errors="coerce")

    result_df["stock_code"] = profile.stock_code
    result_df["stock_name"] = profile.stock_name
    result_df["turnover_rate"] = result_df["turn"]
    result_df["adjust_type"] = "none"
    result_df["data_source"] = "baostock.query_history_k_data_plus"
    result_df["pe_ttm"] = result_df["peTTM"]
    result_df["pb"] = result_df["pbMRQ"]
    result_df["bs_code"] = result_df["code"]
    result_df["bs_preclose"] = result_df["preclose"]
    result_df["bs_adjustflag"] = result_df["adjustflag"]
    result_df["bs_turn"] = result_df["turn"]
    result_df["bs_tradestatus"] = result_df["tradestatus"]
    result_df["bs_pct_chg"] = result_df["pctChg"]
    result_df["bs_pe_ttm"] = result_df["peTTM"]
    result_df["bs_pb_mrq"] = result_df["pbMRQ"]
    result_df["bs_ps_ttm"] = result_df["psTTM"]
    result_df["bs_pcf_ncf_ttm"] = result_df["pcfNcfTTM"]
    result_df["bs_ipo_date"] = profile.ipo_date
    result_df["bs_out_date"] = profile.out_date
    result_df["bs_status"] = profile.status
    result_df.sort_values("trade_date", inplace=True)
    result_df.drop_duplicates(subset=["trade_date"], keep="last", inplace=True)
    result_df.reset_index(drop=True, inplace=True)
    return result_df


def fetch_akshare_daily(stock_code: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, str]:
    try:
        hist_df = safe_call(
            "stock_zh_a_hist",
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="",
        )
        if hist_df is not None and not hist_df.empty:
            hist_df = hist_df.rename(
                columns={
                    "\u65e5\u671f": "trade_date",
                    "\u80a1\u7968\u4ee3\u7801": "stock_code",
                    "\u5f00\u76d8": "open",
                    "\u6700\u9ad8": "high",
                    "\u6700\u4f4e": "low",
                    "\u6536\u76d8": "close",
                    "\u6210\u4ea4\u91cf": "volume",
                    "\u6210\u4ea4\u989d": "amount",
                    "\u6362\u624b\u7387": "turnover_rate",
                }
            ).copy()
            hist_df["trade_date"] = to_datetime_series(hist_df["trade_date"])
            hist_df = hist_df[hist_df["trade_date"].notna()].copy()
            if "stock_code" in hist_df.columns:
                hist_df["stock_code"] = hist_df["stock_code"].astype(str).map(normalize_stock_code)
            hist_df["volume"] = pd.to_numeric(hist_df["volume"], errors="coerce") * 100.0
            for column in ["open", "high", "low", "close", "amount", "turnover_rate"]:
                hist_df[column] = pd.to_numeric(hist_df[column], errors="coerce")
            hist_df["adjust_type"] = "none"
            hist_df["data_source"] = "akshare.stock_zh_a_hist"
            hist_df.sort_values("trade_date", inplace=True)
            hist_df.drop_duplicates(subset=["trade_date"], keep="last", inplace=True)
            hist_df.reset_index(drop=True, inplace=True)
            return hist_df, "akshare.stock_zh_a_hist"
    except Exception:
        pass

    daily_df = safe_call(
        "stock_zh_a_daily",
        symbol=to_sina_symbol(stock_code),
        start_date=start_date,
        end_date=end_date,
    )
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"AkShare fallback returned empty daily data for {stock_code}")

    daily_df = daily_df.copy()
    daily_df["trade_date"] = to_datetime_series(daily_df["date"])
    daily_df = daily_df[daily_df["trade_date"].notna()].copy()
    for column in ["open", "high", "low", "close", "volume", "amount", "turnover"]:
        if column in daily_df.columns:
            daily_df[column] = pd.to_numeric(daily_df[column], errors="coerce")
    daily_df["stock_code"] = stock_code
    daily_df["turnover_rate"] = daily_df["turnover"].map(normalize_ratio_to_percentage_points)
    daily_df["adjust_type"] = "none"
    daily_df["data_source"] = "akshare.stock_zh_a_daily"
    daily_df.sort_values("trade_date", inplace=True)
    daily_df.drop_duplicates(subset=["trade_date"], keep="last", inplace=True)
    daily_df.reset_index(drop=True, inplace=True)
    return daily_df, "akshare.stock_zh_a_daily"


def fetch_outstanding_share_history(
    stock_code: str,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    warnings: list[str] = []
    lookback_start = (datetime.strptime(start_date, "%Y%m%d") - timedelta(days=31)).strftime("%Y%m%d")
    try:
        daily_df = safe_call(
            "stock_zh_a_daily",
            symbol=to_sina_symbol(stock_code),
            start_date=lookback_start,
            end_date=end_date,
        )
        if daily_df is None or daily_df.empty:
            return pd.DataFrame(columns=["trade_date", "outstanding_share"]), None, warnings
        if "outstanding_share" not in daily_df.columns:
            warnings.append(f"{stock_code}: akshare.stock_zh_a_daily missing outstanding_share")
            return pd.DataFrame(columns=["trade_date", "outstanding_share"]), None, warnings

        daily_df = daily_df.copy()
        daily_df["trade_date"] = to_datetime_series(daily_df["date"])
        daily_df["outstanding_share"] = pd.to_numeric(daily_df["outstanding_share"], errors="coerce")
        daily_df = daily_df[daily_df["trade_date"].notna() & daily_df["outstanding_share"].notna()].copy()
        daily_df.sort_values("trade_date", inplace=True)
        daily_df.drop_duplicates(subset=["trade_date"], keep="last", inplace=True)
        daily_df.reset_index(drop=True, inplace=True)
        return daily_df[["trade_date", "outstanding_share"]], "akshare.stock_zh_a_daily", warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{stock_code}: akshare.stock_zh_a_daily outstanding_share fetch failed: {exc}")
        return pd.DataFrame(columns=["trade_date", "outstanding_share"]), None, warnings


def fetch_total_share_events(stock_code: str) -> tuple[pd.DataFrame, str | None, list[str]]:
    warnings: list[str] = []
    try:
        gbjg_df = safe_call("stock_zh_a_gbjg_em", symbol=to_em_symbol(stock_code))
        if gbjg_df is None or gbjg_df.empty:
            return pd.DataFrame(columns=["event_date", "total_share"]), None, warnings

        gbjg_df = gbjg_df.copy()
        gbjg_df["event_date"] = to_datetime_series(gbjg_df[GBJG_CHANGE_DATE])
        gbjg_df["total_share"] = pd.to_numeric(
            gbjg_df[GBJG_TOTAL_SHARE].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )
        gbjg_df = gbjg_df[gbjg_df["event_date"].notna() & gbjg_df["total_share"].notna()].copy()
        if gbjg_df.empty:
            return pd.DataFrame(columns=["event_date", "total_share"]), "akshare.stock_zh_a_gbjg_em", warnings

        gbjg_df.sort_values("event_date", inplace=True)
        gbjg_df = gbjg_df.groupby("event_date", as_index=False).last()
        gbjg_df["is_changed"] = gbjg_df["total_share"].ne(gbjg_df["total_share"].shift())
        if not gbjg_df.empty:
            gbjg_df.loc[gbjg_df.index[0], "is_changed"] = True
        gbjg_df = gbjg_df[gbjg_df["is_changed"]].copy()
        return gbjg_df[["event_date", "total_share"]], "akshare.stock_zh_a_gbjg_em", warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{stock_code}: akshare.stock_zh_a_gbjg_em failed: {exc}")
        return pd.DataFrame(columns=["event_date", "total_share"]), None, warnings


def map_to_next_trade_date(trade_dates: pd.Index, event_date: Any) -> pd.Timestamp | None:
    parsed = pd.to_datetime(event_date, errors="coerce")
    if pd.isna(parsed):
        return None
    normalized = parsed.normalize()
    position = trade_dates.searchsorted(normalized, side="left")
    if position >= len(trade_dates):
        return None
    return pd.Timestamp(trade_dates[position])


def build_share_market_value_frame(
    stock_code: str,
    daily_df: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    warnings: list[str] = []
    market_value_sources: list[str] = []

    share_market_df = (
        daily_df[["trade_date", "close"]]
        .dropna(subset=["trade_date"])
        .drop_duplicates(subset=["trade_date"], keep="last")
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    share_market_df["close"] = pd.to_numeric(share_market_df["close"], errors="coerce")

    total_df = pd.DataFrame(columns=["trade_date", "total_share"])
    total_events, total_source, total_warnings = fetch_total_share_events(stock_code)
    warnings.extend(total_warnings)
    if total_source:
        market_value_sources.append(total_source)
    if not total_events.empty:
        effective_total = (
            total_events.rename(columns={"event_date": "effective_date"})[["effective_date", "total_share"]]
            .dropna(subset=["effective_date", "total_share"])
            .sort_values("effective_date")
            .drop_duplicates(subset=["effective_date"], keep="last")
        )
        if not effective_total.empty:
            total_df = pd.merge_asof(
                share_market_df[["trade_date"]].sort_values("trade_date"),
                effective_total,
                left_on="trade_date",
                right_on="effective_date",
                direction="backward",
            )
            total_df = total_df[["trade_date", "total_share"]]

    outstanding_share_df = pd.DataFrame(columns=["trade_date", "outstanding_share"])
    outstanding_df, float_source, float_warnings = fetch_outstanding_share_history(stock_code, start_date, end_date)
    warnings.extend(float_warnings)
    if float_source:
        market_value_sources.append(f"{float_source}.outstanding_share")
    if not outstanding_df.empty:
        outstanding_share_df = (
            outstanding_df[["trade_date", "outstanding_share"]]
            .drop_duplicates(subset=["trade_date"], keep="last")
            .sort_values("trade_date")
            .reset_index(drop=True)
        )

    if total_df.empty:
        share_market_df["total_share"] = pd.NA
    else:
        share_market_df = share_market_df.merge(total_df, how="left", on="trade_date")
    if outstanding_share_df.empty:
        share_market_df["outstanding_share"] = pd.NA
    else:
        share_market_df = share_market_df.merge(outstanding_share_df, how="left", on="trade_date")

    share_market_df["total_market_value"] = share_market_df["close"] * share_market_df["total_share"]
    share_market_df["circulating_market_value"] = (
        share_market_df["close"] * share_market_df["outstanding_share"]
    )
    share_market_df = share_market_df[
        [
            "trade_date",
            "total_share",
            "outstanding_share",
            "total_market_value",
            "circulating_market_value",
        ]
    ].copy()

    source_text = ";".join(sorted(dict.fromkeys(market_value_sources))) if market_value_sources else None
    return share_market_df, source_text, warnings


def fetch_bs_quarterly_endpoint(
    profile: StockProfile,
    query_name: str,
    start_year: int,
    end_year: int,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    rows: list[pd.DataFrame] = []
    warnings: list[str] = []

    for year in range(start_year, end_year + 1):
        for quarter in (1, 2, 3, 4):
            try:
                query_func = getattr(bs, query_name)
                result_df = execute_bs_query(
                    lambda query_func=query_func, year=year, quarter=quarter: query_func(
                        code=profile.bs_code,
                        year=year,
                        quarter=quarter,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{profile.stock_code}: {query_name} {year}Q{quarter} failed: {exc}")
                continue

            if result_df.empty:
                continue
            rows.append(result_df.copy())

    if not rows:
        return pd.DataFrame(), None, warnings

    combined = pd.concat(rows, ignore_index=True)
    return combined, f"baostock.{query_name}", warnings


def first_non_null(series: pd.Series) -> Any:
    valid = series.dropna()
    if valid.empty:
        return pd.NA
    return valid.iloc[-1]


def add_financial_event_rows(
    *,
    rows: list[dict[str, Any]],
    df: pd.DataFrame | None,
    report_date: str,
    source_name: str,
    warnings: list[str],
) -> None:
    if df is None or df.empty:
        return

    working = df.copy()
    try:
        if source_name == "akshare.stock_yjbb_em":
            required = {
                YJBB_STOCK_CODE,
                YJBB_NOTICE_DATE,
                YJBB_ROE,
                YJBB_REVENUE_YOY,
                YJBB_NET_PROFIT_YOY,
            }
            missing = required - set(working.columns)
            if missing:
                warnings.append(f"{source_name} {report_date} missing columns: {sorted(missing)}")
                return
            working["pub_date"] = to_mixed_date_series(working[YJBB_NOTICE_DATE])
            for _, row in working.iterrows():
                try:
                    stock_code = normalize_stock_code(row.get(YJBB_STOCK_CODE))
                except ValueError:
                    continue
                pub_date = row.get("pub_date")
                if pd.isna(pub_date):
                    continue
                rows.append(
                    {
                        "stock_code": stock_code,
                        "pub_date": pub_date,
                        "stat_date": datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d"),
                        "roe": parse_numeric(row.get(YJBB_ROE)),
                        "asset_liability_ratio": pd.NA,
                        "revenue_yoy": parse_numeric(row.get(YJBB_REVENUE_YOY)),
                        "net_profit_yoy": parse_numeric(row.get(YJBB_NET_PROFIT_YOY)),
                    }
                )
        elif source_name == "akshare.stock_zcfz_em":
            required = {ZCFZ_STOCK_CODE, ZCFZ_NOTICE_DATE, ZCFZ_ASSET_LIABILITY_RATIO}
            missing = required - set(working.columns)
            if missing:
                warnings.append(f"{source_name} {report_date} missing columns: {sorted(missing)}")
                return
            working["pub_date"] = to_mixed_date_series(working[ZCFZ_NOTICE_DATE])
            for _, row in working.iterrows():
                try:
                    stock_code = normalize_stock_code(row.get(ZCFZ_STOCK_CODE))
                except ValueError:
                    continue
                pub_date = row.get("pub_date")
                if pd.isna(pub_date):
                    continue
                rows.append(
                    {
                        "stock_code": stock_code,
                        "pub_date": pub_date,
                        "stat_date": datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d"),
                        "roe": pd.NA,
                        "asset_liability_ratio": parse_numeric(row.get(ZCFZ_ASSET_LIABILITY_RATIO)),
                        "revenue_yoy": pd.NA,
                        "net_profit_yoy": pd.NA,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{source_name} {report_date} normalization failed: {exc}")


def fetch_market_financial_events(
    start_date: str,
    end_date: str,
) -> tuple[dict[str, pd.DataFrame], str | None, list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    used_sources: list[str] = []

    for report_date in iter_report_dates(start_date, end_date):
        yjbb_df = None
        try:
            yjbb_df = safe_call("stock_yjbb_em", date=report_date)
            if yjbb_df is not None and not yjbb_df.empty:
                used_sources.append("akshare.stock_yjbb_em")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"akshare.stock_yjbb_em {report_date} failed: {exc}")
        add_financial_event_rows(
            rows=rows,
            df=yjbb_df,
            report_date=report_date,
            source_name="akshare.stock_yjbb_em",
            warnings=warnings,
        )

        zcfz_df = None
        try:
            zcfz_df = safe_call("stock_zcfz_em", date=report_date)
            if zcfz_df is not None and not zcfz_df.empty:
                used_sources.append("akshare.stock_zcfz_em")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"akshare.stock_zcfz_em {report_date} failed: {exc}")
        add_financial_event_rows(
            rows=rows,
            df=zcfz_df,
            report_date=report_date,
            source_name="akshare.stock_zcfz_em",
            warnings=warnings,
        )

    if not rows:
        return {}, None, warnings

    events_df = pd.DataFrame(rows)
    events_df.dropna(subset=["stock_code", "pub_date", "stat_date"], inplace=True)
    if events_df.empty:
        return {}, None, warnings

    events_df.sort_values(["stock_code", "pub_date", "stat_date"], inplace=True)
    events_df = events_df.groupby(["stock_code", "pub_date", "stat_date"], as_index=False).agg(
        {
            "roe": first_non_null,
            "asset_liability_ratio": first_non_null,
            "revenue_yoy": first_non_null,
            "net_profit_yoy": first_non_null,
        }
    )

    event_map = {
        stock_code: group.drop(columns=["stock_code"]).copy()
        for stock_code, group in events_df.groupby("stock_code")
    }
    source_text = ";".join(sorted(set(used_sources))) if used_sources else None
    return event_map, source_text, warnings


def build_financial_event_frame_from_market_cache(
    profile: StockProfile,
    daily_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    financial_event_map: dict[str, pd.DataFrame],
    financial_source: str | None,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    warnings: list[str] = []
    source_events = financial_event_map.get(profile.stock_code)
    empty_frame = pd.DataFrame(
        columns=[
            "trade_date",
            "roe",
            "asset_liability_ratio",
            "revenue_yoy",
            "net_profit_yoy",
            "fundamental_report_date",
        ]
    )
    if source_events is None or source_events.empty:
        return empty_frame, financial_source, warnings

    daily_trade_dates = (
        pd.Index(daily_df["trade_date"].dropna().drop_duplicates().sort_values().tolist()).sort_values()
    )
    start_dt = pd.to_datetime(start_date, format="%Y%m%d")
    end_dt = pd.to_datetime(end_date, format="%Y%m%d")
    event_rows: list[dict[str, Any]] = []
    for row in source_events.itertuples(index=False):
        pub_ts = pd.to_datetime(row.pub_date, errors="coerce")
        if pd.isna(pub_ts):
            continue
        mapped_trade_date = map_to_next_trade_date(daily_trade_dates, pub_ts)
        if mapped_trade_date is None or mapped_trade_date < start_dt or mapped_trade_date > end_dt:
            continue
        event_rows.append(
            {
                "trade_date": mapped_trade_date,
                "pub_date": pub_ts.normalize(),
                "fundamental_report_date": row.stat_date,
                "roe": getattr(row, "roe", None),
                "asset_liability_ratio": getattr(row, "asset_liability_ratio", None),
                "revenue_yoy": getattr(row, "revenue_yoy", None),
                "net_profit_yoy": getattr(row, "net_profit_yoy", None),
            }
        )

    if not event_rows:
        return empty_frame, financial_source, warnings

    event_df = pd.DataFrame(event_rows)
    event_df.sort_values(["trade_date", "pub_date", "fundamental_report_date"], inplace=True)
    event_df = event_df.groupby("trade_date", as_index=False).agg(
        {
            "roe": first_non_null,
            "asset_liability_ratio": first_non_null,
            "revenue_yoy": first_non_null,
            "net_profit_yoy": first_non_null,
            "fundamental_report_date": first_non_null,
        }
    )
    return event_df, financial_source, warnings


def fetch_revenue_yoy_map(stock_code: str) -> tuple[dict[str, float | None], str | None, list[str]]:
    warnings: list[str] = []
    try:
        ths_df = safe_call("stock_financial_abstract_ths", symbol=stock_code)
        if ths_df is None or ths_df.empty:
            return {}, None, warnings

        valid_df = ths_df.copy()
        valid_df["report_date"] = pd.to_datetime(valid_df[THS_REPORT_DATE], errors="coerce").dt.strftime("%Y-%m-%d")
        valid_df = valid_df[valid_df["report_date"].notna()].copy()
        revenue_map: dict[str, float | None] = {}
        for _, row in valid_df.iterrows():
            report_date = clean_text(row.get("report_date"))
            if not report_date:
                continue
            revenue_map[report_date] = parse_numeric(row.get(THS_REVENUE_YOY))
        return revenue_map, "akshare.stock_financial_abstract_ths", warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{stock_code}: akshare.stock_financial_abstract_ths failed: {exc}")
        return {}, None, warnings


def build_financial_event_frame(
    profile: StockProfile,
    daily_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    financial_event_map: dict[str, pd.DataFrame] | None = None,
    financial_batch_source: str | None = None,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    if financial_event_map is not None:
        return build_financial_event_frame_from_market_cache(
            profile,
            daily_df,
            start_date,
            end_date,
            financial_event_map,
            financial_batch_source,
        )

    warnings: list[str] = []
    financial_sources: list[str] = []

    start_year = datetime.strptime(start_date, "%Y%m%d").year
    end_year = datetime.strptime(end_date, "%Y%m%d").year
    ipo_year = None
    if profile.ipo_date:
        try:
            ipo_year = datetime.strptime(profile.ipo_date, "%Y-%m-%d").year
        except ValueError:
            ipo_year = None
    query_start_year = max(start_year - 1, (ipo_year - 1) if ipo_year is not None else start_year - 1)

    profit_df, profit_source, profit_warnings = fetch_bs_quarterly_endpoint(
        profile,
        "query_profit_data",
        query_start_year,
        end_year,
    )
    growth_df, growth_source, growth_warnings = fetch_bs_quarterly_endpoint(
        profile,
        "query_growth_data",
        query_start_year,
        end_year,
    )
    balance_df, balance_source, balance_warnings = fetch_bs_quarterly_endpoint(
        profile,
        "query_balance_data",
        query_start_year,
        end_year,
    )
    warnings.extend(profit_warnings)
    warnings.extend(growth_warnings)
    warnings.extend(balance_warnings)

    if profit_source:
        financial_sources.append(profit_source)
    if growth_source:
        financial_sources.append(growth_source)
    if balance_source:
        financial_sources.append(balance_source)

    profit_norm = pd.DataFrame(columns=["pub_date", "stat_date", "roe"])
    if not profit_df.empty:
        profit_norm = profit_df.copy()
        profit_norm["pub_date"] = pd.to_datetime(profit_norm["pubDate"], errors="coerce").dt.strftime("%Y-%m-%d")
        profit_norm["stat_date"] = pd.to_datetime(profit_norm["statDate"], errors="coerce").dt.strftime("%Y-%m-%d")
        profit_norm["roe"] = profit_norm["roeAvg"].map(normalize_ratio_to_percentage_points)
        profit_norm = profit_norm[["pub_date", "stat_date", "roe"]].dropna(
            subset=["pub_date", "stat_date"],
            how="any",
        )
        profit_norm.drop_duplicates(subset=["pub_date", "stat_date"], keep="last", inplace=True)

    growth_norm = pd.DataFrame(columns=["pub_date", "stat_date", "net_profit_yoy"])
    if not growth_df.empty:
        growth_norm = growth_df.copy()
        growth_norm["pub_date"] = pd.to_datetime(growth_norm["pubDate"], errors="coerce").dt.strftime("%Y-%m-%d")
        growth_norm["stat_date"] = pd.to_datetime(growth_norm["statDate"], errors="coerce").dt.strftime("%Y-%m-%d")
        growth_norm["net_profit_yoy"] = growth_norm["YOYNI"].map(normalize_ratio_to_percentage_points)
        growth_norm = growth_norm[["pub_date", "stat_date", "net_profit_yoy"]].dropna(
            subset=["pub_date", "stat_date"],
            how="any",
        )
        growth_norm.drop_duplicates(subset=["pub_date", "stat_date"], keep="last", inplace=True)

    balance_norm = pd.DataFrame(columns=["pub_date", "stat_date", "asset_liability_ratio"])
    if not balance_df.empty:
        balance_norm = balance_df.copy()
        balance_norm["pub_date"] = pd.to_datetime(balance_norm["pubDate"], errors="coerce").dt.strftime("%Y-%m-%d")
        balance_norm["stat_date"] = pd.to_datetime(balance_norm["statDate"], errors="coerce").dt.strftime("%Y-%m-%d")
        balance_norm["asset_liability_ratio"] = balance_norm.apply(
            lambda row: normalize_balance_ratio(
                row.get("liabilityToAsset"),
                row.get("assetToEquity"),
            ),
            axis=1,
        )
        balance_norm = balance_norm[["pub_date", "stat_date", "asset_liability_ratio"]].dropna(
            subset=["pub_date", "stat_date"],
            how="any",
        )
        balance_norm.drop_duplicates(subset=["pub_date", "stat_date"], keep="last", inplace=True)

    merged_df = pd.DataFrame(columns=["pub_date", "stat_date"])
    if not profit_norm.empty:
        merged_df = profit_norm[["pub_date", "stat_date"]].copy()
    if not growth_norm.empty:
        merged_df = (
            growth_norm[["pub_date", "stat_date"]].copy()
            if merged_df.empty
            else merged_df.merge(growth_norm[["pub_date", "stat_date"]], how="outer", on=["pub_date", "stat_date"])
        )
    if not balance_norm.empty:
        merged_df = (
            balance_norm[["pub_date", "stat_date"]].copy()
            if merged_df.empty
            else merged_df.merge(balance_norm[["pub_date", "stat_date"]], how="outer", on=["pub_date", "stat_date"])
        )
    if merged_df.empty:
        merged_df = pd.DataFrame(columns=["pub_date", "stat_date"])

    if not profit_norm.empty:
        merged_df = merged_df.merge(profit_norm, how="left", on=["pub_date", "stat_date"])
    if not growth_norm.empty:
        merged_df = merged_df.merge(growth_norm, how="left", on=["pub_date", "stat_date"])
    if not balance_norm.empty:
        merged_df = merged_df.merge(balance_norm, how="left", on=["pub_date", "stat_date"])

    revenue_map, revenue_source, revenue_warnings = fetch_revenue_yoy_map(profile.stock_code)
    warnings.extend(revenue_warnings)
    if revenue_source:
        financial_sources.append(revenue_source)
    if not merged_df.empty:
        merged_df["revenue_yoy"] = merged_df["stat_date"].map(revenue_map)
        merged_df["fundamental_report_date"] = merged_df["stat_date"]

    if merged_df.empty:
        return (
            pd.DataFrame(
                columns=[
                    "trade_date",
                    "roe",
                    "asset_liability_ratio",
                    "revenue_yoy",
                    "net_profit_yoy",
                    "fundamental_report_date",
                ]
            ),
            ";".join(sorted(dict.fromkeys(financial_sources))) if financial_sources else None,
            warnings,
        )

    daily_trade_dates = (
        pd.Index(daily_df["trade_date"].dropna().drop_duplicates().sort_values().tolist()).sort_values()
    )
    start_dt = pd.to_datetime(start_date, format="%Y%m%d")
    end_dt = pd.to_datetime(end_date, format="%Y%m%d")
    event_rows: list[dict[str, Any]] = []
    for row in merged_df.itertuples(index=False):
        pub_ts = pd.to_datetime(row.pub_date, errors="coerce")
        if pd.isna(pub_ts):
            continue
        mapped_trade_date = map_to_next_trade_date(daily_trade_dates, pub_ts)
        if mapped_trade_date is None or mapped_trade_date < start_dt or mapped_trade_date > end_dt:
            continue
        event_rows.append(
            {
                "trade_date": mapped_trade_date,
                "pub_date": pub_ts.normalize(),
                "roe": getattr(row, "roe", None),
                "asset_liability_ratio": getattr(row, "asset_liability_ratio", None),
                "revenue_yoy": getattr(row, "revenue_yoy", None),
                "net_profit_yoy": getattr(row, "net_profit_yoy", None),
                "fundamental_report_date": getattr(row, "fundamental_report_date", None),
            }
        )

    if not event_rows:
        return (
            pd.DataFrame(
                columns=[
                    "trade_date",
                    "roe",
                    "asset_liability_ratio",
                    "revenue_yoy",
                    "net_profit_yoy",
                    "fundamental_report_date",
                ]
            ),
            ";".join(sorted(dict.fromkeys(financial_sources))) if financial_sources else None,
            warnings,
        )

    event_df = pd.DataFrame(event_rows)
    event_df.sort_values(["trade_date", "pub_date"], inplace=True)
    event_df = event_df.groupby("trade_date", as_index=False).last()
    event_df.drop(columns=["pub_date"], inplace=True, errors="ignore")
    source_text = ";".join(sorted(dict.fromkeys(financial_sources))) if financial_sources else None
    return event_df, source_text, warnings


def build_stock_frame(
    *,
    profile: StockProfile,
    daily_df: pd.DataFrame,
    daily_source: str,
    benchmark_df: pd.DataFrame,
    share_market_value_df: pd.DataFrame,
    financial_event_df: pd.DataFrame,
) -> pd.DataFrame:
    frame = daily_df.copy()
    frame["trade_date"] = to_datetime_series(frame["trade_date"])
    frame = frame[frame["trade_date"].notna()].copy()
    frame["stock_code"] = profile.stock_code
    frame["stock_name"] = profile.stock_name
    frame["adjust_type"] = "none"
    frame["data_source"] = daily_source

    if daily_source != "baostock.query_history_k_data_plus":
        for column in BS_EXTENSION_COLUMNS:
            if column not in frame.columns:
                frame[column] = pd.NA
        if "pe_ttm" not in frame.columns:
            frame["pe_ttm"] = pd.NA
        if "pb" not in frame.columns:
            frame["pb"] = pd.NA

    frame = frame.merge(benchmark_df, how="left", on="trade_date")
    if not share_market_value_df.empty:
        frame = frame.merge(share_market_value_df, how="left", on="trade_date")
    else:
        frame["total_share"] = pd.NA
        frame["outstanding_share"] = pd.NA
        frame["total_market_value"] = pd.NA
        frame["circulating_market_value"] = pd.NA

    if not financial_event_df.empty:
        frame = frame.merge(financial_event_df, how="left", on="trade_date")
    else:
        frame["roe"] = pd.NA
        frame["asset_liability_ratio"] = pd.NA
        frame["revenue_yoy"] = pd.NA
        frame["net_profit_yoy"] = pd.NA
        frame["fundamental_report_date"] = pd.NA

    frame["calendar_trade_date"] = frame["trade_date"].dt.strftime("%Y-%m-%d")
    frame["trade_date"] = frame["trade_date"].dt.strftime("%Y-%m-%d")
    frame["valuation_as_of"] = pd.NA

    for column in ALL_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    frame["fundamental_report_date"] = frame["fundamental_report_date"].map(format_date_value)
    frame["bs_ipo_date"] = frame["bs_ipo_date"].map(format_date_value)
    frame["bs_out_date"] = frame["bs_out_date"].map(format_date_value)
    # Keep CSV serialization compatible with earlier generated parts.
    for numeric_column in ["volume", "total_share"]:
        frame[numeric_column] = pd.to_numeric(frame[numeric_column], errors="coerce").astype("float64")

    frame = frame[ALL_COLUMNS].copy()
    frame.drop_duplicates(subset=["stock_code", "trade_date"], keep="last", inplace=True)
    frame.sort_values(["stock_code", "trade_date"], inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame


def fetch_one_stock(
    *,
    profile: StockProfile,
    start_date: str,
    end_date: str,
    benchmark_df: pd.DataFrame,
    financial_event_map: dict[str, pd.DataFrame] | None = None,
    financial_batch_source: str | None = None,
) -> StockFetchResult:
    warnings: list[str] = []

    try:
        daily_df = fetch_baostock_daily(profile, start_date, end_date)
        daily_source = "baostock.query_history_k_data_plus"
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{profile.stock_code}: BaoStock daily fetch failed and AkShare fallback was used: {exc}")
        daily_df, daily_source = fetch_akshare_daily(profile.stock_code, start_date, end_date)

    share_market_value_df, market_value_source, market_value_warnings = build_share_market_value_frame(
        profile.stock_code,
        daily_df,
        start_date,
        end_date,
    )
    financial_event_df, financial_source, financial_warnings = build_financial_event_frame(
        profile,
        daily_df,
        start_date,
        end_date,
        financial_event_map=financial_event_map,
        financial_batch_source=financial_batch_source,
    )
    warnings.extend(market_value_warnings)
    warnings.extend(financial_warnings)

    frame = build_stock_frame(
        profile=profile,
        daily_df=daily_df,
        daily_source=daily_source,
        benchmark_df=benchmark_df,
        share_market_value_df=share_market_value_df,
        financial_event_df=financial_event_df,
    )
    if frame.empty:
        raise RuntimeError(f"{profile.stock_code}: fetched data frame is empty after normalization")

    return StockFetchResult(
        profile=profile,
        frame=frame,
        daily_source=daily_source,
        market_value_source=market_value_source,
        financial_source=financial_source,
        warnings=warnings,
    )


def build_part_report(
    *,
    frame: pd.DataFrame,
    csv_path: Path,
    part_no: int,
    accumulator: PartAccumulator,
    calendar_source: str,
    benchmark_source: str,
    benchmark_name_source: str,
) -> dict[str, Any]:
    field_non_null_counts = {
        column: int(frame[column].notna().sum()) if column in frame.columns else 0
        for column in ALL_COLUMNS
    }
    return {
        "generated_at": datetime.now().isoformat(),
        "output_csv": str(csv_path),
        "part_no": part_no,
        "row_count": int(len(frame)),
        "stock_count": int(frame["stock_code"].nunique()),
        "stock_code_range": [
            clean_text(frame["stock_code"].iloc[0]),
            clean_text(frame["stock_code"].iloc[-1]),
        ],
        "date_range": [
            clean_text(frame["trade_date"].min()),
            clean_text(frame["trade_date"].max()),
        ],
        "column_count": int(len(frame.columns)),
        "field_non_null_counts": field_non_null_counts,
        "sources": {
            "calendar_source": calendar_source,
            "benchmark_source": benchmark_source,
            "benchmark_name_source": benchmark_name_source,
            "daily_sources": dict(accumulator.daily_source_counts),
            "market_value_sources": dict(accumulator.market_value_source_counts),
            "financial_sources": dict(accumulator.financial_source_counts),
        },
        "failed_stocks": accumulator.failed_stocks,
        "warnings": accumulator.warnings,
    }


def flush_part(
    *,
    accumulator: PartAccumulator,
    part_no: int,
    output_dir: Path,
    start_date: str,
    end_date: str,
    timestamp: str,
    calendar_source: str,
    benchmark_source: str,
    benchmark_name_source: str,
) -> dict[str, Any]:
    if accumulator.is_empty():
        raise ValueError("Cannot flush an empty part")

    frame = pd.concat(accumulator.frames, ignore_index=True)
    frame = frame[ALL_COLUMNS].copy()
    frame.sort_values(["stock_code", "trade_date"], inplace=True)
    frame.reset_index(drop=True, inplace=True)

    first_code = clean_text(frame["stock_code"].iloc[0]) or "unknown"
    last_code = clean_text(frame["stock_code"].iloc[-1]) or "unknown"
    stem = (
        f"stock_complete_requirements_batch_{start_date}_{end_date}_{timestamp}_"
        f"part{part_no:02d}_{first_code}_{last_code}"
    )
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"

    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    report = build_part_report(
        frame=frame,
        csv_path=csv_path,
        part_no=part_no,
        accumulator=accumulator,
        calendar_source=calendar_source,
        benchmark_source=benchmark_source,
        benchmark_name_source=benchmark_name_source,
    )
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_json"] = str(json_path)
    log(f"Wrote part {part_no:02d}: {csv_path.name} ({len(frame)} rows, {frame['stock_code'].nunique()} stocks)")
    return report


def build_manifest(
    *,
    start_date: str,
    end_date: str,
    output_dir: Path,
    benchmark_code: str,
    benchmark_name: str,
    total_profiles: int,
    processed_profiles: int,
    stock_limit: int | None,
    part_reports: list[dict[str, Any]],
    failed_stocks: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    total_row_count = sum(int(item["row_count"]) for item in part_reports)
    total_stock_count = sum(int(item["stock_count"]) for item in part_reports)
    field_non_null_counts = {column: 0 for column in ALL_COLUMNS}
    for item in part_reports:
        for column, count in item["field_non_null_counts"].items():
            field_non_null_counts[column] += int(count)

    return {
        "generated_at": datetime.now().isoformat(),
        "date_range": [start_date, end_date],
        "output_dir": str(output_dir),
        "benchmark": {"code": benchmark_code, "name": benchmark_name},
        "stock_pool_size": total_profiles,
        "processed_stock_count": processed_profiles,
        "stock_limit": stock_limit,
        "file_count": len(part_reports),
        "total_row_count": total_row_count,
        "total_stock_count": total_stock_count,
        "failed_stock_count": len(failed_stocks),
        "failed_stocks": failed_stocks,
        "field_non_null_counts": field_non_null_counts,
        "warnings": warnings,
        "parts": part_reports,
    }


def detect_resume_parts(
    *,
    output_dir: Path,
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], str | None, int, list[str]]:
    warnings: list[str] = []
    pattern = re.compile(
        rf"^stock_complete_requirements_batch_{re.escape(start_date)}_{re.escape(end_date)}_"
        r"(?P<timestamp>\d{8}_\d{6})_part(?P<part_no>\d{2})_.*\.json$"
    )
    candidates: list[tuple[int, str, Path, dict[str, Any]]] = []
    for json_path in output_dir.glob("stock_complete_requirements_batch_*_part*.json"):
        match = pattern.match(json_path.name)
        if not match:
            continue
        try:
            report = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Resume skipped {json_path.name}: invalid JSON report: {exc}")
            continue
        csv_path = Path(report.get("output_csv", ""))
        if not csv_path.exists():
            warnings.append(f"Resume skipped {json_path.name}: output_csv does not exist")
            continue
        candidates.append((int(match.group("part_no")), match.group("timestamp"), json_path, report))

    if not candidates:
        return [], None, 1, warnings

    best_by_part_no: dict[int, tuple[str, Path, dict[str, Any]]] = {}
    for part_no, timestamp, json_path, report in candidates:
        previous = best_by_part_no.get(part_no)
        if previous is None or timestamp > previous[0]:
            best_by_part_no[part_no] = (timestamp, json_path, report)

    reports: list[dict[str, Any]] = []
    last_code: str | None = None
    next_part_no = 1
    previous_last_code: str | None = None
    loaded_timestamps: set[str] = set()
    for part_no, (timestamp, json_path, report) in sorted(best_by_part_no.items()):
        stock_range = report.get("stock_code_range", [None, None])
        first_code = clean_text(stock_range[0] if len(stock_range) >= 1 else None)
        candidate_last_code = clean_text(stock_range[1] if len(stock_range) >= 2 else None)
        if previous_last_code and first_code and first_code <= previous_last_code:
            warnings.append(
                f"Resume skipped {json_path.name}: stock range overlaps or is not after "
                f"previous loaded last stock_code={previous_last_code}"
            )
            continue
        report["report_json"] = str(json_path)
        reports.append(report)
        loaded_timestamps.add(timestamp)
        last_code = candidate_last_code or last_code
        previous_last_code = candidate_last_code or previous_last_code
        next_part_no = max(next_part_no, part_no + 1)

    if reports:
        warnings.append(
            f"Resuming from existing output: loaded {len(reports)} completed part(s) "
            f"from {len(loaded_timestamps)} timestamp group(s), "
            f"last saved stock_code={last_code}."
        )
    return reports, last_code, next_part_no, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch batched complete A-share historical datasets with AkShare and BaoStock"
    )
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="Start date in YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="End date in YYYYMMDD; clamped to latest completed trade day")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for CSV and JSON files")
    parser.add_argument("--benchmark-code", default=DEFAULT_BENCHMARK_CODE, help="Benchmark index code, e.g. sh000300")
    parser.add_argument(
        "--max-data-rows-per-file",
        type=int,
        default=MAX_DATA_ROWS_PER_FILE,
        help="Maximum number of data rows per CSV part",
    )
    parser.add_argument(
        "--stock-limit",
        type=int,
        default=None,
        help="Optional stock limit for smoke tests and sample runs",
    )
    parser.add_argument(
        "--start-after-stock-code",
        default=None,
        help="Resume manually from the first stock_code greater than this six-digit code",
    )
    parser.add_argument(
        "--resume-existing-output",
        action="store_true",
        help="Load completed part JSON files from output-dir and continue after the last saved stock_code",
    )
    parser.add_argument(
        "--financial-mode",
        choices=["akshare-batch", "baostock-quarterly"],
        default="baostock-quarterly",
        help=(
            "Financial event source mode. baostock-quarterly preserves the original field semantics; "
            "akshare-batch is experimental and should only be used after source-parity validation."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.max_data_rows_per_file <= 0:
        raise ValueError("--max-data-rows-per-file must be greater than 0")
    if args.stock_limit is not None and args.stock_limit <= 0:
        raise ValueError("--stock-limit must be greater than 0 when provided")
    if args.start_after_stock_code is not None:
        args.start_after_stock_code = normalize_stock_code(args.start_after_stock_code)

    calendar_source = "akshare.tool_trade_date_hist_sina"
    general_warnings: list[str] = []
    failed_stocks: list[dict[str, Any]] = []
    part_reports: list[dict[str, Any]] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log("Logging into BaoStock")
    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login_result.error_code} {login_result.error_msg}")

    try:
        log("Fetching trading calendar")
        calendar_df = fetch_trade_calendar()
        start_date, end_date, date_warnings = resolve_date_range(
            start_date_text=args.start_date,
            end_date_text=args.end_date,
            calendar_df=calendar_df,
        )
        general_warnings.extend(date_warnings)
        log(f"Resolved date range: {start_date} -> {end_date}")

        resume_after_code = args.start_after_stock_code
        part_no = 1
        if args.resume_existing_output:
            existing_reports, existing_last_code, next_part_no, resume_warnings = detect_resume_parts(
                output_dir=output_dir,
                start_date=start_date,
                end_date=end_date,
            )
            part_reports.extend(existing_reports)
            general_warnings.extend(resume_warnings)
            if existing_last_code:
                resume_after_code = max(
                    [code for code in [resume_after_code, existing_last_code] if code is not None]
                )
            part_no = next_part_no

        log("Fetching A-share code-name map")
        code_name_map = fetch_code_name_map()

        log("Building current listed A-share stock pool from BaoStock and AkShare intersection")
        stock_profiles = fetch_stock_pool(code_name_map)
        total_profiles = len(stock_profiles)
        if not stock_profiles:
            raise RuntimeError("No current listed A-share stocks were found in the AkShare/BaoStock intersection")

        if resume_after_code:
            before_count = len(stock_profiles)
            stock_profiles = [profile for profile in stock_profiles if profile.stock_code > resume_after_code]
            general_warnings.append(
                f"Stock pool was resumed after {resume_after_code}; "
                f"{before_count - len(stock_profiles)} stock(s) were skipped."
            )

        if args.stock_limit is not None:
            stock_profiles = stock_profiles[: args.stock_limit]
            general_warnings.append(
                f"Stock pool was limited to the first {args.stock_limit} stocks for this run."
            )

        log(f"Prepared stock pool with {len(stock_profiles)} stocks (full pool size: {total_profiles})")

        log("Fetching benchmark series")
        benchmark_df, benchmark_source, benchmark_name_source = fetch_benchmark_frame(
            args.benchmark_code,
            start_date,
            end_date,
        )
        benchmark_name = clean_text(benchmark_df["benchmark_name"].dropna().iloc[0]) or args.benchmark_code

        financial_event_map: dict[str, pd.DataFrame] | None = None
        financial_batch_source: str | None = None
        if args.financial_mode == "akshare-batch" and stock_profiles:
            general_warnings.append(
                "Financial mode akshare-batch is experimental: it is faster but is not guaranteed "
                "to preserve BaoStock quarterly field coverage/semantics unless separately validated."
            )
            log("Fetching market-wide financial events from AkShare batch endpoints")
            financial_event_map, financial_batch_source, financial_warnings = fetch_market_financial_events(
                start_date,
                end_date,
            )
            general_warnings.extend(financial_warnings)
            if not financial_event_map:
                raise RuntimeError("AkShare batch financial event fetch returned no usable rows")
            log(
                "Prepared market-wide financial event cache for "
                f"{len(financial_event_map)} stock(s)"
            )

        accumulator = PartAccumulator()
        processed_profiles = sum(int(item.get("stock_count", 0)) for item in part_reports)

        for index, profile in enumerate(stock_profiles, start=1):
            log(f"Fetching stock {index}/{len(stock_profiles)}: {profile.stock_code}")

            try:
                result = fetch_one_stock(
                    profile=profile,
                    start_date=start_date,
                    end_date=end_date,
                    benchmark_df=benchmark_df,
                    financial_event_map=financial_event_map,
                    financial_batch_source=financial_batch_source,
                )
            except Exception as exc:  # noqa: BLE001
                failed_item = {
                    "stock_code": profile.stock_code,
                    "stock_name": profile.stock_name,
                    "error": str(exc),
                }
                failed_stocks.append(failed_item)
                accumulator.add_failed_stock(failed_item)
                continue

            if len(result.frame) > args.max_data_rows_per_file:
                raise RuntimeError(
                    f"Single stock {profile.stock_code} produced {len(result.frame)} rows, exceeding "
                    f"the per-file limit {args.max_data_rows_per_file}"
                )

            if not accumulator.is_empty() and accumulator.row_count + len(result.frame) > args.max_data_rows_per_file:
                part_reports.append(
                    flush_part(
                        accumulator=accumulator,
                        part_no=part_no,
                        output_dir=output_dir,
                        start_date=start_date,
                        end_date=end_date,
                        timestamp=timestamp,
                        calendar_source=calendar_source,
                        benchmark_source=benchmark_source,
                        benchmark_name_source=benchmark_name_source,
                    )
                )
                part_no += 1
                accumulator = PartAccumulator()

            accumulator.add_result(result)
            processed_profiles += 1

        if accumulator.is_empty() and not part_reports:
            raise RuntimeError("All stock fetches failed; no output files were generated")

        if not accumulator.is_empty():
            part_reports.append(
                flush_part(
                    accumulator=accumulator,
                    part_no=part_no,
                    output_dir=output_dir,
                    start_date=start_date,
                    end_date=end_date,
                    timestamp=timestamp,
                    calendar_source=calendar_source,
                    benchmark_source=benchmark_source,
                    benchmark_name_source=benchmark_name_source,
                )
            )

        manifest = build_manifest(
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            benchmark_code=args.benchmark_code,
            benchmark_name=benchmark_name,
            total_profiles=total_profiles,
            processed_profiles=processed_profiles,
            stock_limit=args.stock_limit,
            part_reports=part_reports,
            failed_stocks=failed_stocks,
            warnings=general_warnings,
        )
        manifest_path = output_dir / f"stock_complete_requirements_batch_{start_date}_{end_date}_{timestamp}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"Manifest written to: {manifest_path}")
        log(
            "Run completed with "
            f"{manifest['file_count']} file(s), {manifest['total_stock_count']} stock(s), "
            f"{manifest['total_row_count']} row(s), {manifest['failed_stock_count']} failed stock(s)."
        )
        return 0
    finally:
        bs.logout()


if __name__ == "__main__":
    raise SystemExit(main())
