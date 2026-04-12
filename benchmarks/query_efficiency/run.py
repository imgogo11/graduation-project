from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
import time

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.common.backend_runtime import (  # noqa: E402
    cleanup_benchmark_run,
    create_benchmark_run,
    create_runtime,
    dispose_runtime,
    insert_benchmark_rows,
)
from benchmarks.common.io import prepare_suite_paths, write_csv, write_json  # noqa: E402
from benchmarks.common.metrics import safe_speedup, sample_sort_key, summarize_latencies  # noqa: E402
from benchmarks.common.plotting import (  # noqa: E402
    save_grouped_bar_chart,
    save_line_chart,
    save_pie_chart,
    save_table_image,
)
from benchmarks.common.synthetic_data import (  # noqa: E402
    build_query_windows,
    build_synthetic_trading_rows,
    resolve_samples,
)

from app.algo_bridge.adapters.trading import load_algo_module  # noqa: E402
from app.algo_bridge.loaders.trading import scale_amount, scale_volume  # noqa: E402


try:
    import psutil
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise SystemExit("psutil is required for benchmark memory sampling. Install the benchmark optional dependencies.") from exc


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
    parser = argparse.ArgumentParser(description="Benchmark high-frequency SQL queries versus the C++ algo module.")
    parser.add_argument("--sample", default="all", help="300x480, 1000x480, 3000x480, or all.")
    parser.add_argument("--seed", type=int, default=20260412)
    parser.add_argument("--keep-data", action="store_true", help="Keep the synthetic benchmark data in the database.")
    parser.add_argument("--output-dir", type=Path, help="Optional explicit output directory.")
    parser.add_argument("--query-counts", default="10,100,1000,10000", help="Comma-separated query batch sizes.")
    return parser.parse_args()


def parse_query_counts(query_counts_text: str) -> list[int]:
    counts = sorted({int(part.strip()) for part in query_counts_text.split(",") if part.strip()})
    if not counts or counts[0] <= 0:
        raise ValueError("query counts must contain positive integers")
    return counts


def rss_mb() -> float:
    return float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)


def measure_sql_max(session, *, import_run_id: int, instrument_code: str, windows: list[tuple[object, object, int]]) -> list[float]:
    latencies: list[float] = []
    for query_start, query_end, _ in windows:
        started = time.perf_counter()
        session.execute(
            SQL_MAX_QUERY,
            {
                "import_run_id": import_run_id,
                "instrument_code": instrument_code,
                "start_date": query_start,
                "end_date": query_end,
            },
        ).scalar_one()
        latencies.append(time.perf_counter() - started)
    return latencies


def measure_algo_max(tree: object, *, date_to_index: dict[object, int], windows: list[tuple[object, object, int]]) -> list[float]:
    latencies: list[float] = []
    for query_start, query_end, _ in windows:
        started = time.perf_counter()
        tree.query_inclusive(date_to_index[query_start], date_to_index[query_end])
        latencies.append(time.perf_counter() - started)
    return latencies


def measure_sql_kth(session, *, import_run_id: int, instrument_code: str, windows: list[tuple[object, object, int]]) -> list[float]:
    latencies: list[float] = []
    for query_start, query_end, kth in windows:
        started = time.perf_counter()
        session.execute(
            SQL_KTH_QUERY,
            {
                "import_run_id": import_run_id,
                "instrument_code": instrument_code,
                "start_date": query_start,
                "end_date": query_end,
                "offset": kth - 1,
            },
        ).scalar_one()
        latencies.append(time.perf_counter() - started)
    return latencies


def measure_algo_kth(tree: object, *, date_to_index: dict[object, int], windows: list[tuple[object, object, int]]) -> list[float]:
    latencies: list[float] = []
    for query_start, query_end, kth in windows:
        started = time.perf_counter()
        tree.query_inclusive(date_to_index[query_start], date_to_index[query_end], kth)
        latencies.append(time.perf_counter() - started)
    return latencies


def build_summary_row(
    *,
    sample: str,
    scenario: str,
    implementation: str,
    query_count: int,
    build_seconds: float,
    build_rss_mb: float,
    latencies: list[float],
) -> dict[str, object]:
    summary = summarize_latencies(latencies)
    return {
        "sample": sample,
        "scenario": scenario,
        "implementation": implementation,
        "query_count": query_count,
        "build_seconds": round(build_seconds, 6),
        "build_rss_mb": round(build_rss_mb, 4),
        "total_seconds": round(summary.total_seconds, 6),
        "mean_seconds": round(summary.mean_seconds, 8),
        "p50_seconds": round(summary.p50_seconds, 8),
        "p95_seconds": round(summary.p95_seconds, 8),
        "p99_seconds": round(summary.p99_seconds, 8),
        "throughput_qps": round(summary.throughput_qps, 4),
        "speedup_vs_sql": 1.0,
    }


