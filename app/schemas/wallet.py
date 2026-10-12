"""Wallet address schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WalletAddressCreate(BaseModel):
    """Payload to provision a wallet address for an existing user."""
    user_id: uuid.UUID


class WalletAddressRead(BaseModel):
    """Public representation of a provisioned wallet address."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    address: str
    public_name: str | None = None
    rafiki_wallet_address_id: str | None = None
    asset_id: str | None = None
    asset_code: str
    asset_scale: int
    created_at: datetime
