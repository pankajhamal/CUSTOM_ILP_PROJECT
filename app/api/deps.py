"""Shared FastAPI dependencies: DB session, Rafiki client, webhook auth."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import verify_webhook_signature
from app.schemas.webhook import RafikiWebhookPayload
from app.services.rafiki_client import RafikiClient

# Rafiki delivers the webhook HMAC in this header; version prefix is "v1".
WEBHOOK_SIGNATURE_HEADER = "rafiki-signature"
WEBHOOK_SIGNATURE_VERSION = "1"
WEBHOOK_TOLERANCE_SECONDS = 300

# Async DB session, one per request.
DBSession = Annotated[AsyncSession, Depends(get_session)]


async def get_rafiki_client() -> AsyncIterator[RafikiClient]:
    """Provide a Rafiki Admin API client for the request."""
    client = RafikiClient()
    try:
        yield client
    finally:
        await client.aclose()


RafikiDep = Annotated[RafikiClient, Depends(get_rafiki_client)]


async def verify_rafiki_webhook(
    request: Request,
    rafiki_signature: Annotated[str | None, Header(alias=WEBHOOK_SIGNATURE_HEADER)] = None,
) -> RafikiWebhookPayload:
    """Authenticate an inbound webhook via HMAC and return its parsed payload.

    The signature is verified against the JSON-canonicalized body (matching how
    Rafiki signs), and the timestamp must be within the tolerance window.
    """
    raw = await request.body()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON body"
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook body must be an object"
        )

    valid = verify_webhook_signature(
        data,
        rafiki_signature,
        settings.RAFIKI_SIGNATURE_SECRET,
        version=WEBHOOK_SIGNATURE_VERSION,
        tolerance_seconds=WEBHOOK_TOLERANCE_SECONDS,
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature"
        )

    try:
        return RafikiWebhookPayload(**data)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid webhook payload"
        ) from exc


VerifiedWebhook = Annotated[RafikiWebhookPayload, Depends(verify_rafiki_webhook)]
