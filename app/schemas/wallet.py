"""Wallet address schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WalletAddressCreate(BaseModel):
    """Payload to provision a wallet address for an existing user."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123456",
                "public_name": "Pankaj",
            }
        }
    )

    user_id: uuid.UUID
    public_name: str | None = Field(default=None, max_length=128)
    asset_id: str | None = Field(
        default=None, description="Optional Rafiki asset id; omit to use DEFAULT_ASSET_ID."
    )
    asset_code: str | None = Field(default=None, max_length=8)
    asset_scale: int | None = Field(default=None, ge=0, le=18)


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
