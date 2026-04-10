from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.vendor.tdigest import TDigest


DEFAULT_TDIGEST_DELTA = 0.01
DEFAULT_TDIGEST_K = 25
DEFAULT_TDIGEST_BLOCK_SIZE = 128


@dataclass(frozen=True, slots=True)
class RangeKthTDigestResult:
    kth_value_scaled: int
    matched_indices: list[int]
    approximation_note: str


class RangeKthTDigestBlockIndex:
    """Approximate Kth-largest queries by merging block-level t-digests."""

    def __init__(
        self,
        values: Sequence[int],
        *,
        block_size: int = DEFAULT_TDIGEST_BLOCK_SIZE,
        delta: float = DEFAULT_TDIGEST_DELTA,
        K: int = DEFAULT_TDIGEST_K,
    ) -> None:
        if block_size <= 0:
            raise ValueError("block_size must be greater than 0")

        self._values = [int(value) for value in values]
        self._n = len(self._values)
        self._block_size = int(block_size)
        self._delta = float(delta)
        self._K = int(K)
        self._block_digests = self._build_block_digests()

    def size(self) -> int:
        return self._n

    def query_inclusive(self, left: int, right: int, k: int) -> RangeKthTDigestResult:
        self._validate_query(left, right, k)
        digest = TDigest(delta=self._delta, K=self._K)

        prefix_end = min(right + 1, self._align_up(left))
        if left < prefix_end:
            digest.batch_update(self._values[left:prefix_end])

        suffix_start = max(prefix_end, self._align_down(right + 1))
        if suffix_start < right + 1:
            digest.batch_update(self._values[suffix_start : right + 1])

        for block_index in range(prefix_end // self._block_size, suffix_start // self._block_size):
            digest.merge(self._block_digests[block_index])

        interval_length = right - left + 1
        quantile = self._quantile_for_k(interval_length, k)
        estimated_value = digest.percentile(quantile * 100.0)
        interval_values = self._values[left : right + 1]
        bounded_value = min(max(estimated_value, min(interval_values)), max(interval_values))

        return RangeKthTDigestResult(
            kth_value_scaled=int(round(bounded_value)),
            matched_indices=[],
            approximation_note=(
                "t-digest returns an approximate quantile-based Kth volume and does not provide exact matched trade dates."
            ),
        )

    def _build_block_digests(self) -> list[TDigest]:
        digests: list[TDigest] = []
        for start in range(0, self._n, self._block_size):
            digest = TDigest(delta=self._delta, K=self._K)
            digest.batch_update(self._values[start : start + self._block_size])
            digests.append(digest)
        return digests

    def _align_up(self, index: int) -> int:
        return ((index + self._block_size - 1) // self._block_size) * self._block_size

    def _align_down(self, index: int) -> int:
        return (index // self._block_size) * self._block_size

    @staticmethod
    def _quantile_for_k(interval_length: int, k: int) -> float:
        if interval_length == 1:
            return 1.0
        return (interval_length - k) / (interval_length - 1)

    def _validate_query(self, left: int, right: int, k: int) -> None:
        if self._n == 0:
            raise IndexError("t-digest index is empty")
        if left < 0 or right < 0 or left >= self._n or right >= self._n:
            raise IndexError("query indices are out of range")
        if left > right:
            raise ValueError("left index must be less than or equal to right index")

        interval_length = right - left + 1
        if k <= 0 or k > interval_length:
            raise ValueError("k must be between 1 and the interval length")
