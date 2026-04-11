from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import json
import random
from statistics import median
import sys
import time
from pathlib import Path

from sqlalchemy import delete, insert, text
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.core.database import create_all_tables, get_engine, get_session_factory
from app.engine_bridge.adapters.trading import query_historical_dominance
from app.engine_bridge.loaders.trading import build_trading_joint_anomaly_events
from app.models import ImportRun, TradingRecord, utc_now
from app.repositories.imports import CURRENT_IMPORT_SOURCE_NAME, CURRENT_IMPORT_SOURCE_TYPE
from app.repositories.trading import TradingRepository


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    instruments: int
    days: int


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    valid_event_count: int
    cdq_total_median_seconds: float
    cdq_engine_median_seconds: float
    sql_median_seconds: float
    speedup_vs_sql: float


SQL_BASELINE_QUERY = text(
    """
    WITH ordered AS (
        SELECT
            instrument_code,
            COALESCE(instrument_name, instrument_code) AS instrument_name,
            trade_date,
            close::double precision AS close_value,
            volume::double precision AS volume_value,
            lag(close::double precision) OVER (
                PARTITION BY instrument_code
                ORDER BY trade_date
            ) AS previous_close
        FROM trading_records
        WHERE import_run_id = :import_run_id
    ),
    signals AS (
        SELECT
            instrument_code,
            instrument_name,
            trade_date,
            (close_value - previous_close) / NULLIF(previous_close, 0.0) AS daily_return,
            volume_value
        FROM ordered
    ),
    windowed AS (
        SELECT
            instrument_code,
            instrument_name,
            trade_date,
            daily_return,
            stddev_pop(daily_return) OVER (
                PARTITION BY instrument_code
                ORDER BY trade_date
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS previous_return_std20,
            count(daily_return) OVER (
                PARTITION BY instrument_code
                ORDER BY trade_date
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS previous_return_count,
            avg(volume_value) OVER (
                PARTITION BY instrument_code
                ORDER BY trade_date
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS previous_volume_mean20,
            count(volume_value) OVER (
                PARTITION BY instrument_code
                ORDER BY trade_date
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS previous_volume_count,
            volume_value
        FROM signals
    ),
    events AS (
        SELECT
            instrument_code,
            instrument_name,
            trade_date,
            daily_return,
            abs(daily_return) / NULLIF(previous_return_std20, 0.0) AS return_z20,
            volume_value / NULLIF(previous_volume_mean20, 0.0) AS volume_ratio20,
            row_number() OVER (ORDER BY trade_date, instrument_code) - 1 AS event_index
        FROM windowed
        WHERE daily_return IS NOT NULL
          AND previous_return_std20 IS NOT NULL
          AND previous_return_count = 20
          AND previous_return_std20 > 0
          AND previous_volume_mean20 IS NOT NULL
          AND previous_volume_count = 20
          AND previous_volume_mean20 > 0
    )
    SELECT
        current_event.event_index,
        count(previous_event.event_index) AS historical_dominated_count
    FROM events AS current_event
    LEFT JOIN events AS previous_event
        ON previous_event.event_index < current_event.event_index
       AND previous_event.return_z20 <= current_event.return_z20
       AND previous_event.volume_ratio20 <= current_event.volume_ratio20
    GROUP BY current_event.event_index
    ORDER BY current_event.event_index
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark CDQ joint anomaly ranking against a PostgreSQL SQL baseline.")
    parser.add_argument("--instruments", type=int, help="Number of instruments to synthesize.")
    parser.add_argument("--days", type=int, help="Number of trading days per instrument.")
    parser.add_argument("--repeats", type=int, default=3, help="Number of timed repetitions for each path.")
    parser.add_argument("--seed", type=int, default=20260410, help="Deterministic random seed.")
    parser.add_argument(
        "--sample",
        choices=["300x480", "1000x480", "3000x480"],
        help="Predefined benchmark scale. Overrides --instruments and --days when provided.",
    )
    parser.add_argument(
        "--skip-sql",
        action="store_true",
        help="Run the CDQ path only. Useful for local smoke checks on non-PostgreSQL databases.",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep the generated benchmark import run instead of deleting it after the benchmark finishes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional output directory for summary.json and timings.csv.",
    )
    return parser.parse_args()


def resolve_sample(args: argparse.Namespace) -> BenchmarkSample:
    if args.sample:
        instruments_text, days_text = args.sample.split("x", maxsplit=1)
        return BenchmarkSample(instruments=int(instruments_text), days=int(days_text))
    if args.instruments and args.days:
        return BenchmarkSample(instruments=args.instruments, days=args.days)
    return BenchmarkSample(instruments=300, days=480)


def build_synthetic_trading_rows(*, instruments: int, days: int, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    start_day = date(2024, 1, 1)
    rows: list[dict[str, object]] = []

    for instrument_index in range(instruments):
        instrument_code = f"SYM{instrument_index:05d}"
        instrument_name = f"Synthetic {instrument_index:05d}"
        previous_close = 40.0 + (instrument_index % 200) * 0.35
        volume_base = 50_000.0 + instrument_index * 25.0
        move_pattern = [0.0030, -0.0012, 0.0024, 0.0008, -0.0016, 0.0018]

        for day_index in range(days):
            trade_day = start_day + timedelta(days=day_index)
            if day_index == 0:
                close_value = previous_close
            else:
                move = move_pattern[day_index % len(move_pattern)] + rng.uniform(-0.0015, 0.0015)
                if day_index >= 24 and (day_index + instrument_index) % 97 == 0:
                    move += 0.0500 + (instrument_index % 7) * 0.0025
                close_value = max(previous_close * (1.0 + move), 1.0)

            open_value = previous_close if day_index > 0 else close_value * 0.998
            high_value = max(open_value, close_value) * (1.01 + rng.uniform(0.0, 0.004))
            low_value = max(min(open_value, close_value) * (0.99 - rng.uniform(0.0, 0.004)), 0.1)

            volume_value = volume_base + day_index * 18.0 + rng.uniform(-750.0, 750.0)
            if day_index >= 24 and (day_index * 3 + instrument_index) % 89 == 0:
                volume_value *= 3.5 + (instrument_index % 5) * 0.2
            volume_value = max(volume_value, 1.0)

            amount_value = close_value * volume_value
            rows.append(
                {
                    "instrument_code": instrument_code,
                    "instrument_name": instrument_name,
                    "trade_date": trade_day,
                    "open": Decimal(f"{open_value:.4f}"),
                    "high": Decimal(f"{high_value:.4f}"),
                    "low": Decimal(f"{low_value:.4f}"),
                    "close": Decimal(f"{close_value:.4f}"),
                    "volume": Decimal(f"{volume_value:.4f}"),
                    "amount": Decimal(f"{amount_value:.4f}"),
                }
            )
            previous_close = close_value

    return rows


def create_benchmark_run(session: Session, *, instruments: int, days: int, row_count: int) -> ImportRun:
    timestamp = utc_now()
    run = ImportRun(
        owner_user_id=None,
        dataset_name=f"joint_anomaly_benchmark_{instruments}x{days}_{int(timestamp.timestamp())}",
        source_type=CURRENT_IMPORT_SOURCE_TYPE,
        source_name=CURRENT_IMPORT_SOURCE_NAME,
        source_uri=f"benchmark://joint-anomaly/{instruments}x{days}",
        original_file_name=None,
        file_format="synthetic",
        status="completed",
        started_at=timestamp,
        completed_at=timestamp,
        record_count=row_count,
        metadata_json={"benchmark": "joint_anomaly_cdq"},
    )
    session.add(run)
    session.flush()
    return run


def insert_benchmark_rows(session: Session, *, import_run_id: int, rows: Sequence[dict[str, object]]) -> None:
    session.execute(
        insert(TradingRecord),
        [
            {
                "import_run_id": import_run_id,
                **row,
            }
            for row in rows
        ],
    )


def run_cdq_path(session: Session, *, import_run_id: int) -> tuple[int, float, float]:
    total_started = time.perf_counter()
    rows = TradingRepository.list_joint_anomaly_rows(session, import_run_id=import_run_id)
    events = build_trading_joint_anomaly_events(import_run_id=import_run_id, rows=rows, lookback_window=20)
    engine_started = time.perf_counter()
    result = query_historical_dominance(
        [event.return_z20_scaled for event in events],
        [event.volume_ratio20_scaled for event in events],
    )
    engine_finished = time.perf_counter()
    assert len(events) == len(result.dominated_counts)
    return len(events), engine_finished - total_started, engine_finished - engine_started


def run_sql_path(session: Session, *, import_run_id: int) -> tuple[list[int], float]:
    started = time.perf_counter()
    rows = session.execute(SQL_BASELINE_QUERY, {"import_run_id": import_run_id}).all()
    finished = time.perf_counter()
    counts = [int(dominated_count) for _, dominated_count in rows]
    return counts, finished - started


def cleanup_benchmark_run(session: Session, *, import_run_id: int) -> None:
    session.execute(delete(TradingRecord).where(TradingRecord.import_run_id == import_run_id))
    session.execute(delete(ImportRun).where(ImportRun.id == import_run_id))


def write_benchmark_artifacts(
    output_dir: Path,
    *,
    import_run_id: int,
    sample: BenchmarkSample,
    row_count: int,
    result: BenchmarkResult,
    skip_sql: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "import_run_id": import_run_id,
        "sample": f"{sample.instruments}x{sample.days}",
        "row_count": row_count,
        "valid_event_count": result.valid_event_count,
        "cdq_total_median_seconds": result.cdq_total_median_seconds,
        "cdq_engine_median_seconds": result.cdq_engine_median_seconds,
        "sql_median_seconds": None if skip_sql else result.sql_median_seconds,
        "speedup_vs_sql": None if skip_sql else result.speedup_vs_sql,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "timings.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["scenario", "mode", "batch_queries", "seconds"])
        writer.writeheader()
        writer.writerow(
            {
                "scenario": "joint_anomaly_cdq",
                "mode": "algo_hot",
                "batch_queries": 1,
                "seconds": f"{result.cdq_total_median_seconds:.6f}",
            }
        )
        if not skip_sql:
            writer.writerow(
                {
                    "scenario": "joint_anomaly_cdq",
                    "mode": "sql_cold",
                    "batch_queries": 1,
                    "seconds": f"{result.sql_median_seconds:.6f}",
                }
            )


def benchmark_run(
    *,
    session: Session,
    import_run_id: int,
    repeats: int,
    skip_sql: bool,
) -> BenchmarkResult:
    cdq_total_times: list[float] = []
    cdq_engine_times: list[float] = []
    valid_event_count = 0
    expected_sql_counts: list[int] | None = None
    sql_times: list[float] = []

    for _ in range(repeats):
        valid_event_count, cdq_total_seconds, cdq_engine_seconds = run_cdq_path(session, import_run_id=import_run_id)
        cdq_total_times.append(cdq_total_seconds)
        cdq_engine_times.append(cdq_engine_seconds)

    if skip_sql:
        return BenchmarkResult(
            valid_event_count=valid_event_count,
            cdq_total_median_seconds=median(cdq_total_times),
            cdq_engine_median_seconds=median(cdq_engine_times),
            sql_median_seconds=0.0,
            speedup_vs_sql=0.0,
        )

    for _ in range(repeats):
        sql_counts, sql_seconds = run_sql_path(session, import_run_id=import_run_id)
        if expected_sql_counts is None:
            expected_sql_counts = sql_counts
        else:
            assert sql_counts == expected_sql_counts
        sql_times.append(sql_seconds)

    _, _, cdq_engine_seconds = run_cdq_path(session, import_run_id=import_run_id)
    if expected_sql_counts is not None:
        # Re-run the CDQ path once to verify the full count cardinality against SQL.
        rows = TradingRepository.list_joint_anomaly_rows(session, import_run_id=import_run_id)
        events = build_trading_joint_anomaly_events(import_run_id=import_run_id, rows=rows, lookback_window=20)
        cdq_counts = query_historical_dominance(
            [event.return_z20_scaled for event in events],
            [event.volume_ratio20_scaled for event in events],
        ).dominated_counts
        assert cdq_counts == expected_sql_counts

    return BenchmarkResult(
        valid_event_count=valid_event_count,
        cdq_total_median_seconds=median(cdq_total_times),
        cdq_engine_median_seconds=median(cdq_engine_times),
        sql_median_seconds=median(sql_times),
        speedup_vs_sql=(median(sql_times) / median(cdq_total_times)) if median(cdq_total_times) > 0 else 0.0,
    )


def main() -> int:
    args = parse_args()
    sample = resolve_sample(args)
    settings = get_settings()

    if not args.skip_sql and not settings.database_url.startswith("postgresql"):
        raise SystemExit(
            "The SQL baseline requires PostgreSQL. Use a PostgreSQL DATABASE_URL or pass --skip-sql for a CDQ-only smoke run."
        )

    create_all_tables()
    engine = get_engine()
    session_factory = get_session_factory()
    rows = build_synthetic_trading_rows(instruments=sample.instruments, days=sample.days, seed=args.seed)

    with session_factory() as session:
        run = create_benchmark_run(
            session,
            instruments=sample.instruments,
            days=sample.days,
            row_count=len(rows),
        )
        insert_benchmark_rows(session, import_run_id=run.id, rows=rows)
        session.commit()

        result = benchmark_run(
            session=session,
            import_run_id=run.id,
            repeats=args.repeats,
            skip_sql=args.skip_sql,
        )

        print(f"database_url={settings.database_url}")
        print(f"import_run_id={run.id}")
        print(f"sample={sample.instruments}x{sample.days}")
        print(f"row_count={len(rows)}")
        print(f"valid_event_count={result.valid_event_count}")
        print(f"cdq_total_median_seconds={result.cdq_total_median_seconds:.6f}")
        print(f"cdq_engine_median_seconds={result.cdq_engine_median_seconds:.6f}")
        if args.skip_sql:
            print("sql_median_seconds=skipped")
            print("speedup_vs_sql=skipped")
        else:
            print(f"sql_median_seconds={result.sql_median_seconds:.6f}")
            print(f"speedup_vs_sql={result.speedup_vs_sql:.2f}x")

        if args.output_dir:
            write_benchmark_artifacts(
                args.output_dir.resolve(),
                import_run_id=run.id,
                sample=sample,
                row_count=len(rows),
                result=result,
                skip_sql=args.skip_sql,
            )

        if not args.keep_data:
            cleanup_benchmark_run(session, import_run_id=run.id)
            session.commit()

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
