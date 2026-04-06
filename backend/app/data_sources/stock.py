from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .contracts import DatasetArtifact, ImportManifest, SourceType, now_utc_iso, write_manifest

AKSHARE_DOC_URL = "https://akshare.akfamily.xyz/data/stock/stock.html"

_COLUMN_MAP = {
    "日期": "trade_date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "change",
    "换手率": "turnover",
}


def normalize_date_arg(value: str) -> str:
    cleaned = value.replace("-", "").strip()
    if len(cleaned) != 8 or not cleaned.isdigit():
        raise ValueError(f"Expected date in YYYYMMDD or YYYY-MM-DD format, got: {value}")
    return cleaned


def normalize_adjust_arg(adjust: str) -> str:
    lowered = adjust.strip().lower()
    if lowered in {"", "none"}:
        return ""
    if lowered not in {"qfq", "hfq"}:
        raise ValueError("adjust must be one of: none, qfq, hfq")
    return lowered


def _load_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError(
            "AkShare is not installed. Run `pip install -r backend/requirements.txt` first."
        ) from exc
    return ak


def normalize_stock_frame(symbol: str, frame: pd.DataFrame, adjust: str) -> pd.DataFrame:
    renamed = frame.rename(columns=_COLUMN_MAP).copy()
    required = ["trade_date", "open", "close", "high", "low", "volume"]
    missing = [column for column in required if column not in renamed.columns]
    if missing:
        raise ValueError(f"AkShare response for {symbol} is missing columns: {missing}")

    renamed["trade_date"] = pd.to_datetime(renamed["trade_date"]).dt.strftime("%Y-%m-%d")
    renamed["symbol"] = symbol
    renamed["adjust"] = adjust or "none"
    renamed["source_type"] = SourceType.API.value

    ordered = [
        "symbol",
        "trade_date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "amplitude",
        "pct_change",
        "change",
        "turnover",
        "adjust",
        "source_type",
    ]
    ordered_existing = [column for column in ordered if column in renamed.columns]
    extras = [column for column in renamed.columns if column not in ordered_existing]

    normalized = (
        renamed[ordered_existing + extras]
        .sort_values("trade_date")
        .drop_duplicates(subset=["symbol", "trade_date"])
        .reset_index(drop=True)
    )
    return normalized


def fetch_daily_history(symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
    ak = _load_akshare()
    compact_start = normalize_date_arg(start_date)
    compact_end = normalize_date_arg(end_date)
    normalized_adjust = normalize_adjust_arg(adjust)
    frame = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=compact_start,
        end_date=compact_end,
        adjust=normalized_adjust,
    )
    if frame.empty:
        raise ValueError(f"No data returned for symbol={symbol}")
    return normalize_stock_frame(symbol=symbol, frame=frame, adjust=normalized_adjust or "none")


def fetch_daily_histories(
    symbols: Iterable[str],
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        result[symbol] = fetch_daily_history(symbol=symbol, start_date=start_date, end_date=end_date, adjust=adjust)
    return result


def write_daily_histories(
    frames: dict[str, pd.DataFrame],
    output_dir: Path,
    start_date: str,
    end_date: str,
    adjust: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[DatasetArtifact] = []
    combined_columns: set[str] = set()
    total_rows = 0

    for symbol, frame in frames.items():
        file_name = f"{symbol}_daily_{normalize_date_arg(start_date)}_{normalize_date_arg(end_date)}_{adjust or 'none'}.csv"
        symbol_dir = output_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        file_path = symbol_dir / file_name
        frame.to_csv(file_path, index=False, encoding="utf-8-sig")

        artifacts.append(
            DatasetArtifact(
                name=symbol,
                path=str(file_path),
                rows=len(frame),
                columns=list(frame.columns),
            )
        )
        total_rows += len(frame)
        combined_columns.update(frame.columns)

    manifest = ImportManifest(
        dataset_name="akshare_a_share_daily",
        source_type=SourceType.API,
        source_name="akshare.stock_zh_a_hist",
        source_uri=AKSHARE_DOC_URL,
        created_at=now_utc_iso(),
        record_count=total_rows,
        columns=sorted(combined_columns),
        artifacts=artifacts,
        metadata={
            "symbols": list(frames.keys()),
            "start_date": normalize_date_arg(start_date),
            "end_date": normalize_date_arg(end_date),
            "adjust": adjust or "none",
        },
    )
    return write_manifest(manifest, output_dir / "akshare_daily_manifest.json")
