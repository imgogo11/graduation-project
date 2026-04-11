from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.imports import ImportRunRepository
from app.schemas.trading import (
    TradingRiskRadarCalendarRead,
    TradingRiskRadarEventContextRead,
    TradingRiskRadarEventListRead,
    TradingRiskRadarInstrumentListRead,
    TradingRiskRadarOverviewRead,
)
from app.services.risk_radar import (
    AlgoIndexNotReadyError,
    RiskRadarNotFoundError,
    RiskRadarValidationError,
    risk_radar_service,
)


router = APIRouter()
COMPLETED_RUN_STATUSES = ("completed",)


def _ensure_run_visible(session: Session, *, import_run_id: int, current_user: User) -> None:
    owner_scope = None if current_user.role == "admin" else current_user.id
    run = ImportRunRepository.get_visible_run(
        session,
        run_id=import_run_id,
        owner_user_id=owner_scope,
        statuses=COMPLETED_RUN_STATUSES,
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import run not found")


@router.get("/overview", response_model=TradingRiskRadarOverviewRead)
def get_risk_radar_overview(
    import_run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRiskRadarOverviewRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return risk_radar_service.get_overview(import_run_id)
    except AlgoIndexNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/events", response_model=TradingRiskRadarEventListRead)
def list_risk_radar_events(
    import_run_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    instrument_code: str | None = None,
    severity: str | None = None,
    top_n: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRiskRadarEventListRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return risk_radar_service.list_events(
            import_run_id,
            start_date=start_date,
            end_date=end_date,
            instrument_code=instrument_code,
            severity=severity,
            top_n=top_n,
        )
    except RiskRadarValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AlgoIndexNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/instruments", response_model=TradingRiskRadarInstrumentListRead)
def list_risk_radar_instruments(
    import_run_id: int,
    severity: str | None = None,
    top_n: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRiskRadarInstrumentListRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return risk_radar_service.list_instruments(import_run_id, severity=severity, top_n=top_n)
    except RiskRadarValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AlgoIndexNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/calendar", response_model=TradingRiskRadarCalendarRead)
def list_risk_radar_calendar(
    import_run_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRiskRadarCalendarRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return risk_radar_service.list_calendar(import_run_id, start_date=start_date, end_date=end_date)
    except RiskRadarValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AlgoIndexNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/event-context", response_model=TradingRiskRadarEventContextRead)
def get_risk_radar_event_context(
    import_run_id: int,
    instrument_code: str,
    trade_date: date,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRiskRadarEventContextRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return risk_radar_service.get_event_context(
            import_run_id,
            instrument_code=instrument_code,
            trade_date=trade_date,
        )
    except RiskRadarValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RiskRadarNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AlgoIndexNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
