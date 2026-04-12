from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import random


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    instruments: int
    days: int

    @property
    def label(self) -> str:
        return f"{self.instruments}x{self.days}"


SAMPLE_PRESETS: dict[str, BenchmarkSample] = {
    "300x480": BenchmarkSample(instruments=300, days=480),
    "1000x480": BenchmarkSample(instruments=1000, days=480),
    "3000x480": BenchmarkSample(instruments=3000, days=480),
}


def resolve_samples(sample_name: str) -> list[BenchmarkSample]:
    if sample_name == "all":
        return [SAMPLE_PRESETS[key] for key in ("300x480", "1000x480", "3000x480")]
    try:
        return [SAMPLE_PRESETS[sample_name]]
    except KeyError as exc:
        raise ValueError(f"Unsupported benchmark sample: {sample_name}") from exc


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


def build_query_windows(dates: list[date], *, total: int, seed: int) -> list[tuple[date, date, int]]:
    rng = random.Random(seed)
    windows: list[tuple[date, date, int]] = []
    n = len(dates)
    for _ in range(total):
        left = rng.randrange(0, max(1, n - 5))
        right = rng.randrange(left, n)
        interval_length = right - left + 1
        k = rng.randint(1, interval_length)
        windows.append((dates[left], dates[right], k))
    return windows
