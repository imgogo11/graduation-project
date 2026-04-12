from __future__ import annotations

import argparse
from decimal import Decimal
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
from benchmarks.common.metrics import (  # noqa: E402
    classify_relative_error_band,
    rank_error,
    safe_relative_error,
    sample_sort_key,
    summarize_latencies,
)
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
from app.algo_bridge.loaders.trading import scale_volume  # noqa: E402
from app.algo_bridge.tdigest import RangeKthTDigestBlockIndex  # noqa: E402


try:
    import psutil
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise SystemExit("psutil is required for benchmark memory sampling. Install the benchmark optional dependencies.") from exc


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
    parser = argparse.ArgumentParser(description="Benchmark SQL, persistent segment tree, and t-digest for kth queries.")
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


def measure_sql(session, *, import_run_id: int, instrument_code: str, windows: list[tuple[object, object, int]]) -> tuple[list[float], list[int]]:
    latencies: list[float] = []
    values: list[int] = []
    for query_start, query_end, kth in windows:
        started = time.perf_counter()
        result = session.execute(
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
        values.append(scale_volume(result if isinstance(result, Decimal) else Decimal(str(result))))
    return latencies, values


def measure_persistent_tree(tree: object, *, date_to_index: dict[object, int], windows: list[tuple[object, object, int]]) -> tuple[list[float], list[int]]:
    latencies: list[float] = []
    values: list[int] = []
    for query_start, query_end, kth in windows:
        started = time.perf_counter()
        result = tree.query_inclusive(date_to_index[query_start], date_to_index[query_end], kth)
        latencies.append(time.perf_counter() - started)
        values.append(int(result.kth_value_scaled))
    return latencies, values


def measure_tdigest(index: RangeKthTDigestBlockIndex, *, date_to_index: dict[object, int], windows: list[tuple[object, object, int]]) -> tuple[list[float], list[int]]:
    latencies: list[float] = []
    values: list[int] = []
    for query_start, query_end, kth in windows:
        started = time.perf_counter()
        result = index.query_inclusive(date_to_index[query_start], date_to_index[query_end], kth)
        latencies.append(time.perf_counter() - started)
        values.append(int(result.kth_value_scaled))
    return latencies, values


def build_latency_summary_row(
    *,
    sample: str,
    implementation: str,
    query_count: int,
    build_seconds: float,
    build_rss_mb: float,
    latencies: list[float],
) -> dict[str, object]:
    summary = summarize_latencies(latencies)
    return {
        "sample": sample,
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
    }


def build_error_rows(
    *,
    sample: str,
    implementation: str,
    query_count: int,
    windows: list[tuple[object, object, int]],
    exact_values: list[int],
    observed_values: list[int],
    volume_windows: list[list[int]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    band_counts = {"0%": 0, "<=1%": 0, "<=5%": 0, ">5%": 0}

    for index, (window, exact_value, observed_value, values_in_window) in enumerate(
        zip(windows, exact_values, observed_values, volume_windows, strict=True),
        start=1,
    ):
        _, _, kth = window
        absolute_error = abs(float(observed_value - exact_value)) / 10000.0
        relative_error = safe_relative_error(exact=exact_value, observed=observed_value)
        query_rank_error = rank_error(values_in_window, observed_value, kth)
        error_band = classify_relative_error_band(relative_error)
        band_counts[error_band] += 1
        rows.append(
            {
                "sample": sample,
                "implementation": implementation,
                "query_index": index,
                "query_count": query_count,
                "absolute_error": round(absolute_error, 8),
                "relative_error": round(relative_error, 8),
                "rank_error": query_rank_error,
                "error_band": error_band,
            }
        )

    count = len(rows)
    summary = {
        "sample": sample,
        "implementation": implementation,
        "query_count": query_count,
        "mean_absolute_error": round(sum(float(row["absolute_error"]) for row in rows) / count, 8) if rows else 0.0,
        "mean_relative_error": round(sum(float(row["relative_error"]) for row in rows) / count, 8) if rows else 0.0,
        "mean_rank_error": round(sum(int(row["rank_error"]) for row in rows) / count, 4) if rows else 0.0,
        "max_rank_error": max((int(row["rank_error"]) for row in rows), default=0),
        "zero_error_ratio": round(sum(1 for row in rows if float(row["relative_error"]) == 0.0) / count, 6) if rows else 0.0,
        "band_0": band_counts["0%"],
        "band_lte_1": band_counts["<=1%"],
        "band_lte_5": band_counts["<=5%"],
        "band_gt_5": band_counts[">5%"],
    }
    return rows, summary


def render_images(paths: object, latency_summary_rows: list[dict[str, object]], error_summary_rows: list[dict[str, object]]) -> None:
    if not latency_summary_rows:
        return

    samples = sorted({str(row["sample"]) for row in latency_summary_rows}, key=sample_sort_key)
    target_sample = samples[-1]
    target_query_count = max(int(row["query_count"]) for row in latency_summary_rows)
    target_latency_rows = [row for row in latency_summary_rows if row["sample"] == target_sample and int(row["query_count"]) == target_query_count]
    target_error_rows = [row for row in error_summary_rows if row["sample"] == target_sample and int(row["query_count"]) == target_query_count]

    implementation_labels = {
        "sql": "SQL",
        "persistent_segment_tree": "Persistent Segment Tree",
        "t_digest": "t-digest",
    }

    save_table_image(
        paths.images / "kth_summary_table.png",
        title=f"Kth Comparison Summary ({target_sample}, {target_query_count} queries)",
        columns=["Implementation", "Build ms", "Mean ms", "P95 ms", "QPS", "Mean Abs Err", "Mean Rank Err"],
        rows=[
            [
                implementation_labels[str(latency_row["implementation"])],
                f'{float(latency_row["build_seconds"]) * 1000.0:.2f}',
                f'{float(latency_row["mean_seconds"]) * 1000.0:.4f}',
                f'{float(latency_row["p95_seconds"]) * 1000.0:.4f}',
                f'{float(latency_row["throughput_qps"]):.1f}',
                f'{float(next(error_row["mean_absolute_error"] for error_row in target_error_rows if error_row["implementation"] == latency_row["implementation"])):.4f}',
                f'{float(next(error_row["mean_rank_error"] for error_row in target_error_rows if error_row["implementation"] == latency_row["implementation"])):.2f}',
            ]
            for latency_row in target_latency_rows
        ],
    )

    save_grouped_bar_chart(
        paths.images / "kth_efficiency_bar.png",
        title=f"Kth Mean Query Latency ({target_sample}, {target_query_count} queries)",
        categories=[implementation_labels[str(row["implementation"])] for row in target_latency_rows],
        series={"Mean latency (ms)": [float(row["mean_seconds"]) * 1000.0 for row in target_latency_rows]},
        ylabel="Mean Latency (ms)",
    )

    query_counts = sorted({int(row["query_count"]) for row in latency_summary_rows})
    scaling_rows = [row for row in latency_summary_rows if row["sample"] == target_sample]
    save_line_chart(
        paths.images / "kth_scale_line.png",
        title=f"Kth Scaling ({target_sample})",
        x_values=query_counts,
        series={
            implementation_labels["sql"]: [
                float(next(row["total_seconds"] for row in scaling_rows if row["implementation"] == "sql" and int(row["query_count"]) == count))
                for count in query_counts
            ],
            implementation_labels["persistent_segment_tree"]: [
                float(next(row["total_seconds"] for row in scaling_rows if row["implementation"] == "persistent_segment_tree" and int(row["query_count"]) == count))
                for count in query_counts
            ],
            implementation_labels["t_digest"]: [
                float(next(row["total_seconds"] for row in scaling_rows if row["implementation"] == "t_digest" and int(row["query_count"]) == count))
                for count in query_counts
            ],
        },
        xlabel="Batch Queries",
        ylabel="Total Runtime (s)",
    )

    save_grouped_bar_chart(
        paths.images / "kth_error_distribution.png",
        title=f"Kth Error Distribution ({target_sample}, {target_query_count} queries)",
        categories=["0%", "<=1%", "<=5%", ">5%"],
        series={
            implementation_labels[str(row["implementation"])]: [
                float(row["band_0"]),
                float(row["band_lte_1"]),
                float(row["band_lte_5"]),
                float(row["band_gt_5"]),
            ]
            for row in target_error_rows
        },
        ylabel="Query Count",
    )

    tdigest_summary = next(row for row in target_error_rows if row["implementation"] == "t_digest")
    save_pie_chart(
        paths.images / "kth_error_band_pie.png",
        title=f"t-digest Error Band Share ({target_sample}, {target_query_count} queries)",
        labels=["0%", "<=1%", "<=5%", ">5%"],
        values=[
            float(tdigest_summary["band_0"]),
            float(tdigest_summary["band_lte_1"]),
            float(tdigest_summary["band_lte_5"]),
            float(tdigest_summary["band_gt_5"]),
        ],
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
    paths = prepare_suite_paths("kth_comparison", explicit_root=output_dir)
    runtime = create_runtime()
    module = load_algo_module()

    latency_rows: list[dict[str, object]] = []
    raw_latency_rows: list[dict[str, object]] = []
    error_rows: list[dict[str, object]] = []
    error_summary_rows: list[dict[str, object]] = []
    build_rows: list[dict[str, object]] = []
    benchmark_run_ids: list[int] = []

    try:
        for sample in resolve_samples(sample_name):
            rows = build_synthetic_trading_rows(instruments=sample.instruments, days=sample.days, seed=seed)
            with runtime.session_factory() as session:
                run = create_benchmark_run(
                    session,
                    benchmark_name="kth_comparison",
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
                volumes_scaled = [scale_volume(row["volume"]) for row in instrument_rows]
                windows = build_query_windows(dates, total=max_query_count, seed=seed + sample.instruments + 99)
                volume_windows = [
                    volumes_scaled[date_to_index[query_start] : date_to_index[query_end] + 1]
                    for query_start, query_end, _ in windows
                ]

                before_rss = rss_mb()
                build_started = time.perf_counter()
                persistent_tree = module.RangeKthPersistentSegmentTree(volumes_scaled)
                persistent_build_seconds = time.perf_counter() - build_started
                persistent_rss_mb = max(rss_mb() - before_rss, 0.0)
                build_rows.append(
                    {
                        "sample": sample.label,
                        "implementation": "persistent_segment_tree",
                        "build_seconds": round(persistent_build_seconds, 6),
                        "build_rss_mb": round(persistent_rss_mb, 4),
                    }
                )

                before_rss = rss_mb()
                build_started = time.perf_counter()
                tdigest_index = RangeKthTDigestBlockIndex(volumes_scaled)
                tdigest_build_seconds = time.perf_counter() - build_started
                tdigest_rss_mb = max(rss_mb() - before_rss, 0.0)
                build_rows.append(
                    {
                        "sample": sample.label,
                        "implementation": "t_digest",
                        "build_seconds": round(tdigest_build_seconds, 6),
                        "build_rss_mb": round(tdigest_rss_mb, 4),
                    }
                )

                sql_latencies, sql_values = measure_sql(session, import_run_id=run.id, instrument_code=instrument_code, windows=windows)
                persistent_latencies, persistent_values = measure_persistent_tree(persistent_tree, date_to_index=date_to_index, windows=windows)
                tdigest_latencies, tdigest_values = measure_tdigest(tdigest_index, date_to_index=date_to_index, windows=windows)

                latency_series = {
                    "sql": (sql_latencies, sql_values, 0.0, 0.0),
                    "persistent_segment_tree": (persistent_latencies, persistent_values, persistent_build_seconds, persistent_rss_mb),
                    "t_digest": (tdigest_latencies, tdigest_values, tdigest_build_seconds, tdigest_rss_mb),
                }

                for implementation, (latencies, values, _, _) in latency_series.items():
                    raw_latency_rows.extend(
                        {
                            "sample": sample.label,
                            "implementation": implementation,
                            "query_index": query_index,
                            "latency_seconds": round(latency, 8),
                            "value_scaled": int(value),
                        }
                        for query_index, (latency, value) in enumerate(zip(latencies, values, strict=True), start=1)
                    )
                    for query_count in query_counts:
                        build_seconds, build_rss_mb = latency_series[implementation][2:]
                        latency_rows.append(
                            build_latency_summary_row(
                                sample=sample.label,
                                implementation=implementation,
                                query_count=query_count,
                                build_seconds=build_seconds,
                                build_rss_mb=build_rss_mb,
                                latencies=latencies[:query_count],
                            )
                        )

                        slice_error_rows, slice_error_summary = build_error_rows(
                            sample=sample.label,
                            implementation=implementation,
                            query_count=query_count,
                            windows=windows[:query_count],
                            exact_values=sql_values[:query_count],
                            observed_values=values[:query_count],
                            volume_windows=volume_windows[:query_count],
                        )
                        error_rows.extend(slice_error_rows)
                        error_summary_rows.append(slice_error_summary)

                if not keep_data:
                    cleanup_benchmark_run(session, import_run_id=run.id)
                    session.commit()

        write_csv(paths.results / "raw_query_latencies.csv", raw_latency_rows)
        write_csv(paths.results / "build_metrics.csv", build_rows)
        write_csv(paths.results / "latency_summary.csv", latency_rows)
        write_csv(paths.results / "error_summary.csv", error_summary_rows)
        write_csv(paths.results / "raw_errors.csv", error_rows)
        write_json(
            paths.results / "summary.json",
            {
                "generated_at": datetime.now().isoformat(),
                "samples": sorted({str(row["sample"]) for row in latency_rows}, key=sample_sort_key),
                "query_counts": query_counts,
                "benchmark_run_ids": benchmark_run_ids,
                "suite": "kth_comparison",
            },
        )
        render_images(paths, latency_rows, error_summary_rows)
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
