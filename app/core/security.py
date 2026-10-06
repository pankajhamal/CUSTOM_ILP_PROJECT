"""Webhook signature security and password hashing.

Rafiki signs each webhook with an HMAC-SHA256 over ``"{timestamp}.{body}"`` where
``body`` is the **JSON-canonicalized** payload (RFC 8785 / JCS, as produced by the
``canonicalize`` npm package Rafiki uses). The signature is delivered in a header
shaped like Stripe's::

    x-signature: t=1700000000000, v1=9f86d08...e7f"""  """

This module recomputes that digest and compares it in constant time, and also
enforces a timestamp tolerance window to limit replay attacks.

Note on canonicalization: we approximate JCS with sorted keys and compact
separators, which is byte-identical for the string/integer payloads Rafiki emits.
If you adopt floats or exotic unicode in payloads, swap in a full RFC 8785 encoder.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass

import bcrypt

# ---------------------------------------------------------------------------
# JSON canonicalization
# ---------------------------------------------------------------------------


def canonicalize(payload: dict | list) -> str:
    """Return a canonical JSON string (sorted keys, no superfluous whitespace)."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# HMAC signature generation / parsing
# ---------------------------------------------------------------------------


def compute_digest(payload: dict | list, secret: str, timestamp: int) -> str:
    """Compute the hex HMAC-SHA256 digest over ``"{timestamp}.{canonical_body}"``."""
    signed_payload = f"{timestamp}.{canonicalize(payload)}"
    return hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_signature_header(
    payload: dict | list,
    secret: str,
    *,
    timestamp: int | None = None,
    version: str = "1",
) -> str:
    """Build a ``t=…, v{version}=…`` signature header. Used by tests & simulators."""
    ts = timestamp if timestamp is not None else int(time.time() * 1000)
    digest = compute_digest(payload, secret, ts)
    return f"t={ts}, v{version}={digest}"


@dataclass(frozen=True)
class ParsedSignature:
    """A parsed signature header: the timestamp and version→digest mapping."""

    timestamp: int
    digests: dict[str, str]


def parse_signature_header(header: str) -> ParsedSignature | None:
    """Parse ``t=…, v1=…`` into a :class:`ParsedSignature`, or ``None`` if malformed."""
    timestamp: int | None = None
    digests: dict[str, str] = {}

    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        key, value = key.strip(), value.strip()
        if not value:
            continue
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return None
        elif key.startswith("v"):
            digests[key[1:]] = value

    if timestamp is None or not digests:
        return None
    return ParsedSignature(timestamp=timestamp, digests=digests)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_webhook_signature(
    payload: dict | list,
    signature_header: str | None,
    secret: str,
    *,
    version: str = "1",
    tolerance_seconds: int = 300,
    now: float | None = None,
) -> bool:
    """Verify a Rafiki webhook signature.

    Returns ``True`` only if the digest matches **and** the timestamp is within
    ``tolerance_seconds`` of now. Comparison is constant-time.
    """
    if not signature_header:
        return False

    parsed = parse_signature_header(signature_header)
    if parsed is None:
        return False

    expected = parsed.digests.get(version)
    if expected is None:
        return False

    # Replay window. Rafiki timestamps are epoch milliseconds.
    current_ms = (now if now is not None else time.time()) * 1000
    if abs(current_ms - parsed.timestamp) > tolerance_seconds * 1000:
        return False

    actual = compute_digest(payload, secret, parsed.timestamp)
    return hmac.compare_digest(actual, expected)


# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt; returns a UTF-8 encoded hash."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash in constant time."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
