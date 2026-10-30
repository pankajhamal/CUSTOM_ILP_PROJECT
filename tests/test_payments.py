"""Integration tests for POST /api/v1/payments/send (fake Rafiki)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.security import generate_signature_header
from app.models.ledger import LedgerAccount
from app.models.wallet import WalletAddress


async def _setup_sender(client, sessionmaker, username: str, credit: int) -> str:
    """Register a user with a Rafiki-synced wallet and credit them. Returns wallet id."""
    r = await client.post(
        "/api/v1/users",
        json={"username": username, "email": f"{username}@x.com", "password": "pw-123456"},
    )
    uid = uuid.UUID(r.json()["id"])
    wallet_id = None
    async with sessionmaker() as s:
        w = WalletAddress(
            user_id=uid,
            wallet_address=f"https://x/{username}",
            rafiki_wallet_address_id=f"wa-{username}",
            asset_code="USD",
            asset_scale="2",
        )
        s.add(w)
        await s.commit()
        await s.refresh(w)
        wallet_id = str(w.id)

    if credit:
        payload = {
            "id": f"evt-credit-{username}",
            "type": "incoming_payment.completed",
            "data": {
                "id": f"inc-{username}",
                "walletAddressId": f"wa-{username}",
                "receivedAmount": {"value": str(credit), "assetCode": "USD", "assetScale": 2},
            },
        }
        header = {
            "rafiki-signature": generate_signature_header(
                payload, settings.RAFIKI_SIGNATURE_SECRET
            )
        }
        rr = await client.post("/webhooks/rafiki", json=payload, headers=header)
        assert rr.status_code == 200
    return wallet_id


async def _balance(sessionmaker, name: str) -> int | None:
    async with sessionmaker() as s:
        acct = (
            await s.execute(select(LedgerAccount).where(LedgerAccount.name == name))
        ).scalar_one_or_none()
        return acct.balance if acct else None


async def test_send_places_hold_and_creates_payment(client, sessionmaker, fake_rafiki):
    wallet_id = await _setup_sender(client, sessionmaker, "hana", credit=10000)

    r = await client.post(
        "/api/v1/payments/send",
        json={
            "sender_wallet_address_id": wallet_id,
            "receiver": "https://other.example/pay/zoe",
            "amount": 2500,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["payment_id"] == "payment-1"
    assert body["status"] == "FUNDING"
    assert body["quote"]["debit_amount"] == 2500

    assert await _balance(sessionmaker, "liability:hana:available") == 7500
    assert await _balance(sessionmaker, "liability:hana:reserved") == 2500

    # Rafiki sequence: receiver -> quote -> outgoing payment.
    names = [c[0] for c in fake_rafiki.calls]
    assert names == ["create_receiver", "create_quote", "create_outgoing_payment"]
    # Quote was made against the receiver's incoming-payment URL.
    assert fake_rafiki.calls[1][1]["receiver"].endswith("/incoming-payments/recv-1")


async def test_send_normalizes_payment_pointer(client, sessionmaker, fake_rafiki):
    wallet_id = await _setup_sender(client, sessionmaker, "iris", credit=1000)
    r = await client.post(
        "/api/v1/payments/send",
        json={
            "sender_wallet_address_id": wallet_id,
            "receiver": "$other.example/pay/zoe",
            "amount": 100,
        },
    )
    assert r.status_code == 201
    assert fake_rafiki.calls[0][1]["wallet_address_url"] == "https://other.example/pay/zoe"


async def test_send_insufficient_funds_402(client, sessionmaker, fake_rafiki):
    wallet_id = await _setup_sender(client, sessionmaker, "jon", credit=100)
    r = await client.post(
        "/api/v1/payments/send",
        json={
            "sender_wallet_address_id": wallet_id,
            "receiver": "https://other.example/pay/zoe",
            "amount": 5000,
        },
    )
    assert r.status_code == 402
    # No Rafiki resources were created and no hold was placed.
    assert fake_rafiki.calls == []
    assert await _balance(sessionmaker, "liability:jon:reserved") == 0


async def test_send_unknown_wallet_404(client):
    r = await client.post(
        "/api/v1/payments/send",
        json={
            "sender_wallet_address_id": str(uuid.uuid4()),
            "receiver": "https://other.example/pay/zoe",
            "amount": 100,
        },
    )
    assert r.status_code == 404


async def test_send_invalid_amount_422(client, sessionmaker):
    wallet_id = await _setup_sender(client, sessionmaker, "kay", credit=1000)
    r = await client.post(
        "/api/v1/payments/send",
        json={
            "sender_wallet_address_id": wallet_id,
            "receiver": "https://other.example/pay/zoe",
            "amount": 0,
        },
    )
    assert r.status_code == 422
