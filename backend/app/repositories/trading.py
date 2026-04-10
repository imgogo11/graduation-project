from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TradingRecord


class TradingRepository:
    @staticmethod
    def list_instruments(session: Session, *, import_run_id: int) -> list[dict[str, object]]:
        stmt = (
            select(
                TradingRecord.instrument_code,
                func.max(TradingRecord.instrument_name).label("instrument_name"),
                func.min(TradingRecord.trade_date).label("first_trade_date"),
                func.max(TradingRecord.trade_date).label("last_trade_date"),
                func.count(TradingRecord.id).label("record_count"),
            )
            .where(TradingRecord.import_run_id == import_run_id)
            .group_by(TradingRecord.instrument_code)
            .order_by(TradingRecord.instrument_code.asc())
        )
        rows = session.execute(stmt).all()
        return [
            {
                "instrument_code": instrument_code,
                "instrument_name": instrument_name,
                "first_trade_date": first_trade_date,
                "last_trade_date": last_trade_date,
                "record_count": record_count,
            }
            for instrument_code, instrument_name, first_trade_date, last_trade_date, record_count in rows
        ]

    @staticmethod
    def list_records(
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[TradingRecord]:
        stmt = (
            select(TradingRecord)
            .where(TradingRecord.import_run_id == import_run_id)
            .order_by(TradingRecord.trade_date.asc(), TradingRecord.instrument_code.asc())
        )
        if instrument_code:
            stmt = stmt.where(TradingRecord.instrument_code == instrument_code)
        if start_date:
            stmt = stmt.where(TradingRecord.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(TradingRecord.trade_date <= end_date)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(session.scalars(stmt))

    @staticmethod
    def list_amount_series(
        session: Session,
        *,
        import_run_id: int,
        instrument_code: str,
    ) -> list[tuple[date, Decimal]]:
        stmt = (
            select(TradingRecord.trade_date, TradingRecord.amount)
            .where(TradingRecord.import_run_id == import_run_id)
            .where(TradingRecord.instrument_code == instrument_code)
            .order_by(TradingRecord.trade_date.asc())
        )
        rows = session.execute(stmt).all()
        return [(trade_date, amount) for trade_date, amount in rows]
