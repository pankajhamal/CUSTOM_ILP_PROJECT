"""Integration tests for the /webhooks/rafiki receiver and /rates endpoint."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.security import generate_signature_header
from app.models.ledger import LedgerAccount
from app.models.wallet import WalletAddress

SECRET = settings.RAFIKI_SIGNATURE_SECRET


async def _register_with_wallet(client, sessionmaker, username: str, rafiki_wa_id: str):
    r = await client.post(
        "/api/v1/users",
        json={"username": username, "email": f"{username}@x.com", "password": "pw-123456"},
    )
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["id"])
    async with sessionmaker() as s:
        s.add(
            WalletAddress(
                user_id=uid,
                wallet_address=f"https://x/{username}",
                rafiki_wallet_address_id=rafiki_wa_id,
                asset_code="USD",
                asset_scale="2",
            )
        )
        await s.commit()
    return uid


async def _post_signed(client, payload, secret=SECRET):
    header = {"rafiki-signature": generate_signature_header(payload, secret)}
    return await client.post("/webhooks/rafiki", json=payload, headers=header)


def _incoming(event_id: str, wa_id: str, amount: int) -> dict:
    return {
        "id": event_id,
        "type": "incoming_payment.completed",
        "data": {
            "id": f"pay_{event_id}",
            "walletAddressId": wa_id,
            "receivedAmount": {"value": str(amount), "assetCode": "USD", "assetScale": 2},
        },
    }


async def _balance(sessionmaker, name: str) -> int | None:
    async with sessionmaker() as s:
        acct = (
            await s.execute(select(LedgerAccount).where(LedgerAccount.name == name))
        ).scalar_one_or_none()
        return acct.balance if acct else None


async def test_incoming_payment_credits_user(client, sessionmaker):
    await _register_with_wallet(client, sessionmaker, "bob", "wa-bob")
    r = await _post_signed(client, _incoming("evt-1", "wa-bob", 1500))
    assert r.status_code == 200
    body = r.json()
    assert body["duplicate"] is False and body["handled"] is True
    assert await _balance(sessionmaker, "liability:bob:available") == 1500


async def test_duplicate_event_not_double_credited(client, sessionmaker):
    await _register_with_wallet(client, sessionmaker, "carl", "wa-carl")
    payload = _incoming("evt-dup", "wa-carl", 1000)
    r1 = await _post_signed(client, payload)
    r2 = await _post_signed(client, payload)
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["duplicate"] is False
    assert r2.json()["duplicate"] is True
    assert await _balance(sessionmaker, "liability:carl:available") == 1000


async def test_bad_signature_rejected(client, sessionmaker):
    await _register_with_wallet(client, sessionmaker, "dana", "wa-dana")
    payload = _incoming("evt-bad", "wa-dana", 1000)
    r = await client.post(
        "/webhooks/rafiki", json=payload, headers={"rafiki-signature": "t=1, v1=deadbeef"}
    )
    assert r.status_code == 401
    r2 = await client.post("/webhooks/rafiki", json=payload)  # missing header
    assert r2.status_code == 401
    assert await _balance(sessionmaker, "liability:dana:available") in (None, 0)


async def test_wrong_secret_rejected(client, sessionmaker):
    await _register_with_wallet(client, sessionmaker, "eddy", "wa-eddy")
    r = await _post_signed(client, _incoming("evt-ws", "wa-eddy", 1000), secret="wrong-secret")
    assert r.status_code == 401


async def test_unknown_event_type_acknowledged(client):
    payload = {"id": "evt-unk", "type": "asset.liquidity_low", "data": {}}
    r = await _post_signed(client, payload)
    assert r.status_code == 200
    assert r.json()["handled"] is False


async def test_unknown_wallet_rolls_back_and_500(client, sessionmaker):
    payload = _incoming("evt-nowallet", "wa-ghost", 1000)
    r = await _post_signed(client, payload)
    assert r.status_code == 500
    # Idempotency row rolled back -> a retry is processed as new (and fails again).
    r2 = await _post_signed(client, payload)
    assert r2.status_code == 500


async def test_outgoing_completed_settles_hold(client, sessionmaker, fake_rafiki):
    await _register_with_wallet(client, sessionmaker, "fay", "wa-fay")
    await _post_signed(client, _incoming("evt-f1", "wa-fay", 2000))

    # Place the hold via the ledger directly (simulating a prior send).
    from app.services.ledger_service import LedgerService

    async with sessionmaker() as s:
        ledger = LedgerService(s)
        avail = (
            await s.execute(select(LedgerAccount).where(LedgerAccount.name == "liability:fay:available"))
        ).scalar_one()
        res = (
            await s.execute(select(LedgerAccount).where(LedgerAccount.name == "liability:fay:reserved"))
        ).scalar_one()
        await ledger.transfer(from_account_id=avail.id, to_account_id=res.id, amount=700)
        await s.commit()

    payload = {
        "id": "evt-f2",
        "type": "outgoing_payment.completed",
        "data": {
            "id": "outpay-1",
            "walletAddressId": "wa-fay",
            "debitAmount": {"value": "700", "assetCode": "USD", "assetScale": 2},
        },
    }
    r = await _post_signed(client, payload)
    assert r.status_code == 200 and r.json()["handled"] is True
    assert await _balance(sessionmaker, "liability:fay:available") == 1300
    assert await _balance(sessionmaker, "liability:fay:reserved") == 0
    # clearing: +2000 incoming, -700 settle
    assert await _balance(sessionmaker, "clearing:rafiki") == 1300


async def test_outgoing_failed_releases_hold(client, sessionmaker):
    await _register_with_wallet(client, sessionmaker, "gus", "wa-gus")
    await _post_signed(client, _incoming("evt-g1", "wa-gus", 1000))

    from app.services.ledger_service import LedgerService

    async with sessionmaker() as s:
        ledger = LedgerService(s)
        avail = (
            await s.execute(select(LedgerAccount).where(LedgerAccount.name == "liability:gus:available"))
        ).scalar_one()
        res = (
            await s.execute(select(LedgerAccount).where(LedgerAccount.name == "liability:gus:reserved"))
        ).scalar_one()
        await ledger.transfer(from_account_id=avail.id, to_account_id=res.id, amount=400)
        await s.commit()

    payload = {
        "id": "evt-g2",
        "type": "outgoing_payment.failed",
        "data": {
            "id": "outpay-2",
            "walletAddressId": "wa-gus",
            "debitAmount": {"value": "400", "assetCode": "USD", "assetScale": 2},
        },
    }
    r = await _post_signed(client, payload)
    assert r.status_code == 200
    assert await _balance(sessionmaker, "liability:gus:available") == 1000
    assert await _balance(sessionmaker, "liability:gus:reserved") == 0


async def test_outgoing_created_deposits_liquidity(client, fake_rafiki):
    payload = {"id": "evt-liq", "type": "outgoing_payment.created", "data": {"id": "outpay-3"}}
    r = await _post_signed(client, payload)
    assert r.status_code == 200 and r.json()["handled"] is True
    calls = [c for c in fake_rafiki.calls if c[0] == "deposit_event_liquidity"]
    assert len(calls) == 1
    assert calls[0][1]["event_id"] == "evt-liq"


async def test_outgoing_created_deposit_failure_is_5xx(client, fake_rafiki):
    fake_rafiki.deposit_success = False
    payload = {"id": "evt-liq-fail", "type": "outgoing_payment.created", "data": {"id": "op"}}
    r = await _post_signed(client, payload)
    assert r.status_code == 500


async def test_rates_endpoint(client):
    r = await client.get("/rates", params={"base": "usd"})
    assert r.status_code == 200
    body = r.json()
    assert body["base"] == "USD"
    assert isinstance(body["rates"], dict)
    # default base falls back to the configured asset code
    r2 = await client.get("/rates")
    assert r2.status_code == 200
