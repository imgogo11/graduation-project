# -*- coding: utf-8 -*-
"""
用途：导出单只 A 股的“历史日线”数据（非实时快照），输出固定 OHLCV 风格列。

主数据源：akshare.stock_zh_a_hist（东方财富）
补充数据源：akshare.stock_zh_a_daily（新浪，补充流通股本/换手率小数）

输出路径默认：D:\\graduation-project\\data\\row\\
输出编码：utf-8-sig（兼容中文 Excel）
"""

from __future__ import annotations

import argparse
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd

DEFAULT_OUTPUT_DIR = Path(r"D:\graduation-project\data\row")
DEFAULT_START_DATE = "20000101"


def log(message: str) -> None:
    """打印带时间戳的日志。"""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}")


def normalize_symbol(symbol: str) -> str:
    """将输入标准化为 6 位股票代码。"""
    text = str(symbol).strip()
    match = re.search(r"(\d{6})", text)
    if not match:
        raise ValueError(f"无效股票代码: {symbol}")
    return match.group(1)


def to_sina_symbol(symbol_6: str) -> str:
    """将 6 位代码转为新浪代码格式（sh/sz 前缀）。"""
    if symbol_6.startswith(("5", "6", "9")):
        return f"sh{symbol_6}"
    return f"sz{symbol_6}"


def safe_call(api_name: str, retries: int = 3, sleep_seconds: float = 0.8, **kwargs) -> Optional[pd.DataFrame]:
    """调用 akshare 接口并自动重试，失败时返回 None。"""
    api = getattr(ak, api_name, None)
    if api is None:
        log(f"[WARN] akshare 未找到接口: {api_name}")
        return None

    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            data = api(**kwargs)
            if isinstance(data, pd.DataFrame):
                return data
            return None
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)

    log(f"[WARN] {api_name} 调用失败: kwargs={kwargs}, error={last_error}")
    return None


