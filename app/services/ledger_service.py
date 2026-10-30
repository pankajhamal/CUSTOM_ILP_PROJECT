"""Double-entry ledger engine — the only place money moves.

Provisioning (``create_account`` / ``ensure_user_accounts``) plus the balanced
posting engine (``post_transaction`` / ``transfer``). Every posting:

  * has >= 2 legs, all amounts positive integers,
  * shares one asset across legs,
  * has ``sum(debits) == sum(credits)``,
  * locks involved accounts ``FOR UPDATE`` (ordered, deadlock-safe),
  * re-checks non-negative floors after applying.

Cached counters on each account move in lockstep with the entries, so they are a
cache of the immutable entry log — never an independent source of truth.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import (
    AccountType,
    EntryDirection,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    NormalBalance,
)


# --- Exceptions ------------------------------------------------------------


class LedgerError(Exception):
    """Base class for ledger errors."""


class UnbalancedTransactionError(LedgerError):
    """Debits did not equal credits (or too few/invalid postings)."""


class AssetMismatchError(LedgerError):
    """Postings referenced more than one asset."""


class InsufficientFundsError(LedgerError):
    """An account would breach its non-negative floor."""


class AccountNotFoundError(LedgerError):
    """A referenced account does not exist."""


class DuplicateTransactionError(LedgerError):
    """A transaction with the same idempotency ``reference`` already exists."""


@dataclass(frozen=True)
class Posting:
    """A single leg of a transaction: push ``amount`` to one side of an account."""

    account_id: uuid.UUID
    direction: EntryDirection
    amount: int


class LedgerService:
    """Stateless helper bound to a session for the duration of a request/txn."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- Account management ------------------------------------------------

    async def get_account_by_name(self, name: str) -> LedgerAccount | None:
        result = await self.session.execute(select(LedgerAccount).where(LedgerAccount.name == name))
        return result.scalar_one_or_none()

    async def create_account(
        self,
        *,
        name: str,
        account_type: AccountType,
        normal_balance: NormalBalance,
        asset_code: str,
        asset_scale: int,
        user_id: uuid.UUID | None = None,
    ) -> LedgerAccount:
        """Create and flush a new ledger account."""
        account = LedgerAccount(
            name=name,
            account_type=account_type,
            normal_balance=normal_balance,
            asset_code=asset_code,
            asset_scale=asset_scale,
            user_id=user_id,
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def get_or_create_system_account(
        self, *, name: str, asset_code: str, asset_scale: int
    ) -> LedgerAccount:
        """Fetch (or create) a debit-normal system account such as ``clearing:rafiki``."""
        existing = await self.get_account_by_name(name)
        if existing is not None:
            return existing
        return await self.create_account(
            name=name,
            account_type=AccountType.CLEARING,
            normal_balance=NormalBalance.DEBIT,
            asset_code=asset_code,
            asset_scale=asset_scale,
        )

    async def ensure_user_accounts(
        self, *, user_id: uuid.UUID, username: str, asset_code: str, asset_scale: int
    ) -> dict[str, LedgerAccount]:
        """Create the per-user liability accounts (``available`` + ``reserved``).

        Both are credit-normal liabilities: money the ASE owes the customer.
        ``available`` is spendable; ``reserved`` holds funds pending an outgoing
        payment. Idempotent: existing accounts are returned as-is.
        """
        accounts: dict[str, LedgerAccount] = {}
        for suffix in ("available", "reserved"):
            name = f"liability:{username}:{suffix}"
            existing = await self.get_account_by_name(name)
            accounts[suffix] = existing or await self.create_account(
                name=name,
                account_type=AccountType.LIABILITY,
                normal_balance=NormalBalance.CREDIT,
                asset_code=asset_code,
                asset_scale=asset_scale,
                user_id=user_id,
            )
        return accounts

    # -- Posting -----------------------------------------------------------

    async def post_transaction(
        self,
        postings: list[Posting],
        *,
        reference: str | None = None,
        description: str | None = None,
        enforce_non_negative: list[uuid.UUID] | None = None,
    ) -> LedgerTransaction:
        """Atomically post a balanced set of entries. The caller owns commit/rollback."""
        if len(postings) < 2:
            raise UnbalancedTransactionError("A transaction needs at least two postings.")
        if any(p.amount <= 0 for p in postings):
            raise UnbalancedTransactionError("All posting amounts must be positive integers.")

        debits = sum(p.amount for p in postings if p.direction is EntryDirection.DEBIT)
        credits = sum(p.amount for p in postings if p.direction is EntryDirection.CREDIT)
        if debits != credits:
            raise UnbalancedTransactionError(f"Unbalanced: debits={debits} != credits={credits}.")

        # Lock involved accounts in a deterministic order (FOR UPDATE is a no-op on SQLite).
        account_ids = sorted({p.account_id for p in postings})
        locked = await self.session.execute(
            select(LedgerAccount)
            .where(LedgerAccount.id.in_(account_ids))
            .order_by(LedgerAccount.id)
            .with_for_update()
        )
        accounts: dict[uuid.UUID, LedgerAccount] = {a.id: a for a in locked.scalars()}

        missing = [str(aid) for aid in account_ids if aid not in accounts]
        if missing:
            raise AccountNotFoundError(f"Unknown account id(s): {', '.join(missing)}")

        assets = {(a.asset_code, a.asset_scale) for a in accounts.values()}
        if len(assets) != 1:
            raise AssetMismatchError(f"Postings span multiple assets: {assets}")
        asset_code, asset_scale = next(iter(assets))

        # Flush the journal inside a SAVEPOINT so a duplicate-reference violation
        # rolls back only this insert (not the caller's surrounding transaction),
        # and only touch counters once the reference is known to be unique.
        txn = LedgerTransaction(reference=reference, description=description)
        try:
            # add INSIDE the savepoint so a duplicate-reference violation rolls the
            # pending object back too, leaving the outer transaction usable.
            async with self.session.begin_nested():
                self.session.add(txn)
                await self.session.flush()
        except IntegrityError as exc:
            raise DuplicateTransactionError(
                f"Transaction with reference {reference!r} already exists."
            ) from exc

        for p in postings:
            account = accounts[p.account_id]
            self.session.add(
                LedgerEntry(
                    transaction_id=txn.id,
                    account_id=account.id,
                    direction=p.direction,
                    amount=p.amount,
                    asset_code=asset_code,
                    asset_scale=asset_scale,
                )
            )
            if p.direction is EntryDirection.DEBIT:
                account.debits_posted += p.amount
            else:
                account.credits_posted += p.amount

        for account_id in enforce_non_negative or []:
            account = accounts.get(account_id)
            if account is not None and account.balance < 0:
                raise InsufficientFundsError(
                    f"Account {account.name!r} would go negative (balance={account.balance})."
                )

        await self.session.flush()
        return txn

    async def transfer(
        self,
        *,
        from_account_id: uuid.UUID,
        to_account_id: uuid.UUID,
        amount: int,
        reference: str | None = None,
        description: str | None = None,
        enforce_source_non_negative: bool = True,
    ) -> LedgerTransaction:
        """Move ``amount`` from one account to another (debit source, credit dest)."""
        return await self.post_transaction(
            [
                Posting(from_account_id, EntryDirection.DEBIT, amount),
                Posting(to_account_id, EntryDirection.CREDIT, amount),
            ],
            reference=reference,
            description=description,
            enforce_non_negative=[from_account_id] if enforce_source_non_negative else None,
        )
