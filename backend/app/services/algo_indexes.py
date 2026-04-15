from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import shutil
import threading
from typing import Any
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.algo_bridge.adapters.trading import load_algo_module, query_historical_dominance_3d
from app.algo_bridge.loaders.trading import (
    build_trading_risk_radar_events,
    scale_amount,
    scale_signal_metric,
    scale_volume,
)
from app.algo_bridge.tdigest import RangeKthTDigestBlockIndex
from app.models import ImportRun, utc_now
from app.repositories.trading import TradingRepository
from app.schemas.trading import (
    AlgoIndexStatusRead,
    TradingStockRiskProfileRead,
    TradingRiskRadarCalendarDayRead,
    TradingRiskRadarEventRead,
    TradingRiskRadarOverviewRead,
)


ALGO_INDEX_METADATA_KEY = "algo_index"
RISK_RADAR_SNAPSHOT_VERSION = "stock-v2"
ALGO_INDEX_STATUS_PENDING = "pending"
ALGO_INDEX_STATUS_BUILDING = "building"
ALGO_INDEX_STATUS_READY = "ready"
ALGO_INDEX_STATUS_FAILED = "failed"
RISK_RADAR_LOOKBACK_WINDOW = 20
RISK_RADAR_OVERVIEW_LIMIT = 5
RISK_RADAR_EVENT_WINDOW_SIZES = (20, 60, 120)
RISK_RADAR_LOCAL_PEAK_RADIUS = 20


class AlgoIndexNotReadyError(RuntimeError):
    """Raised when a requested algorithm index is not yet ready."""


@dataclass(slots=True)
class StockAlgoIndex:
    stock_code: str
    stock_name: str | None
    trade_dates: list[date]
    close_values: list[float]
    volume_values: list[float]
    amplitude_values: list[float]
    amount_values: list[float | None]
    volumes_scaled: list[int]
    amplitudes_scaled: list[int]
    amounts_scaled: list[int]
    date_to_index: dict[date, int]
    amount_tree: Any | None
    volume_tree: Any
    amplitude_tree: Any
    volume_tdigest: RangeKthTDigestBlockIndex
    amplitude_tdigest: RangeKthTDigestBlockIndex


@dataclass(slots=True)
class RiskRadarIndexCache:
    import_run_id: int
    generated_at: datetime
    lookback_window: int
    events: list[TradingRiskRadarEventRead]
    overview: TradingRiskRadarOverviewRead
    stock_profiles: list[TradingStockRiskProfileRead]
    calendar_rows: list[TradingRiskRadarCalendarDayRead]
    stocks: dict[str, StockAlgoIndex]
    reuse_count: int = 0


