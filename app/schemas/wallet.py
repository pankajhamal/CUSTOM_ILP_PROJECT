"""Wallet address schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WalletAddressCreate(BaseModel):
    """Payload to provision a wallet address for an existing user."""
    user_id: uuid.UUID


class WalletAddressRead(BaseModel):
    """Public representation of a provisioned wallet address."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    wallet_address: str
    rafiki_wallet_address_id: str
    asset_code: str
    asset_scale: str
    created_at: datetime
