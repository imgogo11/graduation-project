from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, utc_now


class UserRepository:
    @staticmethod
    def get_by_id(session: Session, user_id: int) -> User | None:
        return session.get(User, user_id)

    @staticmethod
    def get_by_username(session: Session, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return session.scalar(stmt)

    @staticmethod
    def create_user(
        session: Session,
        *,
        username: str,
        password_hash: str,
        role: str = "user",
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def update_last_login(session: Session, user: User) -> User:
        user.last_login_at = utc_now()
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
