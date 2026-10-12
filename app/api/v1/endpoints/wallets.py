"""Wallet-address provisioning: create locally and sync with Rafiki."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession, RafikiDep
from app.models.user import User
from app.models.wallet import WalletAddress
from app.schemas.wallet import WalletAddressCreate, WalletAddressRead
from app.services.wallet_service import create_wallet_address

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create wallet address through Rafiki",
)
async def create_wallet(
    payload: WalletAddressCreate, session: DBSession, rafiki: RafikiDep
) -> WalletAddressRead:
    """Create Wallet Address for existing user"""
    return await create_wallet_address(
        payload=payload, 
        session=session,
        rafiki=rafiki
    )


@router.get("/{wallet_id}", response_model=None, summary="Fetch a wallet address")
async def get_wallet(wallet_id: uuid.UUID, session: DBSession) -> WalletAddress:
    wallet = (
        await session.execute(select(WalletAddress).where(WalletAddress.id == wallet_id))
    ).scalar_one_or_none()
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return wallet
