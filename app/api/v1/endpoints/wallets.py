"""Wallet-address provisioning.

Phase 1 stub: router exists and is wired in. Later phase: create the wallet
locally and sync it with Rafiki (``createWalletAddress``), persisting the
returned ``walletAddressId``.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
