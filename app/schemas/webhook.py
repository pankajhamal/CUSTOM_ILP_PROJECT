"""Rafiki webhook payload schemas.

Rafiki delivers every webhook as ``{"id", "type", "data"}``. ``data`` is an
open-ended object whose shape depends on ``type``; the webhook service interprets
the fields it needs per event type. Event type values mirror Rafiki's ``EventType``.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class WebhookEventType(str, enum.Enum):
    """Rafiki webhook event types this ASE knows how to react to."""

    INCOMING_PAYMENT_CREATED = "incoming_payment.created"
    INCOMING_PAYMENT_COMPLETED = "incoming_payment.completed"
    INCOMING_PAYMENT_EXPIRED = "incoming_payment.expired"
    OUTGOING_PAYMENT_CREATED = "outgoing_payment.created"
    OUTGOING_PAYMENT_COMPLETED = "outgoing_payment.completed"
    OUTGOING_PAYMENT_FAILED = "outgoing_payment.failed"
    WALLET_ADDRESS_NOT_FOUND = "wallet_address.not_found"


class RafikiWebhookPayload(BaseModel):
    """The envelope Rafiki POSTs to ``/webhooks/rafiki``."""

    id: str = Field(description="Unique Rafiki event id — used as the idempotency key.")
    type: str = Field(description="Event type, e.g. 'incoming_payment.completed'.")
    data: dict = Field(default_factory=dict, description="Event-specific payload.")


class WebhookAck(BaseModel):
    """Response body acknowledging webhook receipt."""

    received: bool = True
    event_id: str
    duplicate: bool = False
    handled: bool = True
