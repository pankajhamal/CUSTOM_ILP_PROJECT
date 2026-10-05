"""Double-entry ledger engine.

Phase 2 scope: account provisioning only — create accounts and ensure a user's
per-user accounts exist. Balanced posting (``post_transaction``), reserve holds,
and settlement are added in a later phase when money starts moving. This remains
the only place money will be allowed to move.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import AccountType, LedgerAccount, NormalBalance


class LedgerService:
    """Stateless helper bound to a session for the duration of a request/txn."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_account_by_name(self, name: str) -> LedgerAccount | None:
        result = await self.session.execute(
            select(LedgerAccount).where(LedgerAccount.name == name)
        )
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
