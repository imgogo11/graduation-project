from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import shutil
import threading
from typing import Any
import numpy as np
import pandas as pd
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
RISK_RADAR_SNAPSHOT_VERSION = "stock-v3"
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
    rvol20_values: list[float]
    range_shock_values: list[float]
    amount_values: list[float | None]
    volumes_scaled: list[int]
    rvol20_scaled: list[int]
    range_shock_scaled: list[int]
    amounts_scaled: list[int]
    date_to_index: dict[date, int]
    amount_tree: Any | None
    volume_tree: Any
    rvol20_tree: Any
    range_shock_tree: Any
    volume_tdigest: RangeKthTDigestBlockIndex
    signal_scale_divisor: float = 1_000_000.0
    volume_scale_divisor: float = 10_000.0


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
            if status.status == ALGO_INDEX_STATUS_FAILED and status.last_error:
                raise AlgoIndexNotReadyError(f"算法索引构建失败：{status.last_error}")
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
            [event.return_shock_scaled for event in events],
            [event.rvol20_scaled for event in events],
            [event.range_shock_scaled for event in events],
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
                    return_z20=round(event.return_shock, 6),
                    volume_ratio20=round(event.liquidity_shock, 6),
                    amplitude_ratio20=round(event.range_shock, 6),
                    return_shock=round(event.return_shock, 6),
                    vol_regime=round(event.vol_regime, 6) if event.vol_regime is not None else None,
                    range_shock=round(event.range_shock, 6),
                    rvol20=round(event.rvol20, 6),
                    liquidity_shock=round(event.liquidity_shock, 6),
                    drawdown_pressure=round(event.drawdown_pressure, 6),
                    score_return_shock=round(event.score_return_shock, 6) if event.score_return_shock is not None else None,
                    score_vol_regime=round(event.score_vol_regime, 6) if event.score_vol_regime is not None else None,
                    score_range_shock=round(event.score_range_shock, 6) if event.score_range_shock is not None else None,
                    score_rvol20=round(event.score_rvol20, 6) if event.score_rvol20 is not None else None,
                    score_liquidity_shock=round(event.score_liquidity_shock, 6)
                    if event.score_liquidity_shock is not None
                    else None,
                    score_drawdown_pressure=round(event.score_drawdown_pressure, 6)
                    if event.score_drawdown_pressure is not None
                    else None,
                    historical_dominated_count=int(dominated_count),
                    historical_sample_count=historical_sample_count,
                    joint_percentile=round(joint_percentile, 6),
                    severity=severity,
                    cause_label=self._cause_label(
                        return_shock=event.return_shock,
                        liquidity_shock=event.rvol20,
                        range_shock=event.range_shock,
                    ),
                )
            )
        event_rows.sort(
            key=lambda item: (
                item.joint_percentile,
                item.historical_dominated_count,
                item.return_shock,
                item.rvol20,
                item.range_shock,
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

    def _build_stock_indexes(
        self,
        rows: list[tuple[str, str | None, date, Any, Any, Any, Any, Any, Any, Any]],
    ) -> dict[str, StockAlgoIndex]:
        module = load_algo_module()
        grouped: dict[str, list[tuple[str, str | None, date, Any, Any, Any, Any, Any, Any, Any]]] = {}
        for row in rows:
            grouped.setdefault(row[0], []).append(row)

        indexes: dict[str, StockAlgoIndex] = {}
        for stock_code, stock_rows in grouped.items():
            trade_dates: list[date] = []
            close_values: list[float] = []
            volume_values: list[float] = []
            rvol20_values: list[float] = []
            range_shock_values: list[float] = []
            amount_values: list[float | None] = []
            volumes_scaled: list[int] = []
            rvol20_scaled: list[int] = []
            range_shock_scaled: list[int] = []
            amounts_scaled: list[int] = []
            has_amount_data = False
            stock_name = stock_rows[0][1]
            stock_frame = pd.DataFrame(
                [
                    {
                        "trade_date": trade_date,
                        "open": float(open_value),
                        "high": float(high_value),
                        "low": float(low_value),
                        "close": float(close_value),
                        "volume": float(volume_value),
                        "amount": float(amount_value) if amount_value is not None else math.nan,
                    }
                    for (
                        _,
                        _,
                        trade_date,
                        open_value,
                        high_value,
                        low_value,
                        close_value,
                        volume_value,
                        amount_value,
                        _turnover_value,
                    ) in stock_rows
                ]
            ).sort_values("trade_date").reset_index(drop=True)
            previous_close = stock_frame["close"].shift(1)
            true_range = pd.concat(
                [
                    stock_frame["high"] - stock_frame["low"],
                    (stock_frame["high"] - previous_close).abs(),
                    (stock_frame["low"] - previous_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            atr20 = true_range.rolling(window=20, min_periods=20).mean()
            volume_ma20 = stock_frame["volume"].rolling(window=20, min_periods=20).mean()
            stock_frame["rvol20"] = stock_frame["volume"] / volume_ma20.replace(0.0, np.nan)
            stock_frame["range_shock"] = true_range / atr20.replace(0.0, np.nan)

            for row in stock_frame.itertuples(index=False):
                trade_dates.append(row.trade_date)
                close_values.append(float(row.close))
                volume_values.append(float(row.volume))
                rvol_value = float(row.rvol20) if pd.notna(row.rvol20) else 0.0
                range_shock_value = float(row.range_shock) if pd.notna(row.range_shock) else 0.0
                rvol20_values.append(rvol_value)
                range_shock_values.append(range_shock_value)
                volumes_scaled.append(scale_volume(Decimal(str(row.volume))))
                rvol20_scaled.append(scale_signal_metric(rvol_value))
                range_shock_scaled.append(scale_signal_metric(range_shock_value))
                if pd.isna(row.amount):
                    amount_values.append(None)
                    amounts_scaled.append(0)
                else:
                    has_amount_data = True
                    amount_values.append(float(row.amount))
                    amounts_scaled.append(scale_amount(Decimal(str(row.amount))))

            indexes[stock_code] = StockAlgoIndex(
                stock_code=stock_code,
                stock_name=stock_name,
                trade_dates=trade_dates,
                close_values=close_values,
                volume_values=volume_values,
                rvol20_values=rvol20_values,
                range_shock_values=range_shock_values,
                amount_values=amount_values,
                volumes_scaled=volumes_scaled,
                rvol20_scaled=rvol20_scaled,
                range_shock_scaled=range_shock_scaled,
                amounts_scaled=amounts_scaled,
                date_to_index={trade_day: index for index, trade_day in enumerate(trade_dates)},
                amount_tree=module.RangeMaxSegmentTree(amounts_scaled) if has_amount_data else None,
                volume_tree=module.RangeKthPersistentSegmentTree(volumes_scaled),
                rvol20_tree=module.RangeKthPersistentSegmentTree(rvol20_scaled),
                range_shock_tree=module.RangeKthPersistentSegmentTree(range_shock_scaled),
                volume_tdigest=RangeKthTDigestBlockIndex(volumes_scaled),
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

    def _cause_label(self, *, return_shock: float, liquidity_shock: float, range_shock: float) -> str:
        if return_shock >= 3.0 and liquidity_shock >= 2.0 and range_shock >= 1.5:
            return "三因子共振"
        if return_shock >= liquidity_shock and return_shock >= range_shock:
            return "价格主导"
        if liquidity_shock >= range_shock:
            return "成交活跃"
        return "波幅放大"

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



