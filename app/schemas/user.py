"""User request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Payload to register a new account holder."""

    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_.-]+$")
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)


class LedgerAccountRead(BaseModel):
    """A provisioned ledger account, as returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    account_type: str
    normal_balance: str
    asset_code: str
    asset_scale: int
    balance: int


class UserRead(BaseModel):
    """Public representation of a user and their provisioned accounts."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: EmailStr | None = None
    is_active: bool
    created_at: datetime
    ledger_accounts: list[LedgerAccountRead] = []
