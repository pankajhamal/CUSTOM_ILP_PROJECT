"""User profile and credentials."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.ledger import LedgerAccount


class User(Base, TimestampMixin):
    """An account holder served by this ASE."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    ledger_accounts: Mapped[list["LedgerAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.username!r}>"
