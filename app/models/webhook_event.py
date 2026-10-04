"""Idempotency log for inbound Rafiki webhook events.

Phase 1 stub. Later phase: define the ``WebhookEvent`` ORM model keyed by a
unique ``rafiki_event_id`` (the idempotency key), with event type, status,
stored payload, and processed-at timestamp. Register it in
``app.models.__init__``.
"""

from __future__ import annotations
