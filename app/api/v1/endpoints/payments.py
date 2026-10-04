"""Outgoing payment initiation.

Phase 1 stub: router exists and is wired in. Later phase: reserve hold
(available -> reserved), create a Rafiki quote and outgoing payment.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
