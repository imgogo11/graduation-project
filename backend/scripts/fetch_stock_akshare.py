# 作用:
# - 这是 A 股日线抓取脚本的命令行入口，负责解析股票代码、日期区间和复权参数，
#   并触发 AkShare 数据抓取与结果写盘。
# 关联文件:
# - 直接导入 backend/scripts/_bootstrap.py，用来准备 backend 的导入路径。
# - 直接调用 backend/app/data_sources/stock.py 中的 fetch_daily_histories 和 write_daily_histories。
# - 生成的 CSV 和 manifest 由 backend/app/data_sources/contracts.py 的契约结构约束。
#
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from _bootstrap import ensure_backend_on_path

_, REPO_ROOT = ensure_backend_on_path()

from app.data_sources.stock import fetch_daily_histories, write_daily_histories


def main() -> int:
    today = date.today()
    default_start = (today - timedelta(days=730)).strftime("%Y%m%d")
    default_end = today.strftime("%Y%m%d")

    parser = argparse.ArgumentParser(description="Fetch A-share daily snapshots with AkShare.")
    parser.add_argument("--symbols", nargs="+", required=True, help="A-share symbols, e.g. 000001 600519 300750")
    parser.add_argument("--start-date", default=default_start, help="Start date in YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--end-date", default=default_end, help="End date in YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--adjust", choices=["none", "qfq", "hfq"], default="qfq", help="Price adjustment mode")
    parser.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "data" / "raw" / "stocks" / "akshare"),
        help="Directory for CSV snapshots and manifest",
    )
    args = parser.parse_args()

    frames = fetch_daily_histories(
        symbols=args.symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        adjust=args.adjust,
    )
    manifest_path = write_daily_histories(
        frames=frames,
        output_dir=Path(args.out_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        adjust=args.adjust,
    )
    total_rows = sum(len(frame) for frame in frames.values())
    print(f"Fetched {len(frames)} symbols and {total_rows} rows.")
    print(f"Manifest written to: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
