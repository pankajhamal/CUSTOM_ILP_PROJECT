"""Unit tests for HMAC webhook signature verification and password hashing."""

from __future__ import annotations

import time

from app.core.security import (
    generate_signature_header,
    hash_password,
    parse_signature_header,
    verify_password,
    verify_webhook_signature,
)

SECRET = "shared-secret"
PAYLOAD = {"id": "evt_1", "type": "incoming_payment.completed", "data": {"amount": 1000}}


def test_sign_and_verify_roundtrip():
    header = generate_signature_header(PAYLOAD, SECRET)
    assert verify_webhook_signature(PAYLOAD, header, SECRET)


def test_key_order_does_not_matter():
    """Canonicalization means logically-equal payloads verify regardless of order."""
    header = generate_signature_header(PAYLOAD, SECRET)
    reordered = {"data": {"amount": 1000}, "type": PAYLOAD["type"], "id": "evt_1"}
    assert verify_webhook_signature(reordered, header, SECRET)


def test_tampered_payload_fails():
    header = generate_signature_header(PAYLOAD, SECRET)
    tampered = {**PAYLOAD, "data": {"amount": 999999}}
    assert not verify_webhook_signature(tampered, header, SECRET)


def test_wrong_secret_fails():
    header = generate_signature_header(PAYLOAD, SECRET)
    assert not verify_webhook_signature(PAYLOAD, header, "not-the-secret")


def test_expired_timestamp_fails():
    old_ts = int((time.time() - 10_000) * 1000)
    header = generate_signature_header(PAYLOAD, SECRET, timestamp=old_ts)
    assert not verify_webhook_signature(PAYLOAD, header, SECRET, tolerance_seconds=300)


def test_future_timestamp_within_tolerance_passes():
    near_future = int((time.time() + 60) * 1000)
    header = generate_signature_header(PAYLOAD, SECRET, timestamp=near_future)
    assert verify_webhook_signature(PAYLOAD, header, SECRET, tolerance_seconds=300)


def test_missing_or_malformed_header():
    assert not verify_webhook_signature(PAYLOAD, None, SECRET)
    assert not verify_webhook_signature(PAYLOAD, "garbage", SECRET)
    assert parse_signature_header("garbage") is None
    assert parse_signature_header("t=abc, v1=xyz") is None  # non-numeric timestamp


def test_parse_signature_header():
    parsed = parse_signature_header("t=1700000000000, v1=deadbeef")
    assert parsed is not None
    assert parsed.timestamp == 1700000000000
    assert parsed.digests["1"] == "deadbeef"


def test_unknown_version_fails():
    header = generate_signature_header(PAYLOAD, SECRET, version="1")
    assert not verify_webhook_signature(PAYLOAD, header, SECRET, version="2")


def test_password_hashing():
    hashed = hash_password("sup3r-secret-pw")
    assert hashed != "sup3r-secret-pw"
    assert verify_password("sup3r-secret-pw", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("x", "not-a-valid-hash")
