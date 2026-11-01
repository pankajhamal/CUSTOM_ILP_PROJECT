"""Tests for the dev-only faucet endpoint."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import settings


async def _register(client, username: str) -> str:
    r = await client.post(
        "/api/v1/users",
        json={"username": username, "email": f"{username}@x.com", "password": "pw-123456"},
    )
    assert r.status_code == 201
    return r.json()["id"]


async def test_faucet_credits_available_balance(client):
    uid = await _register(client, "lucky")
    r = await client.post("/api/v1/dev/faucet", json={"user_id": uid, "amount": 10000})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["credited"] == 10000
    assert body["available_balance"] == 10000

    # Second credit accumulates.
    r2 = await client.post("/api/v1/dev/faucet", json={"user_id": uid, "amount": 500})
    assert r2.json()["available_balance"] == 10500

    # Reflected in the user payload the dashboard reads.
    u = (await client.get(f"/api/v1/users/{uid}")).json()
    available = next(a for a in u["ledger_accounts"] if a["name"].endswith(":available"))
    assert available["balance"] == 10500


async def test_faucet_rejects_bad_input(client):
    uid = await _register(client, "larry")
    assert (
        await client.post("/api/v1/dev/faucet", json={"user_id": uid, "amount": 0})
    ).status_code == 422
    assert (
        await client.post("/api/v1/dev/faucet", json={"user_id": uid, "amount": -5})
    ).status_code == 422
    assert (
        await client.post(
            "/api/v1/dev/faucet", json={"user_id": str(uuid.uuid4()), "amount": 100}
        )
    ).status_code == 404


async def test_faucet_forbidden_outside_development(client, monkeypatch):
    uid = await _register(client, "prodguy")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    r = await client.post("/api/v1/dev/faucet", json={"user_id": uid, "amount": 100})
    assert r.status_code == 403