def fetch_em_daily(symbol_6: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
    """从东方财富获取历史日线数据（字段更丰富）。"""
    em_df = safe_call(
        "stock_zh_a_hist",
        symbol=symbol_6,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
    if em_df is None or em_df.empty:
        raise RuntimeError("stock_zh_a_hist 未返回有效数据")

    rename_map = {
        "日期": "date",
        "股票代码": "symbol",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude_pct",
        "涨跌幅": "change_pct",
        "涨跌额": "change_amount",
        "换手率": "turnover_rate_pct",
    }

    out = em_df.rename(columns=rename_map).copy()
    if "symbol" not in out.columns:
        out["symbol"] = symbol_6

    out["symbol"] = out["symbol"].astype(str).map(normalize_symbol)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out[out["date"].notna()].copy()

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "amplitude_pct",
        "change_pct",
        "change_amount",
        "turnover_rate_pct",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["data_source"] = "stock_zh_a_hist"
    out["adjust_type"] = "none" if adjust == "" else adjust
    return out


def fetch_sina_daily(symbol_6: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从新浪获取历史日线数据（作为回退源，或补充扩展列）。"""
    sina_df = safe_call(
        "stock_zh_a_daily",
        symbol=to_sina_symbol(symbol_6),
        start_date=start_date,
        end_date=end_date,
    )
    if sina_df is None or sina_df.empty:
        raise RuntimeError("stock_zh_a_daily 未返回有效数据")

    out = sina_df.copy()
    out["symbol"] = symbol_6
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out[out["date"].notna()].copy()

    for col in ["open", "high", "low", "close", "volume", "amount", "outstanding_share", "turnover"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "turnover" in out.columns:
        out["turnover_decimal"] = out["turnover"]

    out["data_source"] = "stock_zh_a_daily"
    out["adjust_type"] = "none"
    return out


def fetch_daily_extras_from_sina(symbol_6: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从新浪提取扩展列（date + outstanding_share + turnover_decimal）。"""
    extra = safe_call(
        "stock_zh_a_daily",
        symbol=to_sina_symbol(symbol_6),
        start_date=start_date,
        end_date=end_date,
    )
    if extra is None or extra.empty:
        return pd.DataFrame(columns=["date"])

    keep_cols = ["date"]
    if "outstanding_share" in extra.columns:
        keep_cols.append("outstanding_share")
    if "turnover" in extra.columns:
        keep_cols.append("turnover")

    out = extra[keep_cols].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out[out["date"].notna()].copy()

    if "turnover" in out.columns:
        out.rename(columns={"turnover": "turnover_decimal"}, inplace=True)

    for col in ["outstanding_share", "turnover_decimal"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out.drop_duplicates(subset=["date"], keep="last", inplace=True)
    return out


def build_final_dataframe(df: pd.DataFrame, symbol_6: str) -> pd.DataFrame:
    """整理最终输出：固定列顺序 + 类型 + 去重。"""
    fixed_cols = [
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "amplitude_pct",
        "change_pct",
        "change_amount",
        "turnover_rate_pct",
        "outstanding_share",
        "turnover_decimal",
        "adjust_type",
        "data_source",
    ]

    out = df.copy()
    for col in fixed_cols:
        if col not in out.columns:
            out[col] = pd.NA

    out["symbol"] = symbol_6
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out[out["date"].notna()].copy()

    out.sort_values("date", inplace=True)
    out.drop_duplicates(subset=["date"], keep="last", inplace=True)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")

    # 将固定列放前面，防止列顺序漂移
    extra_cols = [c for c in out.columns if c not in fixed_cols]
    out = out[fixed_cols + extra_cols]
    out.reset_index(drop=True, inplace=True)
    return out


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="导出单只股票历史日线数据（OHLCV+扩展）")
    parser.add_argument("--symbol", required=True, help="股票代码，例如 000001 或 sz000001")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="开始日期，格式 YYYYMMDD")
    parser.add_argument(
        "--end-date",
        default=datetime.now().strftime("%Y%m%d"),
        help="结束日期，格式 YYYYMMDD，默认今天",
    )
    parser.add_argument(
        "--adjust",
        choices=["none", "qfq", "hfq"],
        default="none",
        help="复权类型：none(不复权)/qfq(前复权)/hfq(后复权)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="输出目录，默认 D:\\graduation-project\\data\\row",
    )
    parser.add_argument(
        "--output-prefix",
        default="stock_daily",
        help="输出文件名前缀，默认 stock_daily",
    )
    return parser.parse_args()


def main() -> int:
    """主流程。"""
    args = parse_args()

    symbol_6 = normalize_symbol(args.symbol)
    start_date = args.start_date.strip()
    end_date = args.end_date.strip()
    adjust = "" if args.adjust == "none" else args.adjust

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log(f"开始获取历史日线: symbol={symbol_6}, start={start_date}, end={end_date}, adjust={args.adjust}")

    # 优先使用字段更丰富的东方财富；失败则回退新浪历史日线
    try:
        base_df = fetch_em_daily(symbol_6, start_date, end_date, adjust)
        extras_df = fetch_daily_extras_from_sina(symbol_6, start_date, end_date)
        if not extras_df.empty:
            base_df = base_df.merge(extras_df, on="date", how="left")
            log("已并入新浪扩展列: outstanding_share / turnover_decimal")
    except Exception as em_error:  # noqa: BLE001
        log(f"[WARN] 东方财富日线不可用，回退新浪日线。原因: {em_error}")
        base_df = fetch_sina_daily(symbol_6, start_date, end_date)
        if args.adjust != "none":
            log("[WARN] 当前回退到新浪日线，复权参数不生效，实际导出为不复权。")

    final_df = build_final_dataframe(base_df, symbol_6)
    if final_df.empty:
        raise RuntimeError("结果为空：请检查股票代码或日期范围。")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    main_name = f"{args.output_prefix}_{symbol_6}_{start_date}_{end_date}_{args.adjust}_{ts}.csv"
    latest_name = f"{args.output_prefix}_{symbol_6}_latest.csv"

    out_file = output_dir / main_name
    latest_file = output_dir / latest_name

    final_df.to_csv(out_file, index=False, encoding="utf-8-sig")
    final_df.to_csv(latest_file, index=False, encoding="utf-8-sig")

    log(f"导出完成: {out_file}")
    log(f"同步 latest: {latest_file}")
    log(f"数据规模: rows={len(final_df)}, cols={len(final_df.columns)}")
    log(f"固定列: {list(final_df.columns[:16])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("[ERROR] 用户中断执行")
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        log(f"[ERROR] 执行失败: {exc}")
        raise SystemExit(1)
