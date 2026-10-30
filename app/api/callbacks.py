"""Root-mounted Rafiki callback endpoints: webhooks + exchange rates.

Rafiki is configured to call these at the ASE root (not under ``/api/v1``):
  * ``POST /webhooks/rafiki`` — HMAC-signed payment lifecycle events
  * ``GET  /rates``           — exchange-rate provider used during quoting
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DBSession, RafikiDep, VerifiedWebhook
from app.core.config import settings
from app.schemas.webhook import WebhookAck
from app.services.ledger_service import LedgerError
from app.services.webhook_service import WebhookProcessingError, WebhookService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rafiki-callbacks"])

# Minimal static rates for quoting. Values are "units of <code> per 1 unit of base".
# Same-currency quotes don't need a rate; extend this table for real FX.
_STATIC_RATES: dict[str, dict[str, float]] = {
    "USD": {"EUR": 0.92, "GBP": 0.79, "NPR": 133.0},
    "EUR": {"USD": 1.09, "GBP": 0.86, "NPR": 145.0},
    "NPR": {"USD": 0.0075, "EUR": 0.0069},
}


@router.post(
    "/webhooks/rafiki",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive a signed Rafiki webhook",
)
async def receive_rafiki_webhook(
    payload: VerifiedWebhook,
    session: DBSession,
    rafiki: RafikiDep,
) -> WebhookAck:
    """Verify (via the dependency), process idempotently, and acknowledge.

    Returns 200 for freshly handled and duplicate events. Any processing error
    rolls back the request — including the idempotency row — and returns 5xx so
    Rafiki retries.
    """
    service = WebhookService(session, rafiki)
    try:
        ack = await service.process(payload)
        await session.commit()
        return ack
    except (WebhookProcessingError, LedgerError) as exc:
        await session.rollback()
        logger.exception("Failed to process webhook %s (%s)", payload.id, payload.type)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {exc}",
        ) from exc


@router.get("/rates", summary="Exchange-rate provider for Rafiki quoting")
async def get_rates(
    base: str = Query(default=None, min_length=3, max_length=3),
) -> dict:
    """Return ``{base, rates}`` where rates maps currency code -> rate vs. base."""
    code = (base or settings.RAFIKI_ASSET_CODE or "USD").upper()
    return {"base": code, "rates": _STATIC_RATES.get(code, {})}
