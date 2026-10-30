"""Double-entry ledger models: accounts, transactions, and immutable entries.

Every money movement is a :class:`LedgerTransaction` of two or more
:class:`LedgerEntry` postings whose debit and credit amounts are equal. Entries
are append-only; each :class:`LedgerAccount` caches ``debits_posted`` /
``credits_posted`` (updated atomically with a balanced posting) for O(1) balances.

A customer's spendable money is a **liability** of the ASE (credit-normal); the
Rafiki clearing account tracks the settlement position (debit-normal).
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Amount, Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class AccountType(str, enum.Enum):
    """Classification of a ledger account."""

    LIABILITY = "liability"  # money the ASE owes a customer
    ASSET = "asset"  # money/claims the ASE holds
    CLEARING = "clearing"  # settlement position vs. Rafiki/network
    EQUITY = "equity"
    REVENUE = "revenue"  # fees, spreads


class NormalBalance(str, enum.Enum):
    """The side on which an account's balance naturally increases."""

    DEBIT = "debit"
    CREDIT = "credit"


class EntryDirection(str, enum.Enum):
    """The side a single posting lands on."""

    DEBIT = "debit"
    CREDIT = "credit"


# Non-native enums => stored as VARCHAR + CHECK, portable across PG and SQLite.
# values_callable persists the lowercase *values* ("liability") rather than the
# member *names* ("LIABILITY"), so DB rows match the API and raw SQL filters work.
def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


_account_type_enum = Enum(
    AccountType, native_enum=False, length=20, name="account_type", values_callable=_enum_values
)
_normal_balance_enum = Enum(
    NormalBalance, native_enum=False, length=10, name="normal_balance", values_callable=_enum_values
)
_direction_enum = Enum(
    EntryDirection, native_enum=False, length=10, name="entry_direction", values_callable=_enum_values
)


class LedgerAccount(Base, TimestampMixin):
    """A single account in the double-entry ledger."""

    __tablename__ = "ledger_accounts"

    id: Mapped[uuid.UUID] = uuid_pk()
    # System accounts (e.g. clearing:rafiki) have no owner.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Stable, unique machine name, e.g. "liability:alice:available".
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    account_type: Mapped[AccountType] = mapped_column(_account_type_enum, nullable=False)
    normal_balance: Mapped[NormalBalance] = mapped_column(_normal_balance_enum, nullable=False)

    asset_code: Mapped[str] = mapped_column(String(8), nullable=False)
    asset_scale: Mapped[int] = mapped_column(Integer, nullable=False)

    # Cached counters — maintained atomically with balanced postings.
    debits_posted: Mapped[int] = mapped_column(Amount, default=0, nullable=False)
    credits_posted: Mapped[int] = mapped_column(Amount, default=0, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="ledger_accounts")

    __table_args__ = (
        CheckConstraint("debits_posted >= 0", name="debits_non_negative"),
        CheckConstraint("credits_posted >= 0", name="credits_non_negative"),
    )

    @property
    def balance(self) -> int:
        """Current balance in minor units, signed per the account's normal side."""
        if self.normal_balance is NormalBalance.CREDIT:
            return self.credits_posted - self.debits_posted
        return self.debits_posted - self.credits_posted

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LedgerAccount {self.name!r} balance={self.balance}>"


class LedgerTransaction(Base, TimestampMixin):
    """A balanced group of postings (a journal entry)."""

    __tablename__ = "ledger_transactions"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Optional external/idempotency reference (e.g. a payment or webhook id).
    reference: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255))

    entries: Mapped[list["LedgerEntry"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LedgerTransaction {self.reference or self.id}>"


class LedgerEntry(Base, TimestampMixin):
    """An immutable single-sided posting against one account."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("ledger_transactions.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False
    )

    direction: Mapped[EntryDirection] = mapped_column(_direction_enum, nullable=False)
    amount: Mapped[int] = mapped_column(Amount, nullable=False)
    asset_code: Mapped[str] = mapped_column(String(8), nullable=False)
    asset_scale: Mapped[int] = mapped_column(Integer, nullable=False)

    transaction: Mapped["LedgerTransaction"] = relationship(back_populates="entries")
    account: Mapped["LedgerAccount"] = relationship()

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_ledger_entries_account_txn", "account_id", "transaction_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LedgerEntry {self.direction.value} {self.amount} acct={self.account_id}>"