def render_images(paths: object, summary_rows: list[dict[str, object]]) -> None:
    if not summary_rows:
        return

    samples = sorted({str(row["sample"]) for row in summary_rows}, key=sample_sort_key)
    target_sample = samples[-1]
    target_query_count = max(int(row["query_count"]) for row in summary_rows)
    target_rows = [row for row in summary_rows if row["sample"] == target_sample and int(row["query_count"]) == target_query_count]

    scenario_labels = {
        "range_max_amount": "Range Max Amount",
        "range_kth_volume": "Range Kth Volume",
    }
    implementation_labels = {
        "sql": "SQL",
        "algo_module": "Algo Module",
    }

    table_rows = [
        [
            scenario_labels[str(row["scenario"])],
            implementation_labels[str(row["implementation"])],
            f'{float(row["build_seconds"]) * 1000.0:.2f}',
            f'{float(row["mean_seconds"]) * 1000.0:.4f}',
            f'{float(row["p95_seconds"]) * 1000.0:.4f}',
            f'{float(row["throughput_qps"]):.1f}',
            f'{float(row["speedup_vs_sql"]):.2f}x',
        ]
        for row in target_rows
    ]
    save_table_image(
        paths.images / "summary_table.png",
        title=f"Query Efficiency Summary ({target_sample}, {target_query_count} queries)",
        columns=["Scenario", "Implementation", "Build ms", "Mean ms", "P95 ms", "QPS", "Speedup"],
        rows=table_rows,
    )

    categories = [scenario_labels["range_max_amount"], scenario_labels["range_kth_volume"]]
    save_grouped_bar_chart(
        paths.images / "latency_bar.png",
        title=f"Mean Query Latency ({target_sample}, {target_query_count} queries)",
        categories=categories,
        series={
            "SQL": [
                float(next(row["mean_seconds"] for row in target_rows if row["scenario"] == "range_max_amount" and row["implementation"] == "sql")) * 1000.0,
                float(next(row["mean_seconds"] for row in target_rows if row["scenario"] == "range_kth_volume" and row["implementation"] == "sql")) * 1000.0,
            ],
            "Algo Module": [
                float(next(row["mean_seconds"] for row in target_rows if row["scenario"] == "range_max_amount" and row["implementation"] == "algo_module")) * 1000.0,
                float(next(row["mean_seconds"] for row in target_rows if row["scenario"] == "range_kth_volume" and row["implementation"] == "algo_module")) * 1000.0,
            ],
        },
        ylabel="Mean Latency (ms)",
    )

    query_counts = sorted({int(row["query_count"]) for row in summary_rows})
    scaling_rows = [row for row in summary_rows if row["sample"] == target_sample]
    save_line_chart(
        paths.images / "batch_scaling_line.png",
        title=f"Batch Scaling ({target_sample})",
        x_values=query_counts,
        series={
            "Range Max / SQL": [
                float(next(row["total_seconds"] for row in scaling_rows if row["scenario"] == "range_max_amount" and row["implementation"] == "sql" and int(row["query_count"]) == count))
                for count in query_counts
            ],
            "Range Max / Algo Module": [
                float(next(row["total_seconds"] for row in scaling_rows if row["scenario"] == "range_max_amount" and row["implementation"] == "algo_module" and int(row["query_count"]) == count))
                for count in query_counts
            ],
            "Range Kth / SQL": [
                float(next(row["total_seconds"] for row in scaling_rows if row["scenario"] == "range_kth_volume" and row["implementation"] == "sql" and int(row["query_count"]) == count))
                for count in query_counts
            ],
            "Range Kth / Algo Module": [
                float(next(row["total_seconds"] for row in scaling_rows if row["scenario"] == "range_kth_volume" and row["implementation"] == "algo_module" and int(row["query_count"]) == count))
                for count in query_counts
            ],
        },
        xlabel="Batch Queries",
        ylabel="Total Runtime (s)",
    )

    save_pie_chart(
        paths.images / "runtime_share_pie.png",
        title=f"Runtime Share ({target_sample}, {target_query_count} queries)",
        labels=[f'{scenario_labels[str(row["scenario"])]}\n{implementation_labels[str(row["implementation"])]}' for row in target_rows],
        values=[float(row["total_seconds"]) for row in target_rows],
    )


