from __future__ import annotations

import argparse
import csv
from pathlib import Path


try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit("matplotlib is required for benchmark visualization. Install backend/requirements-optional.txt.") from exc


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render runtime and memory plots from benchmark CSV outputs.")
    parser.add_argument("--input-dir", type=Path, help="Benchmark artifact directory under docs/benchmarks.")
    return parser.parse_args()


def resolve_input_dir(args: argparse.Namespace) -> Path:
    if args.input_dir:
        return args.input_dir.resolve()
    benchmark_root = (REPO_ROOT / "docs" / "benchmarks").resolve()
    candidates = sorted([item for item in benchmark_root.iterdir() if item.is_dir()])
    if not candidates:
        raise SystemExit("No benchmark directories found under docs/benchmarks.")
    return candidates[-1]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def plot_runtime(rows: list[dict[str, str]], output_path: Path) -> None:
    cold_rows = [row for row in rows if row["batch_queries"] == "1"]
    labels = [f'{row["scenario"]}\n{row["mode"]}' for row in cold_rows]
    values = [float(row["seconds"]) for row in cold_rows]
    plt.figure(figsize=(12, 6))
    plt.bar(labels, values, color="#0b8f8c")
    plt.ylabel("Seconds")
    plt.title("Runtime Comparison (Cold + Single Query)")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def plot_memory(rows: list[dict[str, str]], output_path: Path) -> None:
    labels = [row["scenario"] for row in rows]
    values = [float(row["rss_mb"]) for row in rows]
    plt.figure(figsize=(10, 5))
    plt.bar(labels, values, color="#f28c28")
    plt.ylabel("RSS MB Delta")
    plt.title("Build Memory Delta")
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def plot_cold_vs_hot(rows: list[dict[str, str]], output_path: Path) -> None:
    scenarios = sorted({row["scenario"] for row in rows})
    modes = ["sql_cold", "algo_cold", "algo_hot"]
    batch_target = "1000"
    plt.figure(figsize=(12, 6))
    width = 0.22
    x_positions = list(range(len(scenarios)))
    for offset, mode in enumerate(modes):
        values: list[float] = []
        for scenario in scenarios:
            candidate = next(
                (
                    row
                    for row in rows
                    if row["scenario"] == scenario and row["mode"] == mode and (row["batch_queries"] == ("1" if mode != "algo_hot" else batch_target))
                ),
                None,
            )
            values.append(float(candidate["seconds"]) if candidate is not None else 0.0)
        plt.bar([position + width * offset for position in x_positions], values, width=width, label=mode)
    plt.xticks([position + width for position in x_positions], scenarios, rotation=20, ha="right")
    plt.ylabel("Seconds")
    plt.title("Cold vs Hot (Algo hot uses 1000 queries)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def plot_batch_scaling(rows: list[dict[str, str]], output_path: Path) -> None:
    scaling_rows = [row for row in rows if row["batch_queries"] in {"10", "100", "1000"}]
    plt.figure(figsize=(12, 6))
    groups = sorted({(row["scenario"], row["mode"]) for row in scaling_rows})
    for scenario, mode in groups:
        relevant = sorted(
            [row for row in scaling_rows if row["scenario"] == scenario and row["mode"] == mode],
            key=lambda item: int(item["batch_queries"]),
        )
        plt.plot(
            [int(row["batch_queries"]) for row in relevant],
            [float(row["seconds"]) for row in relevant],
            marker="o",
            label=f"{scenario}:{mode}",
        )
    plt.xlabel("Batch Queries")
    plt.ylabel("Seconds")
    plt.title("Batch Scaling")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def main() -> int:
    input_dir = resolve_input_dir(parse_args())
    timings = read_csv_rows(input_dir / "timings.csv")
    memory = read_csv_rows(input_dir / "memory.csv")
    plots_dir = input_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    plot_runtime(timings, plots_dir / "runtime.png")
    plot_memory(memory, plots_dir / "memory.png")
    plot_cold_vs_hot(timings, plots_dir / "cold_vs_hot.png")
    plot_batch_scaling(timings, plots_dir / "batch_scaling.png")
    print(f"Wrote plots to {plots_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
