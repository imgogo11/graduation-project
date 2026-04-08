# 作用:
# - 这是股票查询路由模块，用来暴露股票日线数据的最小只读接口。
# 关联文件:
# - 被 backend/app/api/router.py 统一挂载到 `/api/stocks/daily-prices`。
# - 依赖 backend/app/repositories/stocks.py 查询已入库的股票日线记录。
# - 返回模型定义在 backend/app/schemas/api.py。
#
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repositories.stocks import StockRepository
from app.schemas.api import StockDailyPriceRead


router = APIRouter()


@router.get("/daily-prices", response_model=list[StockDailyPriceRead])
def list_daily_prices(
    symbol: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
    session: Session = Depends(get_db_session),
) -> list[StockDailyPriceRead]:
    rows = StockRepository.list_daily_prices(
        session,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return [StockDailyPriceRead.model_validate(item) for item in rows]
