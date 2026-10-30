"""Webhook event dispatcher.

Given a verified :class:`RafikiWebhookPayload`, this service:

  1. records the event for idempotency (unique ``rafiki_event_id``), short-circuiting
     duplicates without touching the ledger;
  2. dispatches by event type to the matching handler;
  3. marks the event processed.

The caller (the webhook endpoint) owns commit/rollback. On any handler error we
raise so the request rolls back — including the idempotency row — letting Rafiki
retry the delivery as if new.

Phase 4 handles ``incoming_payment.completed`` → ledger credit. Note: a fully
Rafiki-consistent flow should also withdraw the incoming-payment liquidity
(``createIncomingPaymentWithdrawal`` keyed by the webhook id); that's a follow-up
since it needs a real payment to exercise.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import LedgerAccount
from app.models.user import User
from app.models.wallet import WalletAddress
from app.models.webhook_event import WebhookEvent, WebhookStatus
from app.schemas.webhook import RafikiWebhookPayload, WebhookAck, WebhookEventType
from app.services.ledger_service import LedgerService

logger = logging.getLogger(__name__)

# System settlement account shared across all users.
CLEARING_ACCOUNT_NAME = "clearing:rafiki"


class WebhookProcessingError(Exception):
    """A webhook could not be processed; the request should roll back (5xx)."""


class WebhookService:
    def __init__(self, session: AsyncSession, rafiki_client=None) -> None:  # noqa: ANN001
        self.session = session
        self.ledger = LedgerService(session)
        self.rafiki = rafiki_client

    # -- Entry point -------------------------------------------------------

    async def process(self, payload: RafikiWebhookPayload) -> WebhookAck:
        event = await self._record_event(payload)
        if event is None:
            logger.info("Duplicate webhook %s (%s); skipping.", payload.id, payload.type)
            return WebhookAck(event_id=payload.id, duplicate=True, handled=True)

        handled = await self._dispatch(payload)

        event.status = WebhookStatus.PROCESSED
        event.processed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return WebhookAck(event_id=payload.id, duplicate=False, handled=handled)

    # -- Idempotency -------------------------------------------------------

    async def _record_event(self, payload: RafikiWebhookPayload) -> WebhookEvent | None:
        """Insert the idempotency row. Returns ``None`` if already seen."""
        event = WebhookEvent(
            rafiki_event_id=payload.id,
            event_type=payload.type,
            payload=payload.model_dump(),
            status=WebhookStatus.RECEIVED,
        )
        try:
            # add INSIDE the savepoint so a unique violation rolls the pending
            # object back too, leaving the outer transaction usable.
            async with self.session.begin_nested():
                self.session.add(event)
                await self.session.flush()
        except IntegrityError:
            return None
        return event

    # -- Dispatch ----------------------------------------------------------

    async def _dispatch(self, payload: RafikiWebhookPayload) -> bool:
        """Route to a handler. Returns False for events we deliberately ignore."""
        handlers = {
            WebhookEventType.INCOMING_PAYMENT_COMPLETED.value: self._on_incoming_completed,
            WebhookEventType.OUTGOING_PAYMENT_CREATED.value: self._on_outgoing_created,
            WebhookEventType.OUTGOING_PAYMENT_COMPLETED.value: self._on_outgoing_completed,
            WebhookEventType.OUTGOING_PAYMENT_FAILED.value: self._on_outgoing_failed,
        }
        handler = handlers.get(payload.type)
        if handler is None:
            logger.info("No handler for webhook type %s; acknowledging.", payload.type)
            return False
        await handler(payload)
        return True

    # -- Handlers ----------------------------------------------------------

    async def _on_incoming_completed(self, payload: RafikiWebhookPayload) -> None:
        """Credit a user: DEBIT clearing:rafiki / CREDIT liability:<user>:available."""
        data = payload.data
        accounts = await self._resolve_accounts(data)
        amount = self._amount(data, "receivedAmount", "incomingAmount")
        if amount <= 0:
            logger.info("Incoming payment with zero amount; nothing to credit.")
            return
        available = accounts["available"]
        clearing = await self._clearing(available)
        await self.ledger.transfer(
            from_account_id=clearing.id,
            to_account_id=available.id,
            amount=amount,
            reference=f"incoming:{data.get('id', '')}",
            description="Incoming payment received",
            enforce_source_non_negative=False,
        )

    async def _on_outgoing_created(self, payload: RafikiWebhookPayload) -> None:
        """Fund the outgoing payment's liquidity in Rafiki (keyed by the event id)."""
        if self.rafiki is None:
            raise WebhookProcessingError("Rafiki client required to fund outgoing payment")
        success = await self.rafiki.deposit_event_liquidity(
            event_id=payload.id, idempotency_key=f"deposit:{payload.id}"
        )
        if not success:
            raise WebhookProcessingError(f"Liquidity deposit failed for event {payload.id}")

    async def _on_outgoing_completed(self, payload: RafikiWebhookPayload) -> None:
        """Settle a sent payment: DEBIT reserved / CREDIT clearing:rafiki."""
        data = payload.data
        accounts = await self._resolve_accounts(data)
        reserved = accounts["reserved"]
        amount = self._amount(data, "debitAmount", "sentAmount")
        clearing = await self._clearing(reserved)
        await self.ledger.transfer(
            from_account_id=reserved.id,
            to_account_id=clearing.id,
            amount=amount,
            reference=f"outgoing-settle:{data.get('id', '')}",
            description="Outgoing payment settled",
            enforce_source_non_negative=True,
        )

    async def _on_outgoing_failed(self, payload: RafikiWebhookPayload) -> None:
        """Release a hold on failure: DEBIT reserved / CREDIT available."""
        data = payload.data
        accounts = await self._resolve_accounts(data)
        amount = self._amount(data, "debitAmount", "sentAmount")
        await self.ledger.transfer(
            from_account_id=accounts["reserved"].id,
            to_account_id=accounts["available"].id,
            amount=amount,
            reference=f"outgoing-release:{data.get('id', '')}",
            description="Outgoing payment failed; hold released",
            enforce_source_non_negative=True,
        )

    # -- Helpers -----------------------------------------------------------

    async def _clearing(self, like_account: LedgerAccount) -> LedgerAccount:
        return await self.ledger.get_or_create_system_account(
            name=CLEARING_ACCOUNT_NAME,
            asset_code=like_account.asset_code,
            asset_scale=like_account.asset_scale,
        )

    async def _resolve_accounts(self, data: dict) -> dict[str, LedgerAccount]:
        """Map a webhook's ``walletAddressId`` to the owner's ledger accounts."""
        rafiki_wa_id = data.get("walletAddressId")
        if not rafiki_wa_id:
            raise WebhookProcessingError("Webhook data missing walletAddressId")

        wallet = (
            await self.session.execute(
                select(WalletAddress).where(
                    WalletAddress.rafiki_wallet_address_id == str(rafiki_wa_id)
                )
            )
        ).scalar_one_or_none()
        if wallet is None:
            raise WebhookProcessingError(f"No local wallet for Rafiki id {rafiki_wa_id}")

        user = await self.session.get(User, wallet.user_id)
        if user is None:
            raise WebhookProcessingError(f"Wallet {wallet.id} has no owning user")

        return await self.ledger.ensure_user_accounts(
            user_id=user.id,
            username=user.username,
            asset_code=wallet.asset_code,
            asset_scale=int(wallet.asset_scale),
        )

    @staticmethod
    def _amount(data: dict, *keys: str) -> int:
        """Extract an integer minor-unit amount from Rafiki's ``{value, …}`` objects."""
        for key in keys:
            node = data.get(key)
            if isinstance(node, dict) and "value" in node:
                return int(node["value"])
            if isinstance(node, (int, str)):
                return int(node)
        raise WebhookProcessingError(f"Webhook data missing amount (tried {keys})")
