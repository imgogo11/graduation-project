from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


@dataclass(frozen=True, slots=True)
class LatencySummary:
    total_seconds: float
    mean_seconds: float
    p50_seconds: float
    p95_seconds: float
    p99_seconds: float
    throughput_qps: float


def summarize_latencies(latencies: list[float]) -> LatencySummary:
    total_seconds = float(sum(latencies))
    mean_seconds = float(mean(latencies)) if latencies else 0.0
    return LatencySummary(
        total_seconds=total_seconds,
        mean_seconds=mean_seconds,
        p50_seconds=percentile(latencies, 0.50),
        p95_seconds=percentile(latencies, 0.95),
        p99_seconds=percentile(latencies, 0.99),
        throughput_qps=(float(len(latencies)) / total_seconds) if total_seconds > 0 else 0.0,
    )


def safe_speedup(*, baseline_seconds: float, optimized_seconds: float) -> float:
    if optimized_seconds <= 0:
        return 0.0
    return baseline_seconds / optimized_seconds


def rank_error(values: list[int], estimate: int, k: int) -> int:
    strict_greater = sum(1 for value in values if value > estimate)
    greater_or_equal = sum(1 for value in values if value >= estimate)
    lower_rank = strict_greater + 1
    upper_rank = greater_or_equal
    if lower_rank <= k <= upper_rank:
        return 0
    if k < lower_rank:
        return lower_rank - k
    return k - upper_rank


def safe_relative_error(*, exact: int, observed: int) -> float:
    if exact == 0:
        return 0.0 if observed == 0 else 1.0
    return abs(float(observed - exact)) / abs(float(exact))


def classify_relative_error_band(relative_error: float) -> str:
    if relative_error == 0:
        return "0%"
    if relative_error <= 0.01:
        return "<=1%"
    if relative_error <= 0.05:
        return "<=5%"
    return ">5%"


def counter_to_rows(counter: Counter[str], *, label_key: str, value_key: str) -> list[dict[str, object]]:
    return [{label_key: label, value_key: int(value)} for label, value in counter.items()]


def sample_sort_key(sample_label: str) -> tuple[int, int]:
    left, right = sample_label.split("x", maxsplit=1)
    return int(left), int(right)