class AlgoIndexManager:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="algo-index")
        self._lock = threading.RLock()
        self._futures: dict[int, Future[None]] = {}
        self._cache: dict[int, RiskRadarIndexCache] = {}

    def prepare_after_import(self, import_run_id: int) -> None:
        self._update_status(
            import_run_id,
            {
                "status": ALGO_INDEX_STATUS_PENDING,
                "build_started_at": None,
                "build_completed_at": None,
                "build_duration_ms": None,
                "stock_count": None,
                "event_count": None,
                "last_error": None,
            },
        )

    def enqueue_build(self, import_run_id: int, *, force: bool = False) -> None:
        if get_settings().app_env == "test":
            self.build_for_run(import_run_id, force=force)
            return
        with self._lock:
            existing = self._futures.get(import_run_id)
            if existing is not None and not existing.done() and not force:
                return
            self._futures[import_run_id] = self._executor.submit(self.build_for_run, import_run_id, force)

    def invalidate(self, import_run_id: int) -> None:
        with self._lock:
            self._cache.pop(import_run_id, None)
        snapshot_dir = self._snapshot_dir(import_run_id)
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)

    def reset(self) -> None:
        with self._lock:
            self._cache.clear()
            self._futures.clear()

    def get_status(self, import_run_id: int) -> AlgoIndexStatusRead:
        session = get_session_factory()()
        try:
            run = session.get(ImportRun, import_run_id)
            metadata = dict(run.metadata_json or {}) if run is not None else {}
        finally:
            session.close()
        algo_metadata = metadata.get(ALGO_INDEX_METADATA_KEY, {})
        with self._lock:
            reuse_count = self._cache.get(import_run_id).reuse_count if import_run_id in self._cache else 0
        return self._build_status_read(import_run_id, algo_metadata, reuse_count)

    def get_cache(self, import_run_id: int) -> RiskRadarIndexCache:
        with self._lock:
            cached = self._cache.get(import_run_id)
            if cached is not None:
                cached.reuse_count += 1
                return cached
        status = self.get_status(import_run_id)
        if status.status != ALGO_INDEX_STATUS_READY:
            raise AlgoIndexNotReadyError(f"算法索引当前状态为 {status.status}，请稍后再试。")
        snapshot_path = self._snapshot_path(import_run_id)
        if not snapshot_path.exists():
            self.build_for_run(import_run_id, force=True)
            with self._lock:
                rebuilt = self._cache.get(import_run_id)
                if rebuilt is None:
                    raise AlgoIndexNotReadyError("算法索引重建失败，请稍后重试。")
                rebuilt.reuse_count += 1
                return rebuilt
        try:
            cache, needs_rewrite = self._load_cache_from_snapshot(import_run_id, snapshot_path)
        except (ValidationError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            snapshot_path.unlink(missing_ok=True)
            self.build_for_run(import_run_id, force=True)
            with self._lock:
                rebuilt = self._cache.get(import_run_id)
                if rebuilt is None:
                    raise AlgoIndexNotReadyError("算法索引重建失败，请稍后重试。")
                rebuilt.reuse_count += 1
                return rebuilt
        with self._lock:
            cache.reuse_count += 1
            self._cache[import_run_id] = cache
            if needs_rewrite:
                self._write_snapshot(cache)
            return cache

    def build_for_run(self, import_run_id: int, force: bool = False) -> None:
        status = self.get_status(import_run_id)
        if status.status == ALGO_INDEX_STATUS_BUILDING and not force:
            return
        started_at = utc_now()
        self._update_status(
            import_run_id,
            {
                "status": ALGO_INDEX_STATUS_BUILDING,
                "build_started_at": started_at.isoformat(),
                "build_completed_at": None,
                "build_duration_ms": None,
                "last_error": None,
            },
        )
        try:
            cache = self._build_cache(import_run_id)
            self._write_snapshot(cache)
            finished_at = utc_now()
            duration_ms = int(max((finished_at - started_at).total_seconds() * 1000.0, 0.0))
            with self._lock:
                self._cache[import_run_id] = cache
            self._update_status(
                import_run_id,
                {
                    "status": ALGO_INDEX_STATUS_READY,
                    "build_completed_at": finished_at.isoformat(),
                    "build_duration_ms": duration_ms,
                    "stock_count": len(cache.stocks),
                    "event_count": len(cache.events),
                    "last_error": None,
                },
            )
        except Exception as exc:
            finished_at = utc_now()
            duration_ms = int(max((finished_at - started_at).total_seconds() * 1000.0, 0.0))
            self._update_status(
                import_run_id,
                {
                    "status": ALGO_INDEX_STATUS_FAILED,
                    "build_completed_at": finished_at.isoformat(),
                    "build_duration_ms": duration_ms,
                    "last_error": str(exc),
                },
            )
            raise

    def _build_cache(self, import_run_id: int) -> RiskRadarIndexCache:
        session = get_session_factory()()
        try:
            rows = TradingRepository.list_risk_radar_rows(session, import_run_id=import_run_id)
        finally:
            session.close()
        if not rows:
            raise ValueError(f"No trading rows found for import_run_id={import_run_id}")

        stocks = self._build_stock_indexes(rows)
        events = build_trading_risk_radar_events(
            import_run_id=import_run_id,
            rows=rows,
            lookback_window=RISK_RADAR_LOOKBACK_WINDOW,
        )
        if not events:
            raise ValueError(f"数据不足分析：风险雷达至少需要 {RISK_RADAR_LOOKBACK_WINDOW} 日历史窗口和有效样本")

        dominance_result = query_historical_dominance_3d(
            [event.return_z20_scaled for event in events],
            [event.volume_ratio20_scaled for event in events],
            [event.amplitude_ratio20_scaled for event in events],
        )

        event_rows: list[TradingRiskRadarEventRead] = []
        for historical_sample_count, (event, dominated_count) in enumerate(
            zip(events, dominance_result.dominated_counts, strict=True)
        ):
            joint_percentile = float(dominated_count) / float(historical_sample_count) if historical_sample_count else 0.0
            severity = self._severity(joint_percentile)
            if severity is None:
                continue
            event_rows.append(
                TradingRiskRadarEventRead(
                    stock_code=event.stock_code,
                    stock_name=event.stock_name,
                    trade_date=event.trade_date,
                    daily_return=round(event.daily_return, 6),
                    return_z20=round(event.return_z20, 6),
                    volume_ratio20=round(event.volume_ratio20, 6),
                    amplitude_ratio20=round(event.amplitude_ratio20, 6),
                    historical_dominated_count=int(dominated_count),
                    historical_sample_count=historical_sample_count,
                    joint_percentile=round(joint_percentile, 6),
                    severity=severity,
                    cause_label=self._cause_label(
                        return_z20=event.return_z20,
                        volume_ratio20=event.volume_ratio20,
                        amplitude_ratio20=event.amplitude_ratio20,
                    ),
                )
            )
        event_rows.sort(
            key=lambda item: (
                item.joint_percentile,
                item.historical_dominated_count,
                item.return_z20,
                item.volume_ratio20,
                item.amplitude_ratio20,
                item.trade_date.toordinal(),
            ),
            reverse=True,
        )
        stock_profiles = self._build_stock_profiles(event_rows)
        calendar_rows = self._build_calendar_rows(event_rows)
        generated_at = utc_now()
        overview = TradingRiskRadarOverviewRead(
            import_run_id=import_run_id,
            lookback_window=RISK_RADAR_LOOKBACK_WINDOW,
            generated_at=generated_at,
            total_events=len(event_rows),
            impacted_stock_count=len(stock_profiles),
            medium_count=sum(1 for item in event_rows if item.severity == "medium"),
            high_count=sum(1 for item in event_rows if item.severity == "high"),
            critical_count=sum(1 for item in event_rows if item.severity == "critical"),
            top_stocks=stock_profiles[:RISK_RADAR_OVERVIEW_LIMIT],
            busiest_dates=sorted(
                calendar_rows,
                key=lambda item: (item.event_count, item.critical_count, item.max_joint_percentile, item.trade_date.toordinal()),
                reverse=True,
            )[:RISK_RADAR_OVERVIEW_LIMIT],
        )
        return RiskRadarIndexCache(
            import_run_id=import_run_id,
            generated_at=generated_at,
            lookback_window=RISK_RADAR_LOOKBACK_WINDOW,
            events=event_rows,
            overview=overview,
            stock_profiles=stock_profiles,
            calendar_rows=calendar_rows,
            stocks=stocks,
        )

    def _build_stock_indexes(self, rows: list[tuple[str, str | None, date, Any, Any, Any, Any, Any, Any]]) -> dict[str, StockAlgoIndex]:
        module = load_algo_module()
        grouped: dict[str, list[tuple[str, str | None, date, Any, Any, Any, Any, Any, Any]]] = {}
        for row in rows:
            grouped.setdefault(row[0], []).append(row)

        indexes: dict[str, StockAlgoIndex] = {}
        for stock_code, stock_rows in grouped.items():
            trade_dates: list[date] = []
            close_values: list[float] = []
            volume_values: list[float] = []
            amplitude_values: list[float] = []
            amount_values: list[float | None] = []
            volumes_scaled: list[int] = []
            amplitudes_scaled: list[int] = []
            amounts_scaled: list[int] = []
            has_amount_data = False
            stock_name = stock_rows[0][1]

            for _, _, trade_date, open_value, high_value, low_value, close_value, volume_value, amount_value in stock_rows:
                open_number = float(open_value)
                high_number = float(high_value)
                low_number = float(low_value)
                close_number = float(close_value)
                volume_number = float(volume_value)
                amplitude_number = max((high_number - low_number) / open_number, 0.0) if open_number > 0 else 0.0

                trade_dates.append(trade_date)
                close_values.append(close_number)
                volume_values.append(volume_number)
                amplitude_values.append(amplitude_number)
                volumes_scaled.append(scale_volume(volume_value))
                amplitudes_scaled.append(scale_signal_metric(amplitude_number))
                if amount_value is None:
                    amount_values.append(None)
                    amounts_scaled.append(0)
                else:
                    has_amount_data = True
                    amount_values.append(float(amount_value))
                    amounts_scaled.append(scale_amount(amount_value))

            indexes[stock_code] = StockAlgoIndex(
                stock_code=stock_code,
                stock_name=stock_name,
                trade_dates=trade_dates,
                close_values=close_values,
                volume_values=volume_values,
                amplitude_values=amplitude_values,
                amount_values=amount_values,
                volumes_scaled=volumes_scaled,
                amplitudes_scaled=amplitudes_scaled,
                amounts_scaled=amounts_scaled,
                date_to_index={trade_day: index for index, trade_day in enumerate(trade_dates)},
                amount_tree=module.RangeMaxSegmentTree(amounts_scaled) if has_amount_data else None,
                volume_tree=module.RangeKthPersistentSegmentTree(volumes_scaled),
                amplitude_tree=module.RangeKthPersistentSegmentTree(amplitudes_scaled),
                volume_tdigest=RangeKthTDigestBlockIndex(volumes_scaled),
                amplitude_tdigest=RangeKthTDigestBlockIndex(amplitudes_scaled),
            )
        return indexes

    def _build_stock_profiles(self, events: list[TradingRiskRadarEventRead]) -> list[TradingStockRiskProfileRead]:
        grouped: dict[str, list[TradingRiskRadarEventRead]] = {}
        for event in events:
            grouped.setdefault(event.stock_code, []).append(event)
        rows: list[TradingStockRiskProfileRead] = []
        for stock_code, stock_events in grouped.items():
            top_event = max(stock_events, key=lambda item: (item.joint_percentile, item.trade_date.toordinal()))
            latest_event = max(stock_events, key=lambda item: item.trade_date.toordinal())
            rows.append(
                TradingStockRiskProfileRead(
                    stock_code=stock_code,
                    stock_name=top_event.stock_name,
                    event_count=len(stock_events),
                    medium_count=sum(1 for item in stock_events if item.severity == "medium"),
                    high_count=sum(1 for item in stock_events if item.severity == "high"),
                    critical_count=sum(1 for item in stock_events if item.severity == "critical"),
                    max_joint_percentile=round(max(item.joint_percentile for item in stock_events), 6),
                    avg_joint_percentile=round(sum(item.joint_percentile for item in stock_events) / float(len(stock_events)), 6),
                    latest_event_date=latest_event.trade_date,
                    top_event_date=top_event.trade_date,
                    top_event_severity=top_event.severity,
                )
            )
        rows.sort(
            key=lambda item: (item.critical_count, item.high_count, item.max_joint_percentile, item.event_count, item.latest_event_date.toordinal()),
            reverse=True,
        )
        return rows

    def _build_calendar_rows(self, events: list[TradingRiskRadarEventRead]) -> list[TradingRiskRadarCalendarDayRead]:
        grouped: dict[date, list[TradingRiskRadarEventRead]] = {}
        for event in events:
            grouped.setdefault(event.trade_date, []).append(event)
        rows: list[TradingRiskRadarCalendarDayRead] = []
        for trade_day, day_events in sorted(grouped.items()):
            rows.append(
                TradingRiskRadarCalendarDayRead(
                    trade_date=trade_day,
                    event_count=len(day_events),
                    impacted_stock_count=len({item.stock_code for item in day_events}),
                    medium_count=sum(1 for item in day_events if item.severity == "medium"),
                    high_count=sum(1 for item in day_events if item.severity == "high"),
                    critical_count=sum(1 for item in day_events if item.severity == "critical"),
                    max_joint_percentile=round(max(item.joint_percentile for item in day_events), 6),
                )
            )
        return rows

    def _write_snapshot(self, cache: RiskRadarIndexCache) -> None:
        snapshot_dir = self._snapshot_dir(cache.import_run_id)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": RISK_RADAR_SNAPSHOT_VERSION,
            "overview": cache.overview.model_dump(mode="json"),
            "events": [item.model_dump(mode="json") for item in cache.events],
            "stock_profiles": [item.model_dump(mode="json") for item in cache.stock_profiles],
            "calendar_rows": [item.model_dump(mode="json") for item in cache.calendar_rows],
        }
        self._snapshot_path(cache.import_run_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_cache_from_snapshot(self, import_run_id: int, snapshot_path: Path) -> tuple[RiskRadarIndexCache, bool]:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != RISK_RADAR_SNAPSHOT_VERSION:
            raise ValueError("Unsupported risk radar snapshot schema")
        session = get_session_factory()()
        try:
            rows = TradingRepository.list_risk_radar_rows(session, import_run_id=import_run_id)
        finally:
            session.close()
        return RiskRadarIndexCache(
            import_run_id=import_run_id,
            generated_at=self._parse_datetime(payload["overview"].get("generated_at")) or utc_now(),
            lookback_window=int(payload["overview"]["lookback_window"]),
            events=[TradingRiskRadarEventRead.model_validate(item) for item in payload["events"]],
            overview=TradingRiskRadarOverviewRead.model_validate(payload["overview"]),
            stock_profiles=[TradingStockRiskProfileRead.model_validate(item) for item in payload["stock_profiles"]],
            calendar_rows=[TradingRiskRadarCalendarDayRead.model_validate(item) for item in payload["calendar_rows"]],
            stocks=self._build_stock_indexes(rows),
        ), False

    def _update_status(self, import_run_id: int, fields: dict[str, Any]) -> None:
        session = get_session_factory()()
        try:
            run = session.get(ImportRun, import_run_id)
            if run is None:
                return
            metadata = dict(run.metadata_json or {})
            algo_metadata = dict(metadata.get(ALGO_INDEX_METADATA_KEY, {}))
            algo_metadata.update(fields)
            metadata[ALGO_INDEX_METADATA_KEY] = algo_metadata
            run.metadata_json = metadata
            session.add(run)
            session.commit()
        finally:
            session.close()

    def _build_status_read(self, import_run_id: int, algo_metadata: dict[str, Any], reuse_count: int) -> AlgoIndexStatusRead:
        status = str(algo_metadata.get("status") or ALGO_INDEX_STATUS_PENDING)
        return AlgoIndexStatusRead(
            import_run_id=import_run_id,
            status=status,
            is_ready=status == ALGO_INDEX_STATUS_READY,
            build_started_at=self._parse_datetime(algo_metadata.get("build_started_at")),
            build_completed_at=self._parse_datetime(algo_metadata.get("build_completed_at")),
            build_duration_ms=self._parse_int(algo_metadata.get("build_duration_ms")),
            stock_count=self._parse_int(algo_metadata.get("stock_count")),
            event_count=self._parse_int(algo_metadata.get("event_count")),
            reuse_count=reuse_count,
            last_error=self._parse_text(algo_metadata.get("last_error")),
        )

    def _snapshot_dir(self, import_run_id: int) -> Path:
        return get_settings().project_root / "data" / "algo_indexes" / f"run_{import_run_id}"

    def _snapshot_path(self, import_run_id: int) -> Path:
        return self._snapshot_dir(import_run_id) / "risk_radar_snapshot.json"

    def _severity(self, joint_percentile: float) -> str | None:
        if joint_percentile >= 0.99:
            return "critical"
        if joint_percentile >= 0.95:
            return "high"
        if joint_percentile >= 0.90:
            return "medium"
        return None

    def _cause_label(self, *, return_z20: float, volume_ratio20: float, amplitude_ratio20: float) -> str:
        if return_z20 >= 3.0 and volume_ratio20 >= 2.0 and amplitude_ratio20 >= 2.0:
            return "three-factor resonance"
        if return_z20 >= volume_ratio20 and return_z20 >= amplitude_ratio20:
            return "price-led"
        if volume_ratio20 >= amplitude_ratio20:
            return "volume-led"
        return "amplitude-led"

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return None

    def _parse_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_text(self, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)


algo_index_manager = AlgoIndexManager()



