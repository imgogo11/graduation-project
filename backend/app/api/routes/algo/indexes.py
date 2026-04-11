from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.imports import ImportRunRepository
from app.schemas.trading import AlgoIndexStatusRead
from app.services.algo_indexes import algo_index_manager


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


@router.get("/status", response_model=AlgoIndexStatusRead)
def get_algo_index_status(
    import_run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AlgoIndexStatusRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    return algo_index_manager.get_status(import_run_id)


@router.post("/rebuild", response_model=AlgoIndexStatusRead)
def rebuild_algo_index(
    import_run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AlgoIndexStatusRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    algo_index_manager.prepare_after_import(import_run_id)
    try:
        algo_index_manager.enqueue_build(import_run_id, force=True)
    except Exception:
        pass
    return algo_index_manager.get_status(import_run_id)
