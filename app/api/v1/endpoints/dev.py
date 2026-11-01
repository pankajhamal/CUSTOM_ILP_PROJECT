"""Development-only helpers (disabled outside ENVIRONMENT=development).

The faucet credits a user with test money through the normal ledger path —
a balanced posting DEBIT clearing:rafiki / CREDIT liability:<user>:available —
so the double-entry invariants hold exactly as they would for a real incoming
payment; it just skips the webhook ceremony.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import DBSession
from app.core.config import settings
from app.models.user import User
from app.services.ledger_service import LedgerService
from app.services.webhook_service import CLEARING_ACCOUNT_NAME

router = APIRouter()


class FaucetRequest(BaseModel):
    """Credit a user with test money (amount in integer minor units)."""

    user_id: uuid.UUID
    amount: int = Field(gt=0, le=1_000_000_00, description="Minor units, e.g. 10000 = 100.00")


class FaucetResponse(BaseModel):
    credited: int
    available_balance: int
    transaction_id: uuid.UUID


@router.post(
    "/faucet",
    response_model=FaucetResponse,
    status_code=status.HTTP_200_OK,
    summary="[dev only] Credit a user with test money",
)
async def faucet(payload: FaucetRequest, session: DBSession) -> FaucetResponse:
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faucet is only available in the development environment",
        )

    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    ledger = LedgerService(session)
    accounts = await ledger.ensure_user_accounts(
        user_id=user.id,
        username=user.username,
        asset_code=settings.RAFIKI_ASSET_CODE,
        asset_scale=settings.RAFIKI_ASSET_SCALE,
    )
    available = accounts["available"]
    clearing = await ledger.get_or_create_system_account(
        name=CLEARING_ACCOUNT_NAME,
        asset_code=available.asset_code,
        asset_scale=available.asset_scale,
    )

    txn = await ledger.transfer(
        from_account_id=clearing.id,
        to_account_id=available.id,
        amount=payload.amount,
        reference=f"faucet:{uuid.uuid4()}",
        description="Dev faucet credit",
        enforce_source_non_negative=False,
    )
    await session.commit()

    return FaucetResponse(
        credited=payload.amount,
        available_balance=available.balance,
        transaction_id=txn.id,
    )
