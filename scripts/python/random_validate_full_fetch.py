# -*- coding: utf-8 -*-
"""
Randomly re-fetch a small A-share sample and compare it with the full batch.

The sample is built as random stock-code windows instead of arbitrary scattered
dates. This keeps upstream API traffic bounded while still checking many fields
against the previously generated full dataset.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import baostock as bs
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fetch_stock_complete_requirements_batch import (  # noqa: E402
    ALL_COLUMNS,
    StockProfile,
    build_stock_frame,
    fetch_baostock_daily,
    fetch_benchmark_frame,
    build_financial_event_frame,
    build_share_market_value_frame,
    clean_text,
    fetch_akshare_daily,
    log,
    normalize_stock_code,
)


DEFAULT_FULL_DIR = Path(r"D:\graduation-project\data\row\fetch")
DEFAULT_OUTPUT_DIR = Path(r"D:\graduation-project\data\row\fetch-random")
DEFAULT_BENCHMARK_CODE = "sh000300"
NUMERIC_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover_rate",
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
    "bs_preclose",
    "bs_turn",
    "bs_pct_chg",
    "bs_pe_ttm",
    "bs_pb_mrq",
    "bs_ps_ttm",
    "bs_pcf_ncf_ttm",
]
KEY_COLUMNS = ["stock_code", "trade_date"]


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_manifest(full_dir: Path) -> dict[str, Any]:
    manifest_path = full_dir / "ZZZmanifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def manifest_csv_paths(manifest: dict[str, Any], full_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for part in manifest.get("parts", []):
        raw_path = part.get("output_csv")
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = full_dir / path
        if path.exists():
            paths.append(path)
    if not paths:
        paths = sorted(full_dir.glob("stock_complete_requirements_batch_*.csv"))
    if not paths:
        raise FileNotFoundError(f"No full CSV parts found under {full_dir}")
    return paths


def collect_stock_profiles(csv_paths: list[Path]) -> dict[str, StockProfile]:
    profiles: dict[str, StockProfile] = {}
    usecols = ["stock_code", "stock_name", "bs_code", "bs_ipo_date", "bs_out_date", "bs_status"]
    for csv_path in csv_paths:
        for chunk in pd.read_csv(csv_path, usecols=usecols, dtype=str, chunksize=200_000):
            chunk = chunk.dropna(subset=["stock_code"])
            chunk = chunk.drop_duplicates(subset=["stock_code"], keep="last")
            for row in chunk.itertuples(index=False):
                stock_code = normalize_stock_code(row.stock_code)
                if stock_code in profiles:
                    continue
                bs_code = clean_text(row.bs_code)
                if not bs_code:
                    prefix = "sh" if stock_code.startswith(("5", "6", "9")) else "bj" if stock_code.startswith(("4", "8")) else "sz"
                    bs_code = f"{prefix}.{stock_code}"
                profiles[stock_code] = StockProfile(
                    stock_code=stock_code,
                    bs_code=bs_code,
                    stock_name=clean_text(row.stock_name),
                    ipo_date=clean_text(row.bs_ipo_date),
                    out_date=clean_text(row.bs_out_date),
                    status=clean_text(row.bs_status),
                )
    if not profiles:
        raise RuntimeError("No stock profiles could be read from full CSV parts")
    return dict(sorted(profiles.items()))


def load_rows_for_stocks(csv_paths: list[Path], stock_codes: set[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    dtype = {column: "string" for column in ["stock_code", "stock_name", "data_source", "bs_code", "bs_adjustflag", "bs_tradestatus", "bs_status"]}
    for csv_path in csv_paths:
        for chunk in pd.read_csv(csv_path, dtype=dtype, chunksize=120_000):
            chunk["stock_code"] = chunk["stock_code"].astype(str).str.extract(r"(\d{6})", expand=False)
            matched = chunk[chunk["stock_code"].isin(stock_codes)].copy()
            if not matched.empty:
                frames.append(matched)
    if not frames:
        raise RuntimeError("Selected stock codes were not found in the full CSV parts")
    frame = pd.concat(frames, ignore_index=True)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame = frame[frame["trade_date"].notna()].copy()
    frame.drop_duplicates(subset=KEY_COLUMNS, keep="last", inplace=True)
    frame.sort_values(KEY_COLUMNS, inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame


def pick_windows(
    *,
    profiles: dict[str, StockProfile],
    csv_paths: list[Path],
    seed: int,
    stock_count: int,
    window_trade_days: int,
    max_rows: int,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rng = random.Random(seed)
    stock_codes = list(profiles)
    rng.shuffle(stock_codes)
    selected_codes = set(stock_codes[: min(stock_count * 3, len(stock_codes))])
    candidate_rows = load_rows_for_stocks(csv_paths, selected_codes)

    windows: list[dict[str, Any]] = []
    sampled_frames: list[pd.DataFrame] = []
    total_rows = 0
    for stock_code in stock_codes:
        stock_rows = candidate_rows[candidate_rows["stock_code"] == stock_code].sort_values("trade_date")
        if len(stock_rows) < 5:
            continue
        window_len = min(window_trade_days, len(stock_rows), max_rows - total_rows)
        if window_len <= 0:
            break
        start_offset = rng.randint(0, len(stock_rows) - window_len)
        window_rows = stock_rows.iloc[start_offset : start_offset + window_len].copy()
        sampled_frames.append(window_rows)
        total_rows += len(window_rows)
        windows.append(
            {
                "stock_code": stock_code,
                "stock_name": profiles[stock_code].stock_name,
                "bs_code": profiles[stock_code].bs_code,
                "start_date": window_rows["trade_date"].min(),
                "end_date": window_rows["trade_date"].max(),
                "row_count": int(len(window_rows)),
            }
        )
        if len(windows) >= stock_count or total_rows >= max_rows:
            break

    if not sampled_frames:
        raise RuntimeError("Unable to build a random sample from the full dataset")
    sample_frame = pd.concat(sampled_frames, ignore_index=True)
    sample_frame.sort_values(KEY_COLUMNS, inplace=True)
    sample_frame.reset_index(drop=True, inplace=True)
    return windows, sample_frame


def fetch_random_windows(
    *,
    windows: list[dict[str, Any]],
    profiles: dict[str, StockProfile],
    benchmark_code: str,
    financial_context_start_date: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[str], Counter[str]]:
    fetched_frames: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    warnings: list[str] = []
    source_counts: Counter[str] = Counter()

    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {login_result.error_code} {login_result.error_msg}")

    try:
        for idx, window in enumerate(windows, start=1):
            stock_code = window["stock_code"]
            profile = profiles[stock_code]
            start_yyyymmdd = str(window["start_date"]).replace("-", "")
            end_yyyymmdd = str(window["end_date"]).replace("-", "")
            log(f"Re-fetching sample {idx}/{len(windows)}: {stock_code} {start_yyyymmdd}->{end_yyyymmdd}")

            try:
                benchmark_df, benchmark_source, _ = fetch_benchmark_frame(
                    benchmark_code,
                    start_yyyymmdd,
                    end_yyyymmdd,
                )
                try:
                    daily_df = fetch_baostock_daily(profile, start_yyyymmdd, end_yyyymmdd)
                    daily_source = "baostock.query_history_k_data_plus"
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"{stock_code}: BaoStock daily failed, AkShare fallback used: {exc}")
                    daily_df, daily_source = fetch_akshare_daily(stock_code, start_yyyymmdd, end_yyyymmdd)

                share_df, market_source, market_warnings = build_share_market_value_frame(
                    stock_code,
                    daily_df,
                    start_yyyymmdd,
                    end_yyyymmdd,
                )
                try:
                    financial_context_daily = fetch_baostock_daily(
                        profile,
                        financial_context_start_date,
                        end_yyyymmdd,
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"{stock_code}: BaoStock financial context failed, AkShare fallback used: {exc}")
                    financial_context_daily, _ = fetch_akshare_daily(
                        stock_code,
                        financial_context_start_date,
                        end_yyyymmdd,
                    )
                financial_df, financial_source, financial_warnings = build_financial_event_frame(
                    profile,
                    financial_context_daily,
                    financial_context_start_date,
                    end_yyyymmdd,
                )
                if not financial_df.empty:
                    financial_df = financial_df[
                        (financial_df["trade_date"] >= pd.to_datetime(start_yyyymmdd))
                        & (financial_df["trade_date"] <= pd.to_datetime(end_yyyymmdd))
                    ].copy()
                warnings.extend(market_warnings)
                warnings.extend(financial_warnings)
                frame = build_stock_frame(
                    profile=profile,
                    daily_df=daily_df,
                    daily_source=daily_source,
                    benchmark_df=benchmark_df,
                    share_market_value_df=share_df,
                    financial_event_df=financial_df,
                )
                frame = frame[
                    (frame["trade_date"] >= window["start_date"])
                    & (frame["trade_date"] <= window["end_date"])
                ].copy()
                fetched_frames.append(frame)
                source_counts[daily_source] += 1
                source_counts[benchmark_source] += 1
                if market_source:
                    source_counts[market_source] += 1
                if financial_source:
                    source_counts[financial_source] += 1
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "stock_code": stock_code,
                        "start_date": window["start_date"],
                        "end_date": window["end_date"],
                        "error": str(exc),
                    }
                )
    finally:
        bs.logout()

    if fetched_frames:
        fetched = pd.concat(fetched_frames, ignore_index=True)
        fetched.drop_duplicates(subset=KEY_COLUMNS, keep="last", inplace=True)
        fetched.sort_values(KEY_COLUMNS, inplace=True)
        fetched.reset_index(drop=True, inplace=True)
    else:
        fetched = pd.DataFrame(columns=ALL_COLUMNS)
    return fetched, failures, warnings, source_counts


def values_equal(left: Any, right: Any, column: str, abs_tol: float, rel_tol: float) -> tuple[bool, float | None]:
    left_missing = pd.isna(left) or str(left).strip() == ""
    right_missing = pd.isna(right) or str(right).strip() == ""
    if left_missing and right_missing:
        return True, None
    if left_missing != right_missing:
        return False, None

    if column in NUMERIC_COLUMNS:
        left_num = pd.to_numeric(pd.Series([left]), errors="coerce").iloc[0]
        right_num = pd.to_numeric(pd.Series([right]), errors="coerce").iloc[0]
        if pd.isna(left_num) and pd.isna(right_num):
            return True, None
        if pd.isna(left_num) != pd.isna(right_num):
            return False, None
        diff = float(left_num) - float(right_num)
        scale = max(abs(float(left_num)), abs(float(right_num)), 1.0)
        return abs(diff) <= max(abs_tol, rel_tol * scale), diff

    return str(left).strip() == str(right).strip(), None


def compare_frames(
    *,
    full_sample: pd.DataFrame,
    refetched: pd.DataFrame,
    columns: list[str],
    abs_tol: float,
    rel_tol: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    full_indexed = full_sample.set_index(KEY_COLUMNS, drop=False)
    refetched_indexed = refetched.set_index(KEY_COLUMNS, drop=False)
    full_keys = set(full_indexed.index)
    refetched_keys = set(refetched_indexed.index)
    common_keys = sorted(full_keys & refetched_keys)

    differences: list[dict[str, Any]] = []
    for key in common_keys:
        full_row = full_indexed.loc[key]
        new_row = refetched_indexed.loc[key]
        for column in columns:
            if column in KEY_COLUMNS:
                continue
            if column not in full_row.index or column not in new_row.index:
                continue
            equal, diff = values_equal(full_row[column], new_row[column], column, abs_tol, rel_tol)
            if not equal:
                differences.append(
                    {
                        "stock_code": key[0],
                        "trade_date": key[1],
                        "column": column,
                        "full_value": to_jsonable(full_row[column]),
                        "refetched_value": to_jsonable(new_row[column]),
                        "numeric_diff": diff,
                    }
                )

    diff_df = pd.DataFrame(differences)
    summary = {
        "full_sample_rows": int(len(full_sample)),
        "refetched_rows": int(len(refetched)),
        "common_rows": int(len(common_keys)),
        "missing_in_refetch_rows": int(len(full_keys - refetched_keys)),
        "extra_in_refetch_rows": int(len(refetched_keys - full_keys)),
        "different_cells": int(len(diff_df)),
        "different_rows": int(diff_df[KEY_COLUMNS].drop_duplicates().shape[0]) if not diff_df.empty else 0,
        "different_columns": dict(diff_df["column"].value_counts()) if not diff_df.empty else {},
    }
    return diff_df, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-dir", type=Path, default=DEFAULT_FULL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=20260426)
    parser.add_argument("--stock-count", type=int, default=20)
    parser.add_argument("--window-trade-days", type=int, default=80)
    parser.add_argument("--max-rows", type=int, default=50_000)
    parser.add_argument("--benchmark-code", default=DEFAULT_BENCHMARK_CODE)
    parser.add_argument(
        "--financial-context-start-date",
        default=None,
        help="Start date used to map financial announcement dates; defaults to manifest date_range[0].",
    )
    parser.add_argument("--abs-tol", type=float, default=1e-6)
    parser.add_argument("--rel-tol", type=float, default=1e-8)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_dir / f"random_validate_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    log("Reading full manifest and stock profiles")
    manifest = read_manifest(args.full_dir)
    financial_context_start_date = args.financial_context_start_date or manifest.get("date_range", ["20160101"])[0]
    csv_paths = manifest_csv_paths(manifest, args.full_dir)
    profiles = collect_stock_profiles(csv_paths)

    log("Building random stock/date windows from full data")
    windows, full_sample = pick_windows(
        profiles=profiles,
        csv_paths=csv_paths,
        seed=args.seed,
        stock_count=args.stock_count,
        window_trade_days=args.window_trade_days,
        max_rows=args.max_rows,
    )
    full_sample_path = run_dir / "full_sample_rows.csv"
    full_sample.to_csv(full_sample_path, index=False, encoding="utf-8-sig")
    (run_dir / "sample_windows.json").write_text(
        json.dumps(windows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log(f"Re-fetching {len(windows)} random windows, target sample rows={len(full_sample)}")
    refetched, failures, warnings, source_counts = fetch_random_windows(
        windows=windows,
        profiles=profiles,
        benchmark_code=args.benchmark_code,
        financial_context_start_date=financial_context_start_date,
    )
    refetched_path = run_dir / "refetched_rows.csv"
    refetched.to_csv(refetched_path, index=False, encoding="utf-8-sig")

    common_columns = [column for column in ALL_COLUMNS if column in full_sample.columns and column in refetched.columns]
    diff_df, compare_summary = compare_frames(
        full_sample=full_sample,
        refetched=refetched,
        columns=common_columns,
        abs_tol=args.abs_tol,
        rel_tol=args.rel_tol,
    )
    diff_path = run_dir / "differences.csv"
    diff_df.to_csv(diff_path, index=False, encoding="utf-8-sig")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "seed": args.seed,
        "full_dir": str(args.full_dir),
        "output_dir": str(run_dir),
        "manifest_failed_stock_count": manifest.get("failed_stock_count"),
        "financial_context_start_date": financial_context_start_date,
        "sample_window_count": len(windows),
        "sample_windows": windows,
        "refetch_failures": failures,
        "warnings": warnings,
        "source_counts": dict(source_counts),
        "comparison": compare_summary,
        "paths": {
            "full_sample_rows": str(full_sample_path),
            "refetched_rows": str(refetched_path),
            "differences": str(diff_path),
            "sample_windows": str(run_dir / "sample_windows.json"),
            "summary": str(run_dir / "summary.json"),
        },
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=to_jsonable),
        encoding="utf-8",
    )

    log(f"Comparison finished. different_cells={compare_summary['different_cells']}, run_dir={run_dir}")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
