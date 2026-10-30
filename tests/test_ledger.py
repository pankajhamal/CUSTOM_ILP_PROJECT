"""Tests for double-entry invariants, reserve holds, and transaction idempotency."""

from __future__ import annotations

import uuid

import pytest

from app.models.ledger import AccountType, EntryDirection, NormalBalance
from app.models.user import User
from app.services.ledger_service import (
    AccountNotFoundError,
    AssetMismatchError,
    DuplicateTransactionError,
    InsufficientFundsError,
    LedgerService,
    Posting,
    UnbalancedTransactionError,
)


async def _provision(session):
    """Create a user with available/reserved accounts and a clearing account."""
    user = User(username="alice", email="alice@example.com", hashed_password="x")
    session.add(user)
    await session.flush()

    ledger = LedgerService(session)
    accounts = await ledger.ensure_user_accounts(
        user_id=user.id, username="alice", asset_code="USD", asset_scale=2
    )
    clearing = await ledger.get_or_create_system_account(
        name="clearing:rafiki", asset_code="USD", asset_scale=2
    )
    return ledger, accounts, clearing


async def _credit_incoming(ledger, clearing, available, amount):
    """Simulate an incoming payment: DEBIT clearing / CREDIT available."""
    return await ledger.transfer(
        from_account_id=clearing.id,
        to_account_id=available.id,
        amount=amount,
        enforce_source_non_negative=False,
    )


async def test_incoming_payment_credits_available(session):
    ledger, accounts, clearing = await _provision(session)
    available = accounts["available"]

    await _credit_incoming(ledger, clearing, available, 1000)

    assert available.balance == 1000  # credit-normal liability
    assert clearing.balance == 1000  # debit-normal clearing


async def test_reserve_hold_moves_available_to_reserved(session):
    ledger, accounts, clearing = await _provision(session)
    available, reserved = accounts["available"], accounts["reserved"]
    await _credit_incoming(ledger, clearing, available, 1000)

    await ledger.transfer(from_account_id=available.id, to_account_id=reserved.id, amount=500)

    assert available.balance == 500
    assert reserved.balance == 500


async def test_full_outgoing_cycle_conserves_money(session):
    ledger, accounts, clearing = await _provision(session)
    available, reserved = accounts["available"], accounts["reserved"]
    await _credit_incoming(ledger, clearing, available, 1000)

    # hold 500, then settle 500 (reserved -> clearing)
    await ledger.transfer(from_account_id=available.id, to_account_id=reserved.id, amount=500)
    await ledger.transfer(from_account_id=reserved.id, to_account_id=clearing.id, amount=500)

    assert available.balance == 500
    assert reserved.balance == 0
    # clearing: +1000 (incoming) then -500 (settle) == 500
    assert clearing.balance == 500


async def test_insufficient_funds_blocks_overdraft(session):
    ledger, accounts, clearing = await _provision(session)
    available, reserved = accounts["available"], accounts["reserved"]
    await _credit_incoming(ledger, clearing, available, 100)

    with pytest.raises(InsufficientFundsError):
        await ledger.transfer(from_account_id=available.id, to_account_id=reserved.id, amount=500)


async def test_unbalanced_transaction_rejected(session):
    ledger, accounts, clearing = await _provision(session)
    available = accounts["available"]

    with pytest.raises(UnbalancedTransactionError):
        await ledger.post_transaction(
            [
                Posting(clearing.id, EntryDirection.DEBIT, 100),
                Posting(available.id, EntryDirection.CREDIT, 200),
            ]
        )


async def test_single_posting_rejected(session):
    ledger, accounts, clearing = await _provision(session)
    with pytest.raises(UnbalancedTransactionError):
        await ledger.post_transaction([Posting(clearing.id, EntryDirection.DEBIT, 100)])


async def test_non_positive_amount_rejected(session):
    ledger, accounts, clearing = await _provision(session)
    with pytest.raises(UnbalancedTransactionError):
        await ledger.post_transaction(
            [
                Posting(clearing.id, EntryDirection.DEBIT, 0),
                Posting(accounts["available"].id, EntryDirection.CREDIT, 0),
            ]
        )


async def test_duplicate_reference_rejected(session):
    ledger, accounts, clearing = await _provision(session)
    available = accounts["available"]
    await _credit_incoming(ledger, clearing, available, 1000)

    await ledger.transfer(
        from_account_id=available.id,
        to_account_id=accounts["reserved"].id,
        amount=100,
        reference="unique-ref-1",
    )
    with pytest.raises(DuplicateTransactionError):
        await ledger.transfer(
            from_account_id=available.id,
            to_account_id=accounts["reserved"].id,
            amount=100,
            reference="unique-ref-1",
        )
    # The duplicate must not have moved money.
    assert available.balance == 900
    assert accounts["reserved"].balance == 100


async def test_asset_mismatch_rejected(session):
    ledger, accounts, clearing = await _provision(session)
    eur = await ledger.create_account(
        name="liability:alice:eur",
        account_type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
        asset_code="EUR",
        asset_scale=2,
    )
    with pytest.raises(AssetMismatchError):
        await ledger.post_transaction(
            [
                Posting(accounts["available"].id, EntryDirection.DEBIT, 100),
                Posting(eur.id, EntryDirection.CREDIT, 100),
            ]
        )


async def test_unknown_account_rejected(session):
    ledger, accounts, clearing = await _provision(session)
    with pytest.raises(AccountNotFoundError):
        await ledger.post_transaction(
            [
                Posting(accounts["available"].id, EntryDirection.DEBIT, 100),
                Posting(uuid.uuid4(), EntryDirection.CREDIT, 100),
            ]
        )


async def test_entries_sum_matches_counters(session):
    """The cached counters must equal the sum of immutable entries."""
    from sqlalchemy import func, select

    from app.models.ledger import LedgerEntry

    ledger, accounts, clearing = await _provision(session)
    available = accounts["available"]
    await _credit_incoming(ledger, clearing, available, 1000)
    await ledger.transfer(from_account_id=available.id, to_account_id=accounts["reserved"].id, amount=300)

    total_credits = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == available.id,
                LedgerEntry.direction == EntryDirection.CREDIT,
            )
        )
    ).scalar_one()
    total_debits = (
        await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.account_id == available.id,
                LedgerEntry.direction == EntryDirection.DEBIT,
            )
        )
    ).scalar_one()

    assert total_credits == available.credits_posted == 1000
    assert total_debits == available.debits_posted == 300
