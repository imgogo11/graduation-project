from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import random
from statistics import mean
import time

from sqlalchemy import delete, insert, text

from _bootstrap import ensure_backend_on_path


BACKEND_DIR, REPO_ROOT = ensure_backend_on_path()

from app.core.config import get_settings
from app.core.database import create_all_tables, get_engine, get_session_factory
from app.engine_bridge.adapters.trading import load_algo_engine_module
from app.engine_bridge.loaders.trading import scale_amount, scale_volume
from app.engine_bridge.tdigest import RangeKthTDigestBlockIndex
from app.models import ImportRun, TradingRecord, utc_now
from app.repositories.imports import CURRENT_IMPORT_SOURCE_NAME, CURRENT_IMPORT_SOURCE_TYPE
from benchmark_joint_anomaly_ranking import build_synthetic_trading_rows, benchmark_run, resolve_sample


try:
    import psutil
except ImportError as exc:
    raise SystemExit("psutil is required for benchmark memory sampling. Install backend/requirements-optional.txt.") from exc


SQL_MAX_QUERY = text(
    """
    SELECT MAX(amount)
    FROM trading_records
    WHERE import_run_id = :import_run_id
      AND instrument_code = :instrument_code
      AND trade_date BETWEEN :start_date AND :end_date
    """
)

