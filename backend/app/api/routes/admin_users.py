from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.users import UserRepository
from app.schemas.admin_users import (
    AdminManagedUserDeleteResponse,
    AdminManagedUserRead,
    AdminManagedUserUpdateRequest,
)
from app.services.admin_users import (
    AdminUserConflictError,
    AdminUserDeleteBlockedError,
    AdminUserService,
    AdminUserValidationError,
)


router = APIRouter()
service = AdminUserService()


def _get_target_user_or_404(session: Session, *, user_id: int) -> User:
    user = UserRepository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=list[AdminManagedUserRead])
def list_admin_users(
    query: str | None = None,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> list[AdminManagedUserRead]:
    return service.list_managed_users(session, query=query)


@router.patch("/{user_id}", response_model=AdminManagedUserRead)
def update_admin_user(
    user_id: int,
    payload: AdminManagedUserUpdateRequest,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserRead:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        return service.update_managed_user(
            session,
            actor_admin=current_admin,
            target_user=target_user,
            username=payload.username,
            password=payload.password,
            is_active=payload.is_active,
        )
    except AdminUserConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AdminUserValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{user_id}/disable", response_model=AdminManagedUserRead)
def disable_admin_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserRead:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        return service.set_managed_user_active(
            session,
            actor_admin=current_admin,
            target_user=target_user,
            is_active=False,
        )
    except AdminUserValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{user_id}/enable", response_model=AdminManagedUserRead)
def enable_admin_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserRead:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        return service.set_managed_user_active(
            session,
            actor_admin=current_admin,
            target_user=target_user,
            is_active=True,
        )
    except AdminUserValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{user_id}", response_model=AdminManagedUserDeleteResponse)
def delete_admin_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserDeleteResponse:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        service.delete_managed_user(session, actor_admin=current_admin, target_user=target_user)
    except AdminUserDeleteBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AdminUserValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AdminManagedUserDeleteResponse(id=user_id, status="deleted")
