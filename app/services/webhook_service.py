"""Webhook event dispatcher.

Phase 1 stub. Later phase: implement ``WebhookService`` — record events for
idempotency, then dispatch by type (``incoming_payment.completed``,
``outgoing_payment.created`` / ``.completed`` / ``.failed``) to the matching
ledger postings and Rafiki calls.
"""

from __future__ import annotations
