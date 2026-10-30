#!/usr/bin/env python
"""Fire an HMAC-signed mock Rafiki webhook at the ASE — no real Rafiki needed.

Examples
--------
    # credit a user 10.00 USD (amount is minor units)
    poetry run python scripts/simulate_webhook.py \
        --event incoming_payment.completed \
        --wallet-address-id <rafiki-wallet-address-id> \
        --amount 1000

    # settle a previously held outgoing payment
    poetry run python scripts/simulate_webhook.py \
        --event outgoing_payment.completed \
        --wallet-address-id <id> --amount 500 --payment-id pay_123

The signature uses the same scheme Rafiki uses (HMAC-SHA256 over
``{ts}.{canonical_json}``, header ``rafiki-signature``), so the ASE's verification
accepts it. Point ``--wallet-address-id`` at a wallet whose
``rafiki_wallet_address_id`` exists in your DB so the handler can resolve accounts.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import httpx

# Allow running as `python scripts/simulate_webhook.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.security import canonicalize, generate_signature_header  # noqa: E402

EVENTS = (
    "incoming_payment.completed",
    "outgoing_payment.created",
    "outgoing_payment.completed",
    "outgoing_payment.failed",
)


def _amount(value: int) -> dict:
    return {
        "value": str(value),
        "assetCode": settings.RAFIKI_ASSET_CODE or "USD",
        "assetScale": settings.RAFIKI_ASSET_SCALE,
    }


def build_payload(args: argparse.Namespace) -> dict:
    """Construct a Rafiki-shaped ``{id, type, data}`` envelope for the event."""
    event_id = args.event_id or f"evt_{uuid.uuid4().hex[:16]}"
    payment_id = args.payment_id or f"pay_{uuid.uuid4().hex[:16]}"
    wa = args.wallet_address_id or "REPLACE_WITH_RAFIKI_WALLET_ADDRESS_ID"

    common = {"id": payment_id, "walletAddressId": wa}
    data_by_event = {
        "incoming_payment.completed": {
            **common,
            "completed": True,
            "receivedAmount": _amount(args.amount),
        },
        "outgoing_payment.created": {
            **common,
            "state": "FUNDING",
            "debitAmount": _amount(args.amount),
        },
        "outgoing_payment.completed": {
            **common,
            "state": "COMPLETED",
            "debitAmount": _amount(args.amount),
            "sentAmount": _amount(args.amount),
        },
        "outgoing_payment.failed": {
            **common,
            "state": "FAILED",
            "debitAmount": _amount(args.amount),
        },
    }
    return {"id": event_id, "type": args.event, "data": data_by_event[args.event]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fire a signed mock Rafiki webhook.")
    parser.add_argument("--event", required=True, choices=EVENTS)
    parser.add_argument(
        "--url",
        default="http://localhost:8000/webhooks/rafiki",
        help="Target webhook URL (default: local ASE, root-mounted).",
    )
    parser.add_argument("--wallet-address-id", help="Rafiki wallet address id to target.")
    parser.add_argument("--amount", type=int, default=1000, help="Amount in minor units.")
    parser.add_argument("--payment-id", help="Override the payment id in data.")
    parser.add_argument("--event-id", help="Override the webhook event id (idempotency key).")
    parser.add_argument(
        "--secret",
        default=settings.RAFIKI_SIGNATURE_SECRET,
        help="HMAC secret (defaults to RAFIKI_SIGNATURE_SECRET).",
    )
    args = parser.parse_args()

    payload = build_payload(args)
    signature = generate_signature_header(payload, args.secret)
    headers = {"content-type": "application/json", "rafiki-signature": signature}

    print(f"POST {args.url}")
    print(f"  event     : {payload['type']}")
    print(f"  event id  : {payload['id']}")
    print(f"  signature : {signature[:48]}...")

    # Send the canonical JSON body the signature was computed over.
    body = canonicalize(payload).encode("utf-8")
    response = httpx.post(args.url, content=body, headers=headers, timeout=15.0)

    print(f"\n<- {response.status_code}")
    print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
