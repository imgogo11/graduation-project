from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminManagedUserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    has_business_data: bool


class AdminManagedUserUpdateRequest(BaseModel):
    username: str | None = None
    password: str | None = None
    is_active: bool | None = None


class AdminManagedUserDeleteResponse(BaseModel):
    id: int
    status: str
