"""Wallet-address provisioning: create locally and sync with Rafiki."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DBSession, RafikiDep
from app.core.config import settings
from app.models.user import User
from app.models.wallet import WalletAddress
from app.schemas.wallet import WalletAddressCreate, WalletAddressRead
from app.services.rafiki_client import RafikiClientError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=WalletAddressRead,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a wallet address and sync it with Rafiki",
)
async def create_wallet(
    payload: WalletAddressCreate,
    session: DBSession,
    rafiki: RafikiDep,
) -> WalletAddress:
    """Create wallet address through Rafiki and presist mapping locally"""
    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    asset_id = payload.asset_id or settings.default_asset_id
    asset_code = payload.asset_code or settings.default_asset_code
    asset_scale = (
        payload.asset_scale if payload.asset_scale is not None else settings.default_asset_scale
    )
    # address = f"{settings.wallet_address_base_url.rstrip('/')}/{user.username}"

    rafiki_wallet_address_id: str | None = None
    if asset_id:
        try:
            result = await rafiki.create_wallet_address(
                address=address,
                asset_id=asset_id,
                public_name=payload.public_name,
            )
            rafiki_wallet_address_id = result.get("id")
        except RafikiClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Rafiki wallet-address creation failed: {exc}",
            ) from exc
    else:
        logger.warning(
            "No asset id configured; creating wallet %s locally without Rafiki sync.", address
        )

    wallet = WalletAddress(
        user_id=user.id,
        address=address,
        public_name=payload.public_name,
        rafiki_wallet_address_id=rafiki_wallet_address_id,
        asset_id=asset_id,
        asset_code=asset_code,
        asset_scale=asset_scale,
    )
    session.add(wallet)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wallet address already exists",
        ) from exc

    await session.refresh(wallet)
    return wallet


@router.get("/{wallet_id}", response_model=WalletAddressRead, summary="Fetch a wallet address")
async def get_wallet(wallet_id: uuid.UUID, session: DBSession) -> WalletAddress:
    wallet = (
        await session.execute(select(WalletAddress).where(WalletAddress.id == wallet_id))
    ).scalar_one_or_none()
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return wallet
