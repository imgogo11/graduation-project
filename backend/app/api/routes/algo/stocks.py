from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.schemas.algo import StockRangeMaxAmountRead
from app.services.algo_stocks import StockAlgoQueryNotFoundError, StockAlgoQueryValidationError, StockAlgoService


router = APIRouter()
service = StockAlgoService()


@router.get("/range-max-amount", response_model=StockRangeMaxAmountRead)
def get_range_max_amount(
    symbol: str,
    start_date: date,
    end_date: date,
    adjust: str = "qfq",
    session: Session = Depends(get_db_session),
) -> StockRangeMaxAmountRead:
    try:
        return service.query_range_max_amount(
            session,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except StockAlgoQueryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StockAlgoQueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
