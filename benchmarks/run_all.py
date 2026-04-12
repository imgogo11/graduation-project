from __future__ import annotations

import argparse

from benchmarks.kth_comparison.run import run_suite as run_kth_comparison_suite
from benchmarks.platform_quality.run import run_suite as run_platform_quality_suite
from benchmarks.query_efficiency.run import run_suite as run_query_efficiency_suite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run project benchmark suites from the repository root.")
    parser.add_argument(
        "--suite",
        choices=["query_efficiency", "kth_comparison", "platform_quality", "all"],
        default="all",
        help="Select a single suite or run all suites in sequence.",
    )
    parser.add_argument("--sample", default="all", help="Benchmark sample scale: 300x480, 1000x480, 3000x480, or all.")
    parser.add_argument("--seed", type=int, default=20260412, help="Deterministic random seed for synthetic data.")
    parser.add_argument("--keep-data", action="store_true", help="Keep synthetic benchmark runs in the database.")
    parser.add_argument("--profile", choices=["smoke", "thesis"], default="smoke", help="Platform suite Locust profile.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.suite in {"query_efficiency", "all"}:
        run_query_efficiency_suite(sample_name=args.sample, seed=args.seed, keep_data=args.keep_data)
    if args.suite in {"kth_comparison", "all"}:
        run_kth_comparison_suite(sample_name=args.sample, seed=args.seed, keep_data=args.keep_data)
    if args.suite in {"platform_quality", "all"}:
        run_platform_quality_suite(profile=args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