def run_suite(
    *,
    sample_name: str = "all",
    seed: int = 20260412,
    keep_data: bool = False,
    output_dir: Path | None = None,
    query_counts_text: str = "10,100,1000,10000",
) -> int:
    query_counts = parse_query_counts(query_counts_text)
    max_query_count = max(query_counts)
    paths = prepare_suite_paths("query_efficiency", explicit_root=output_dir)
    runtime = create_runtime()
    module = load_algo_module()

    raw_latency_rows: list[dict[str, object]] = []
    build_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    benchmark_run_ids: list[int] = []

    try:
        for sample in resolve_samples(sample_name):
            rows = build_synthetic_trading_rows(instruments=sample.instruments, days=sample.days, seed=seed)
            with runtime.session_factory() as session:
                run = create_benchmark_run(
                    session,
                    benchmark_name="query_efficiency",
                    instruments=sample.instruments,
                    days=sample.days,
                    row_count=len(rows),
                )
                benchmark_run_ids.append(int(run.id))
                insert_benchmark_rows(session, import_run_id=run.id, rows=rows)
                session.commit()

                instrument_code = "SYM00000"
                instrument_rows = [row for row in rows if row["instrument_code"] == instrument_code]
                dates = [row["trade_date"] for row in instrument_rows]
                date_to_index = {trade_date: index for index, trade_date in enumerate(dates)}
                amounts_scaled = [scale_amount(row["amount"]) for row in instrument_rows]
                volumes_scaled = [scale_volume(row["volume"]) for row in instrument_rows]
                windows = build_query_windows(dates, total=max_query_count, seed=seed + sample.instruments)

                before_rss = rss_mb()
                build_started = time.perf_counter()
                range_max_tree = module.RangeMaxSegmentTree(amounts_scaled)
                range_max_build_seconds = time.perf_counter() - build_started
                range_max_rss_mb = max(rss_mb() - before_rss, 0.0)
                build_rows.append(
                    {
                        "sample": sample.label,
                        "scenario": "range_max_amount",
                        "implementation": "algo_module",
                        "structure": "RangeMaxSegmentTree",
                        "build_seconds": round(range_max_build_seconds, 6),
                        "build_rss_mb": round(range_max_rss_mb, 4),
                    }
                )

                before_rss = rss_mb()
                build_started = time.perf_counter()
                range_kth_tree = module.RangeKthPersistentSegmentTree(volumes_scaled)
                range_kth_build_seconds = time.perf_counter() - build_started
                range_kth_rss_mb = max(rss_mb() - before_rss, 0.0)
                build_rows.append(
                    {
                        "sample": sample.label,
                        "scenario": "range_kth_volume",
                        "implementation": "algo_module",
                        "structure": "RangeKthPersistentSegmentTree",
                        "build_seconds": round(range_kth_build_seconds, 6),
                        "build_rss_mb": round(range_kth_rss_mb, 4),
                    }
                )

                sql_max_latencies = measure_sql_max(session, import_run_id=run.id, instrument_code=instrument_code, windows=windows)
                algo_max_latencies = measure_algo_max(range_max_tree, date_to_index=date_to_index, windows=windows)
                sql_kth_latencies = measure_sql_kth(session, import_run_id=run.id, instrument_code=instrument_code, windows=windows)
                algo_kth_latencies = measure_algo_kth(range_kth_tree, date_to_index=date_to_index, windows=windows)

                latency_series = {
                    ("range_max_amount", "sql"): (sql_max_latencies, 0.0, 0.0),
                    ("range_max_amount", "algo_module"): (algo_max_latencies, range_max_build_seconds, range_max_rss_mb),
                    ("range_kth_volume", "sql"): (sql_kth_latencies, 0.0, 0.0),
                    ("range_kth_volume", "algo_module"): (algo_kth_latencies, range_kth_build_seconds, range_kth_rss_mb),
                }

                for (scenario, implementation), (latencies, _, _) in latency_series.items():
                    raw_latency_rows.extend(
                        {
                            "sample": sample.label,
                            "scenario": scenario,
                            "implementation": implementation,
                            "query_index": query_index,
                            "latency_seconds": round(latency, 8),
                        }
                        for query_index, latency in enumerate(latencies, start=1)
                    )
                    for query_count in query_counts:
                        build_seconds, build_rss_mb = latency_series[(scenario, implementation)][1:]
                        summary_rows.append(
                            build_summary_row(
                                sample=sample.label,
                                scenario=scenario,
                                implementation=implementation,
                                query_count=query_count,
                                build_seconds=build_seconds,
                                build_rss_mb=build_rss_mb,
                                latencies=latencies[:query_count],
                            )
                        )

                if not keep_data:
                    cleanup_benchmark_run(session, import_run_id=run.id)
                    session.commit()

        sql_totals = {
            (str(row["sample"]), str(row["scenario"]), int(row["query_count"])): float(row["total_seconds"])
            for row in summary_rows
            if row["implementation"] == "sql"
        }
        for row in summary_rows:
            key = (str(row["sample"]), str(row["scenario"]), int(row["query_count"]))
            row["speedup_vs_sql"] = round(
                1.0 if row["implementation"] == "sql" else safe_speedup(baseline_seconds=sql_totals[key], optimized_seconds=float(row["total_seconds"])),
                4,
            )

        write_csv(paths.results / "raw_query_latencies.csv", raw_latency_rows)
        write_csv(paths.results / "build_metrics.csv", build_rows)
        write_csv(paths.results / "latency_summary.csv", summary_rows)
        write_json(
            paths.results / "summary.json",
            {
                "generated_at": datetime.now().isoformat(),
                "samples": sorted({str(row["sample"]) for row in summary_rows}, key=sample_sort_key),
                "query_counts": query_counts,
                "benchmark_run_ids": benchmark_run_ids,
                "suite": "query_efficiency",
            },
        )
        render_images(paths, summary_rows)
    finally:
        dispose_runtime(runtime)

    return 0


def main() -> int:
    args = parse_args()
    return run_suite(
        sample_name=args.sample,
        seed=args.seed,
        keep_data=args.keep_data,
        output_dir=args.output_dir,
        query_counts_text=args.query_counts,
    )


if __name__ == "__main__":
    raise SystemExit(main())