SQL_KTH_QUERY = text(
    """
    SELECT volume
    FROM trading_records
    WHERE import_run_id = :import_run_id
      AND instrument_code = :instrument_code
      AND trade_date BETWEEN :start_date AND :end_date
    ORDER BY volume DESC
    LIMIT 1 OFFSET :offset
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local algorithm benchmark suite and write JSON/CSV artifacts.")
    parser.add_argument("--sample", choices=["300x480", "1000x480", "3000x480"], default="300x480")
    parser.add_argument("--seed", type=int, default=20260411)
    parser.add_argument("--output-dir", type=Path, help="Optional explicit output directory.")
    parser.add_argument("--keep-data", action="store_true", help="Keep the generated benchmark run in the database.")
    return parser.parse_args()


def build_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return args.output_dir.resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (REPO_ROOT / "docs" / "benchmarks" / timestamp).resolve()


def create_benchmark_run(session, *, instruments: int, days: int, row_count: int) -> ImportRun:
    timestamp = utc_now()
    run = ImportRun(
        owner_user_id=None,
        dataset_name=f"algo_suite_{instruments}x{days}_{int(timestamp.timestamp())}",
        source_type=CURRENT_IMPORT_SOURCE_TYPE,
        source_name=CURRENT_IMPORT_SOURCE_NAME,
        source_uri=f"benchmark://algo-suite/{instruments}x{days}",
        original_file_name=None,
        file_format="synthetic",
        status="completed",
        started_at=timestamp,
        completed_at=timestamp,
        record_count=row_count,
        metadata_json={"benchmark": "algo_suite"},
    )
    session.add(run)
    session.flush()
    return run


def insert_benchmark_rows(session, *, import_run_id: int, rows: list[dict[str, object]]) -> None:
    session.execute(insert(TradingRecord), [{"import_run_id": import_run_id, **row} for row in rows])


def cleanup_benchmark_run(session, *, import_run_id: int) -> None:
    session.execute(delete(TradingRecord).where(TradingRecord.import_run_id == import_run_id))
    session.execute(delete(ImportRun).where(ImportRun.id == import_run_id))


def build_query_windows(dates: list, *, total: int, seed: int) -> list[tuple[object, object, int]]:
    rng = random.Random(seed)
    windows: list[tuple[object, object, int]] = []
    n = len(dates)
    for _ in range(total):
        left = rng.randrange(0, max(1, n - 5))
        right = rng.randrange(left, n)
        interval_length = right - left + 1
        k = rng.randint(1, interval_length)
        windows.append((dates[left], dates[right], k))
    return windows


def rss_mb() -> float:
    return float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    output_dir = build_output_dir(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample = resolve_sample(argparse.Namespace(sample=args.sample, instruments=None, days=None))
    settings = get_settings()

    create_all_tables()
    engine = get_engine()
    session_factory = get_session_factory()
    rows = build_synthetic_trading_rows(instruments=sample.instruments, days=sample.days, seed=args.seed)
    module = load_algo_engine_module()

    timing_rows: list[dict[str, object]] = []
    memory_rows: list[dict[str, object]] = []
    summary: dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "database_url": settings.database_url,
        "sample": f"{sample.instruments}x{sample.days}",
        "row_count": len(rows),
    }

    with session_factory() as session:
        run = create_benchmark_run(
            session,
            instruments=sample.instruments,
            days=sample.days,
            row_count=len(rows),
        )
        insert_benchmark_rows(session, import_run_id=run.id, rows=rows)
        session.commit()

        instrument_rows = [row for row in rows if row["instrument_code"] == "SYM00000"]
        dates = [row["trade_date"] for row in instrument_rows]
        amounts_scaled = [scale_amount(row["amount"]) for row in instrument_rows]
        volumes_scaled = [scale_volume(row["volume"]) for row in instrument_rows]
        windows = build_query_windows(dates, total=1000, seed=args.seed + 1)

        before_segment = rss_mb()
        segment_tree = module.RangeMaxSegmentTree(amounts_scaled)
        after_segment = rss_mb()
        memory_rows.append({"scenario": "range_max_segment_tree", "phase": "build", "rss_mb": round(after_segment - before_segment, 4)})

        before_kth = rss_mb()
        kth_tree = module.RangeKthPersistentSegmentTree(volumes_scaled)
        after_kth = rss_mb()
        memory_rows.append({"scenario": "persistent_segment_tree", "phase": "build", "rss_mb": round(after_kth - before_kth, 4)})

        before_digest = rss_mb()
        digest_index = RangeKthTDigestBlockIndex(volumes_scaled)
        after_digest = rss_mb()
        memory_rows.append({"scenario": "t_digest", "phase": "build", "rss_mb": round(after_digest - before_digest, 4)})

        start_date, end_date, first_k = windows[0]

        started = time.perf_counter()
        session.execute(
            SQL_MAX_QUERY,
            {"import_run_id": run.id, "instrument_code": "SYM00000", "start_date": start_date, "end_date": end_date},
        ).scalar_one()
        timing_rows.append({"scenario": "range_max_segment_tree", "mode": "sql_cold", "batch_queries": 1, "seconds": round(time.perf_counter() - started, 6)})

        started = time.perf_counter()
        cold_segment_tree = module.RangeMaxSegmentTree(amounts_scaled)
        cold_segment_tree.query_inclusive(dates.index(start_date), dates.index(end_date))
        timing_rows.append({"scenario": "range_max_segment_tree", "mode": "algo_cold", "batch_queries": 1, "seconds": round(time.perf_counter() - started, 6)})

        for batch_queries in (10, 100, 1000):
            started = time.perf_counter()
            for query_start, query_end, _ in windows[:batch_queries]:
                session.execute(
                    SQL_MAX_QUERY,
                    {"import_run_id": run.id, "instrument_code": "SYM00000", "start_date": query_start, "end_date": query_end},
                ).scalar_one()
            timing_rows.append({"scenario": "range_max_segment_tree", "mode": "sql_batch", "batch_queries": batch_queries, "seconds": round(time.perf_counter() - started, 6)})

            started = time.perf_counter()
            for query_start, query_end, _ in windows[:batch_queries]:
                segment_tree.query_inclusive(dates.index(query_start), dates.index(query_end))
            timing_rows.append({"scenario": "range_max_segment_tree", "mode": "algo_hot", "batch_queries": batch_queries, "seconds": round(time.perf_counter() - started, 6)})

        started = time.perf_counter()
        session.execute(
            SQL_KTH_QUERY,
            {
                "import_run_id": run.id,
                "instrument_code": "SYM00000",
                "start_date": start_date,
                "end_date": end_date,
                "offset": first_k - 1,
            },
        ).scalar_one()
        timing_rows.append({"scenario": "persistent_segment_tree", "mode": "sql_cold", "batch_queries": 1, "seconds": round(time.perf_counter() - started, 6)})

        started = time.perf_counter()
        cold_kth_tree = module.RangeKthPersistentSegmentTree(volumes_scaled)
        cold_kth_tree.query_inclusive(dates.index(start_date), dates.index(end_date), first_k)
        timing_rows.append({"scenario": "persistent_segment_tree", "mode": "algo_cold", "batch_queries": 1, "seconds": round(time.perf_counter() - started, 6)})

        for batch_queries in (10, 100, 1000):
            started = time.perf_counter()
            for query_start, query_end, kth in windows[:batch_queries]:
                session.execute(
                    SQL_KTH_QUERY,
                    {
                        "import_run_id": run.id,
                        "instrument_code": "SYM00000",
                        "start_date": query_start,
                        "end_date": query_end,
                        "offset": kth - 1,
                    },
                ).scalar_one()
            timing_rows.append({"scenario": "persistent_segment_tree", "mode": "sql_batch", "batch_queries": batch_queries, "seconds": round(time.perf_counter() - started, 6)})

            started = time.perf_counter()
            for query_start, query_end, kth in windows[:batch_queries]:
                kth_tree.query_inclusive(dates.index(query_start), dates.index(query_end), kth)
            timing_rows.append({"scenario": "persistent_segment_tree", "mode": "algo_hot", "batch_queries": batch_queries, "seconds": round(time.perf_counter() - started, 6)})

        started = time.perf_counter()
        cold_digest = RangeKthTDigestBlockIndex(volumes_scaled)
        cold_digest.query_inclusive(dates.index(start_date), dates.index(end_date), first_k)
        timing_rows.append({"scenario": "t_digest", "mode": "algo_cold", "batch_queries": 1, "seconds": round(time.perf_counter() - started, 6)})

        abs_errors: list[float] = []
        for batch_queries in (10, 100, 1000):
            started = time.perf_counter()
            for query_start, query_end, kth in windows[:batch_queries]:
                left = dates.index(query_start)
                right = dates.index(query_end)
                exact = sorted(volumes_scaled[left : right + 1], reverse=True)[kth - 1]
                approx = int(digest_index.query_inclusive(left, right, kth).kth_value_scaled)
                abs_errors.append(abs(float(exact - approx)) / 10000.0)
            timing_rows.append({"scenario": "t_digest", "mode": "algo_hot", "batch_queries": batch_queries, "seconds": round(time.perf_counter() - started, 6)})

        cdq_result = benchmark_run(
            session=session,
            import_run_id=run.id,
            repeats=3,
            skip_sql=not settings.database_url.startswith("postgresql"),
        )
        timing_rows.append({"scenario": "joint_anomaly_cdq", "mode": "algo_hot", "batch_queries": 1, "seconds": round(cdq_result.cdq_total_median_seconds, 6)})
        if settings.database_url.startswith("postgresql"):
            timing_rows.append({"scenario": "joint_anomaly_cdq", "mode": "sql_cold", "batch_queries": 1, "seconds": round(cdq_result.sql_median_seconds, 6)})

        summary.update(
            {
                "import_run_id": int(run.id),
                "tdigest_mean_abs_error": round(mean(abs_errors), 6) if abs_errors else 0.0,
                "cdq_valid_event_count": cdq_result.valid_event_count,
                "cdq_speedup_vs_sql": round(cdq_result.speedup_vs_sql, 4),
            }
        )

        if not args.keep_data:
            cleanup_benchmark_run(session, import_run_id=run.id)
            session.commit()

    write_csv(output_dir / "timings.csv", timing_rows)
    write_csv(output_dir / "memory.csv", memory_rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote benchmark artifacts to {output_dir}")

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
