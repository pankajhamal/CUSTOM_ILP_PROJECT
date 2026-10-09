"""Wallet addresses (payment pointers) mapped to Rafiki wallet-address IDs."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class WalletAddress(Base, TimestampMixin):
    """A user wallet address synchronized with Rafiki wallet address"""

    __tablename__ = "wallet_addresses"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    wallet_address: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)

    #Rafiki wallet_address_id
    rafiki_wallet_address_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(8), nullable=False)
    asset_scale: Mapped[int] = mapped_column(String(8), nullable=False)

    user: Mapped["User"] = relationship(back_populates="wallet_addresses")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<WalletAddress {self.address!r}>"
