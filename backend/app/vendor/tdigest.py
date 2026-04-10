"""Minimal vendored t-digest implementation used for approximate quantiles.

This module is adapted for the project from the MIT-licensed
CamDavidsonPilon/tdigest implementation:
https://github.com/CamDavidsonPilon/tdigest
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(slots=True)
class Centroid:
    mean: float
    count: float

    def update(self, value: float, weight: float) -> None:
        next_count = self.count + weight
        self.mean += weight * (value - self.mean) / next_count
        self.count = next_count


class TDigest:
    """Approximate quantile digest with merge support."""

    def __init__(self, delta: float = 0.01, K: int = 25) -> None:
        if delta <= 0:
            raise ValueError("delta must be greater than 0")
        if K <= 0:
            raise ValueError("K must be greater than 0")

        self.delta = float(delta)
        self.K = int(K)
        self.n = 0.0
        self._centroids: list[Centroid] = []
        self._compressed = True

    def __len__(self) -> int:
        return len(self._centroids)

    def __add__(self, other: "TDigest") -> "TDigest":
        merged = self.copy()
        merged.merge(other)
        return merged

    def copy(self) -> "TDigest":
        digest = TDigest(self.delta, self.K)
        digest.n = self.n
        digest._centroids = [Centroid(item.mean, item.count) for item in self._centroids]
        digest._compressed = self._compressed
        return digest

    def update(self, value: float, weight: float = 1.0) -> None:
        if weight <= 0:
            raise ValueError("weight must be greater than 0")

        self._centroids.append(Centroid(float(value), float(weight)))
        self.n += float(weight)
        self._compressed = False

        if len(self._centroids) > self.K / self.delta:
            self.compress()

    def batch_update(self, values: Iterable[float], weight: float = 1.0) -> None:
        for value in values:
            self.update(value, weight)
        if not self._compressed:
            self.compress()

    def merge(self, other: "TDigest") -> None:
        if other.n == 0:
            return

        self.n += other.n
        self._centroids.extend(Centroid(item.mean, item.count) for item in other._centroids)
        self._compressed = False
        self.compress()

    def percentile(self, percentile: float) -> float:
        if not 0.0 <= percentile <= 100.0:
            raise ValueError("percentile must be between 0 and 100, inclusive")
        if self.n == 0:
            raise ValueError("cannot query an empty t-digest")

        self.compress()

        if len(self._centroids) == 1:
            return self._centroids[0].mean
        if percentile == 0.0:
            return self._centroids[0].mean
        if percentile == 100.0:
            return self._centroids[-1].mean

        target_rank = percentile / 100.0 * (self.n - 1.0)
        centers: list[float] = []
        cumulative = 0.0
        for centroid in self._centroids:
            centers.append(cumulative + (centroid.count - 1.0) / 2.0)
            cumulative += centroid.count

        if target_rank <= centers[0]:
            return self._centroids[0].mean

        for index in range(1, len(self._centroids)):
            right_center = centers[index]
            if target_rank <= right_center:
                left_center = centers[index - 1]
                left_value = self._centroids[index - 1].mean
                right_value = self._centroids[index].mean
                if math.isclose(left_center, right_center):
                    return right_value
                ratio = (target_rank - left_center) / (right_center - left_center)
                return left_value + ratio * (right_value - left_value)

        return self._centroids[-1].mean

    def centroids_to_list(self) -> list[dict[str, float]]:
        self.compress()
        return [{"m": item.mean, "c": item.count} for item in self._centroids]

    def compress(self) -> None:
        if self._compressed:
            return
        if not self._centroids:
            self._compressed = True
            return

        items = sorted(self._centroids, key=lambda item: item.mean)
        merged: list[Centroid] = []
        total_count = self.n
        cumulative = 0.0
        current = Centroid(items[0].mean, items[0].count)

        for candidate in items[1:]:
            proposed_count = current.count + candidate.count
            q = (cumulative + proposed_count / 2.0) / total_count if total_count else 0.0
            threshold = max(1.0, 4.0 * total_count * self.delta * q * (1.0 - q))
            if proposed_count <= threshold:
                current.update(candidate.mean, candidate.count)
                continue

            merged.append(current)
            cumulative += current.count
            current = Centroid(candidate.mean, candidate.count)

        merged.append(current)
        self._centroids = merged
        self._compressed = True
