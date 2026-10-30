"""Outgoing payment initiation (Phase 5).

send_payment() orchestrates the sender side of the outgoing flow:
  1. resolve the sender wallet + ledger accounts, pre-check spendable balance,
  2. create a receiver (incoming payment) at the destination wallet,
  3. create a Rafiki quote (fixed-send) against that receiver,
  4. place the reserve hold (available -> reserved) for the quoted debit amount,
  5. create the outgoing payment in Rafiki.

Funding and settlement happen later via webhooks (outgoing_payment.created ->
deposit liquidity; .completed -> settle; .failed -> release).
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import WalletAddress
from app.schemas.payment import QuoteInfo, SendPaymentRequest, SendPaymentResponse
from app.services.ledger_service import InsufficientFundsError, LedgerService
from app.services.rafiki_client import RafikiClient, RafikiClientError

logger = logging.getLogger(__name__)


def _normalize_receiver(receiver: str) -> str:
    """Turn a ``$host/path`` payment pointer into its ``https://host/path`` URL."""
    if receiver.startswith("$"):
        return "https://" + receiver[1:]
    return receiver


async def send_payment(
    *,
    payload: SendPaymentRequest,
    session: AsyncSession,
    rafiki: RafikiClient,
) -> SendPaymentResponse:
    wallet = await session.get(WalletAddress, payload.sender_wallet_address_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Sender wallet not found")
    if not wallet.rafiki_wallet_address_id:
        raise HTTPException(status_code=409, detail="Sender wallet is not synced with Rafiki")

    user = await session.get(User, wallet.user_id)
    if user is None:  # pragma: no cover - referential integrity guards this
        raise HTTPException(status_code=404, detail="Owning user not found")

    ledger = LedgerService(session)
    asset_scale = int(wallet.asset_scale)
    accounts = await ledger.ensure_user_accounts(
        user_id=user.id,
        username=user.username,
        asset_code=wallet.asset_code,
        asset_scale=asset_scale,
    )
    available, reserved = accounts["available"], accounts["reserved"]

    # Pre-check spendable balance before creating any Rafiki resources.
    if available.balance < payload.amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient funds: balance={available.balance}, requested={payload.amount}",
        )

    receiver_url = _normalize_receiver(payload.receiver)

    # 1) Receiver (incoming payment) at the destination, then 2) quote against it.
    try:
        receiver = await rafiki.create_receiver(
            wallet_address_url=receiver_url, description=payload.description
        )
        quote = await rafiki.create_quote(
            wallet_address_id=wallet.rafiki_wallet_address_id,
            receiver=receiver["id"],
            debit_amount=payload.amount,
            asset_code=wallet.asset_code,
            asset_scale=asset_scale,
        )
    except RafikiClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Quote failed: {exc}"
        ) from exc

    debit_amount = int(quote["debitAmount"]["value"])
    receive_amount = int(quote["receiveAmount"]["value"])

    # 3) Reserve hold: available -> reserved for the quoted debit amount.
    try:
        hold = await ledger.transfer(
            from_account_id=available.id,
            to_account_id=reserved.id,
            amount=debit_amount,
            description=f"Reserve hold for payment to {receiver_url}",
            enforce_source_non_negative=True,
        )
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc

    # 4) Create the outgoing payment in Rafiki.
    try:
        payment = await rafiki.create_outgoing_payment(
            wallet_address_id=wallet.rafiki_wallet_address_id,
            quote_id=quote["id"],
        )
    except RafikiClientError as exc:
        # Roll back the hold (and everything else) so we don't strand funds.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Outgoing payment creation failed: {exc}",
        ) from exc

    await session.commit()

    return SendPaymentResponse(
        payment_id=payment["id"],
        status=payment.get("state", "PENDING"),
        quote=QuoteInfo(
            quote_id=quote["id"],
            debit_amount=debit_amount,
            receive_amount=receive_amount,
            asset_code=wallet.asset_code,
            asset_scale=asset_scale,
        ),
        hold_transaction_id=hold.id,
    )
