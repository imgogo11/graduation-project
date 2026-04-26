from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TradingRecord


class TradingRepository:
    @staticmethod
    def list_stocks(session: Session, *, import_run_id: int) -> list[dict[str, object]]:
        stmt = (
            select(
                TradingRecord.stock_code,
                func.max(TradingRecord.stock_name).label("stock_name"),
                func.min(TradingRecord.trade_date).label("first_trade_date"),
                func.max(TradingRecord.trade_date).label("last_trade_date"),
                func.count(TradingRecord.id).label("record_count"),
            )
            .where(TradingRecord.import_run_id == import_run_id)
            .group_by(TradingRecord.stock_code)
            .order_by(TradingRecord.stock_code.asc())
        )
        rows = session.execute(stmt).all()
        return [
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "first_trade_date": first_trade_date,
                "last_trade_date": last_trade_date,
                "record_count": record_count,
            }
            for stock_code, stock_name, first_trade_date, last_trade_date, record_count in rows
        ]

    @staticmethod
    def list_records(
        session: Session,
        *,
        import_run_id: int,
        stock_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[TradingRecord]:
        stmt = (
            select(TradingRecord)
            .where(TradingRecord.import_run_id == import_run_id)
            .order_by(TradingRecord.trade_date.asc(), TradingRecord.stock_code.asc())
        )
        if stock_code:
            stmt = stmt.where(TradingRecord.stock_code == stock_code)
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
        stock_code: str,
    ) -> list[tuple[date, Decimal]]:
        stmt = (
            select(TradingRecord.trade_date, TradingRecord.amount)
            .where(TradingRecord.import_run_id == import_run_id)
            .where(TradingRecord.stock_code == stock_code)
            .where(TradingRecord.amount.is_not(None))
            .order_by(TradingRecord.trade_date.asc())
        )
        rows = session.execute(stmt).all()
        return [(trade_date, amount) for trade_date, amount in rows]

    @staticmethod
    def list_volume_series(
        session: Session,
        *,
        import_run_id: int,
        stock_code: str,
    ) -> list[tuple[date, Decimal]]:
        stmt = (
            select(TradingRecord.trade_date, TradingRecord.volume)
            .where(TradingRecord.import_run_id == import_run_id)
            .where(TradingRecord.stock_code == stock_code)
            .order_by(TradingRecord.trade_date.asc())
        )
        rows = session.execute(stmt).all()
        return [(trade_date, volume) for trade_date, volume in rows]

    @staticmethod
    def list_joint_anomaly_rows(
        session: Session,
        *,
        import_run_id: int,
    ) -> list[tuple[str, str | None, date, Decimal, Decimal]]:
        stmt = (
            select(
                TradingRecord.stock_code,
                TradingRecord.stock_name,
                TradingRecord.trade_date,
                TradingRecord.close,
                TradingRecord.volume,
            )
            .where(TradingRecord.import_run_id == import_run_id)
            .order_by(TradingRecord.trade_date.asc(), TradingRecord.stock_code.asc())
        )
        rows = session.execute(stmt).all()
        return [
            (stock_code, stock_name, trade_date, close_value, volume_value)
            for stock_code, stock_name, trade_date, close_value, volume_value in rows
        ]

    @staticmethod
    def list_risk_radar_rows(
        session: Session,
        *,
        import_run_id: int,
    ) -> list[tuple[str, str | None, date, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal | None, Decimal | None]]:
        stmt = (
            select(
                TradingRecord.stock_code,
                TradingRecord.stock_name,
                TradingRecord.trade_date,
                TradingRecord.open,
                TradingRecord.high,
                TradingRecord.low,
                TradingRecord.close,
                TradingRecord.volume,
                TradingRecord.amount,
                TradingRecord.turnover,
            )
            .where(TradingRecord.import_run_id == import_run_id)
            .order_by(TradingRecord.stock_code.asc(), TradingRecord.trade_date.asc())
        )
        rows = session.execute(stmt).all()
        return [
            (
                stock_code,
                stock_name,
                trade_date,
                open_value,
                high_value,
                low_value,
                close_value,
                volume_value,
                amount_value,
                turnover_value,
            )
            for stock_code, stock_name, trade_date, open_value, high_value, low_value, close_value, volume_value, amount_value, turnover_value in rows
        ]

