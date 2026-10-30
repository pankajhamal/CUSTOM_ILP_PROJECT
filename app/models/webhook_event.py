"""Idempotency log for inbound Rafiki webhook events.

Rafiki retries webhooks until it gets a 2xx, so the same ``rafiki_event_id`` can
arrive multiple times. A unique constraint lets us reject duplicates atomically
(insert-or-conflict) so we never double-post to the ledger for one real event.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import JSONB, Base, TimestampMixin, uuid_pk


class WebhookStatus(str, enum.Enum):
    """Processing lifecycle of a received webhook event."""

    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


_status_enum = Enum(
    WebhookStatus,
    native_enum=False,
    length=16,
    name="webhook_status",
    values_callable=lambda e: [m.value for m in e],
)


class WebhookEvent(Base, TimestampMixin):
    """A record of one Rafiki webhook delivery, keyed by Rafiki's event id."""

    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = uuid_pk()

    # Rafiki's unique event identifier — the idempotency key.
    rafiki_event_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[WebhookStatus] = mapped_column(
        _status_enum, default=WebhookStatus.RECEIVED, nullable=False
    )

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error: Mapped[str | None] = mapped_column(String(1024))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<WebhookEvent {self.event_type} {self.rafiki_event_id} {self.status.value}>"
