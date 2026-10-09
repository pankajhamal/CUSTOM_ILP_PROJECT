"""User registration and lookup."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.ledger_service import LedgerService

router = APIRouter()


async def _load_user_with_accounts(session, user_id: uuid.UUID) -> User | None:
    """Fetch a user with their ledger accounts eagerly loaded (async-safe)."""
    result = await session.execute(
        select(User).options(selectinload(User.ledger_accounts)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account holder",
)
async def create_user(payload: UserCreate, session: DBSession) -> User:
    """User Register"""
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        ) from exc

    ledger = LedgerService(session)
    await ledger.ensure_user_accounts(
        user_id=user.id,
        username=user.username,
        asset_code=settings.default_asset_code,
        asset_scale=settings.default_asset_scale,
    )

    await session.commit()
    return await _load_user_with_accounts(session, user.id)


@router.get("/{user_id}", response_model=UserRead, summary="Fetch a user")
async def get_user(user_id: uuid.UUID, session: DBSession) -> User:
    user = await _load_user_with_accounts(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
