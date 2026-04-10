from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.imports import ImportRunRepository
from app.schemas.trading import DeleteImportRunResponse, ImportRunRead, ImportStatsRead
from app.services.imports import ImportExecutionError, ImportService, ImportValidationError


router = APIRouter()
service = ImportService()


def _resolve_owner_scope(current_user: User, owner_user_id: int | None) -> int | None:
    if current_user.role == "admin":
        return owner_user_id
    return current_user.id


def _get_visible_run_or_404(session: Session, *, run_id: int, current_user: User):
    owner_scope = None if current_user.role == "admin" else current_user.id
    run = ImportRunRepository.get_visible_run(session, run_id=run_id, owner_user_id=owner_scope)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import run not found")
    return run


@router.get("/runs", response_model=list[ImportRunRead])
def list_import_runs(
    limit: int = 20,
    owner_user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[ImportRunRead]:
    return service.list_runs(
        session,
        owner_user_id=_resolve_owner_scope(current_user, owner_user_id),
        limit=limit,
    )


@router.get("/stats", response_model=ImportStatsRead)
def get_import_stats(
    owner_user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ImportStatsRead:
    return service.build_stats(session, owner_user_id=_resolve_owner_scope(current_user, owner_user_id))


@router.post("/trading", response_model=ImportRunRead)
async def import_trading_file(
    dataset_name: str = Form(...),
    asset_class: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ImportRunRead:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file name is required")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    try:
        run = service.import_uploaded_file(
            session,
            owner=current_user,
            dataset_name=dataset_name,
            asset_class=asset_class,
            original_file_name=file.filename,
            file_bytes=file_bytes,
        )
    except ImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ImportExecutionError as exc:
        if isinstance(exc.__cause__, ImportValidationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.__cause__)) from exc
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return service.serialize_run(
        session,
        run,
        owner_user_id=_resolve_owner_scope(current_user, None),
    )


@router.delete("/runs/{run_id}", response_model=DeleteImportRunResponse)
def delete_import_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DeleteImportRunResponse:
    run = _get_visible_run_or_404(session, run_id=run_id, current_user=current_user)
    service.delete_run(session, run=run)
    return DeleteImportRunResponse(id=run_id, status="deleted")
