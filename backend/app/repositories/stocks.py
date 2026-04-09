# 作用:
# - 这是股票仓储模块，用来封装股票代码主数据维护和股票日线查询逻辑。
# 关联文件:
# - 被 backend/app/services/imports.py 用于保证股票主表与日线表的写入顺序。
# - 被 backend/app/api/routes/stocks.py 用于提供只读查询接口。
# - 相关 ORM 实体定义在 backend/app/models/entities.py。
#
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import StockDailyPrice, StockSymbol


class StockRepository:
    @staticmethod
    def ensure_symbols(session: Session, *, symbols: list[dict[str, str | int | None]]) -> None:
        identifiers = [str(item["symbol"]) for item in symbols]
        existing = set(session.scalars(select(StockSymbol.symbol).where(StockSymbol.symbol.in_(identifiers))))
        for item in symbols:
            symbol = str(item["symbol"])
            if symbol in existing:
                current = session.get(StockSymbol, symbol)
                if current is not None:
                    current.market = item.get("market") if isinstance(item.get("market"), str) else current.market
                    current.last_import_run_id = (
                        int(item["last_import_run_id"]) if item.get("last_import_run_id") is not None else current.last_import_run_id
                    )
                    session.add(current)
                continue
            session.add(
                StockSymbol(
                    symbol=symbol,
                    market=item.get("market") if isinstance(item.get("market"), str) else None,
                    last_import_run_id=int(item["last_import_run_id"]) if item.get("last_import_run_id") is not None else None,
                )
            )
        session.flush()

    @staticmethod
    def list_daily_prices(
        session: Session,
        *,
        symbol: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[StockDailyPrice]:
        stmt = select(StockDailyPrice).order_by(desc(StockDailyPrice.trade_date)).limit(limit)
        if symbol:
            stmt = stmt.where(StockDailyPrice.symbol == symbol)
        if start_date:
            stmt = stmt.where(StockDailyPrice.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(StockDailyPrice.trade_date <= end_date)
        return list(session.scalars(stmt))

    @staticmethod
    def list_amount_series(
        session: Session,
        *,
        symbol: str,
        adjust: str = "qfq",
    ) -> list[tuple[date, Decimal]]:
        stmt = (
            select(StockDailyPrice.trade_date, StockDailyPrice.amount)
            .where(StockDailyPrice.symbol == symbol)
            .where(StockDailyPrice.adjust == adjust)
            .where(StockDailyPrice.amount.is_not(None))
            .order_by(StockDailyPrice.trade_date.asc())
        )
        rows = session.execute(stmt).all()
        return [(trade_date, amount) for trade_date, amount in rows]
