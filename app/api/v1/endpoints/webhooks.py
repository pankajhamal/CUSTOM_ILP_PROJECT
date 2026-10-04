"""HMAC-protected Rafiki webhook receiver.

Phase 1 stub: router exists and is wired in. Later phase: verify the HMAC
signature, enforce idempotency, and dispatch events to the ledger.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
