from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.common.io import prepare_suite_paths, read_csv_rows, write_csv, write_json  # noqa: E402
from benchmarks.common.plotting import save_grouped_bar_chart, save_line_chart, save_pie_chart, save_table_image  # noqa: E402


PROFILE_DEFAULTS = {
    "smoke": {"users": 4, "spawn_rate": 2, "run_time": "30s"},
    "thesis": {"users": 24, "spawn_rate": 6, "run_time": "2m"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Locust-based platform stability and security benchmarks.")
    parser.add_argument("--profile", choices=["smoke", "thesis"], default="smoke")
    parser.add_argument("--output-dir", type=Path, help="Optional explicit output directory.")
    return parser.parse_args()


def _lookup(row: dict[str, str], *candidates: str) -> str:
    lowered = {key.lower(): value for key, value in row.items()}
    for candidate in candidates:
        value = lowered.get(candidate.lower())
        if value is not None:
            return value
    return ""


def _as_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required for the platform quality benchmark.")
    return value


def _should_include_request_name(name: str) -> bool:
    return bool(name) and name != "Aggregated" and not name.startswith("setup/")


def build_request_rows(stats_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "request_type": _lookup(row, "Type"),
            "name": _lookup(row, "Name"),
            "request_count": _as_int(_lookup(row, "Request Count")),
            "failure_count": _as_int(_lookup(row, "Failure Count")),
            "avg_ms": round(_as_float(_lookup(row, "Average Response Time")), 4),
            "p95_ms": round(_as_float(_lookup(row, "95%")), 4),
            "rps": round(_as_float(_lookup(row, "Requests/s")), 4),
        }
        for row in stats_rows
        if _should_include_request_name(_lookup(row, "Name"))
    ]


def build_history_rows(history_csv_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    latest_by_user_count: dict[int, dict[str, object]] = {}
    for row in history_csv_rows:
        if _lookup(row, "Name") != "Aggregated":
            continue

        user_count = _as_int(_lookup(row, "User Count"))
        total_request_count = _as_int(_lookup(row, "Total Request Count"))
        if user_count <= 0 or total_request_count <= 0:
            continue

        latest_by_user_count[user_count] = {
            "user_count": user_count,
            "total_request_count": total_request_count,
            "avg_ms": round(_as_float(_lookup(row, "Total Average Response Time", "Average Response Time")), 4),
            "p95_ms": round(_as_float(_lookup(row, "95%")), 4),
        }

    return [latest_by_user_count[count] for count in sorted(latest_by_user_count)]


def run_locust(paths: object, *, profile: str) -> dict[str, Path]:
    base_url = _require_env("BENCHMARK_BASE_URL")
    _require_env("BENCHMARK_USERNAME")
    _require_env("BENCHMARK_PASSWORD")

    defaults = PROFILE_DEFAULTS[profile]
    suite_source_root = REPO_ROOT / "benchmarks" / "platform_quality"
    csv_prefix = paths.results / f"locust_{profile}"
    status_output = paths.results / "status_report.json"

    environment = os.environ.copy()
    environment["LOCUST_STATUS_OUTPUT"] = str(status_output)
    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(suite_source_root / "locustfile.py"),
        "--headless",
        "--host",
        base_url,
        "--users",
        str(defaults["users"]),
        "--spawn-rate",
        str(defaults["spawn_rate"]),
        "--run-time",
        str(defaults["run_time"]),
        "--csv",
        str(csv_prefix),
        "--csv-full-history",
        "--only-summary",
    ]
    subprocess.run(command, cwd=str(REPO_ROOT), check=True, env=environment)
    return {
        "stats": csv_prefix.with_name(f"{csv_prefix.name}_stats.csv"),
        "history": csv_prefix.with_name(f"{csv_prefix.name}_stats_history.csv"),
        "failures": csv_prefix.with_name(f"{csv_prefix.name}_failures.csv"),
        "status": status_output,
    }


def render_images(paths: object, *, request_rows: list[dict[str, object]], history_rows: list[dict[str, object]], status_report: dict[str, object]) -> None:
    if request_rows:
        top_rows = sorted(request_rows, key=lambda row: (int(row["request_count"]), float(row["p95_ms"])), reverse=True)[:6]
        save_grouped_bar_chart(
            paths.images / "platform_latency_bar.png",
            title="Platform Latency by Endpoint",
            categories=[str(row["name"]) for row in top_rows],
            series={
                "Average ms": [float(row["avg_ms"]) for row in top_rows],
                "P95 ms": [float(row["p95_ms"]) for row in top_rows],
            },
            ylabel="Latency (ms)",
        )

    if history_rows:
        user_counts = [int(row["user_count"]) for row in history_rows]
        save_line_chart(
            paths.images / "users_vs_latency_line.png",
            title="Users vs Latency",
            x_values=user_counts,
            series={
                "Average ms": [float(row["avg_ms"]) for row in history_rows],
                "P95 ms": [float(row["p95_ms"]) for row in history_rows],
            },
            xlabel="Concurrent Users",
            ylabel="Latency (ms)",
        )

    status_counts = status_report.get("status_counts", {})
    save_pie_chart(
        paths.images / "status_code_pie.png",
        title="Status Code Distribution",
        labels=[str(label) for label in status_counts.keys()],
        values=[float(value) for value in status_counts.values()],
    )

    security_cases = status_report.get("security_cases", [])
    save_table_image(
        paths.images / "security_case_table.png",
        title="Security Probe Summary",
        columns=["Case", "Expected", "Matched/Total", "Match Ratio"],
        rows=[
            [
                str(case["case"]),
                ",".join(str(item) for item in case["expected_statuses"]),
                f'{int(case["matched"])}/{int(case["total"])}',
                f'{float(case["matched_ratio"]) * 100.0:.1f}%',
            ]
            for case in security_cases
        ] or [["No security data", "-", "-", "-"]],
    )


def run_suite(*, profile: str = "smoke", output_dir: Path | None = None) -> int:
    paths = prepare_suite_paths("platform_quality", explicit_root=output_dir)
    artifacts = run_locust(paths, profile=profile)

    stats_rows = read_csv_rows(artifacts["stats"])
    request_rows = build_request_rows(stats_rows)

    history_csv_rows = read_csv_rows(artifacts["history"])
    history_rows = build_history_rows(history_csv_rows)

    status_report = json.loads(artifacts["status"].read_text(encoding="utf-8"))
    security_rows = [
        {
            "case": str(case["case"]),
            "expected_statuses": ",".join(str(item) for item in case["expected_statuses"]),
            "matched": int(case["matched"]),
            "total": int(case["total"]),
            "matched_ratio": round(float(case["matched_ratio"]), 6),
            "status_counts": json.dumps(case["status_counts"], ensure_ascii=False),
        }
        for case in status_report.get("security_cases", [])
    ]

    write_csv(paths.results / "request_summary.csv", request_rows)
    write_csv(paths.results / "security_summary.csv", security_rows)
    write_json(
        paths.results / "summary.json",
        {
            "generated_at": datetime.now().isoformat(),
            "profile": profile,
            "request_count": sum(int(row["request_count"]) for row in request_rows),
            "failure_count": sum(int(row["failure_count"]) for row in request_rows),
            "status_counts": status_report.get("status_counts", {}),
            "security_case_count": len(security_rows),
        },
    )
    render_images(paths, request_rows=request_rows, history_rows=history_rows, status_report=status_report)
    return 0


def main() -> int:
    args = parse_args()
    return run_suite(profile=args.profile, output_dir=args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
