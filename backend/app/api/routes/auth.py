from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.schemas.auth import AuthTokenRead, LoginRequest, RegisterRequest, UserRead
from app.services.auth import AuthConflictError, AuthInvalidCredentialsError, AuthService, AuthValidationError


router = APIRouter()
service = AuthService()


@router.post("/register", response_model=AuthTokenRead)
def register_user(payload: RegisterRequest, session: Session = Depends(get_db_session)) -> AuthTokenRead:
    try:
        user = service.register_user(session, username=payload.username, password=payload.password)
    except AuthConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AuthValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return service.build_token_response(user)


@router.post("/login", response_model=AuthTokenRead)
def login_user(payload: LoginRequest, session: Session = Depends(get_db_session)) -> AuthTokenRead:
    try:
        user = service.authenticate_user(session, username=payload.username, password=payload.password)
    except (AuthInvalidCredentialsError, AuthValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return service.build_token_response(user)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
