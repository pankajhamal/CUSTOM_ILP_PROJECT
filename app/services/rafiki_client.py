"""Async GraphQL client for the Rafiki Admin API.

Request signing matches what the Rafiki backend verifies (mirrored from the
testnet wallet backend's ``config/rafiki.ts``):

    timestamp = now in milliseconds
    payload   = f"{timestamp}.{canonicalize({'variables': vars, 'query': query})}"
    digest    = HMAC_SHA256(ADMIN_API_SECRET, payload).hexdigest()
    header    = "signature: t=<timestamp>, v<version>=<digest>"
    header    = "tenant-id: <OPERATOR_TENANT_ID>"

``operationName`` is omitted from both the request body and the signed object, so
the two stay consistent (Rafiki canonicalizes whatever we actually send).

Mutations here use the exact field shapes from the live Rafiki schema:
  * ``createAsset(input: { code, scale })``
  * ``createWalletAddress(input: { assetId, address, publicName })``
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import logging

from app.core.config import settings
from app.core.security import compute_digest


logger = logging.getLogger(__name__)


class RafikiClientError(Exception):
    """Transport or protocol error talking to Rafiki."""


class RafikiGraphQLError(RafikiClientError):
    """Rafiki returned a GraphQL ``errors`` array."""

    def __init__(self, errors: list[dict]) -> None:
        self.errors = errors
        messages = "; ".join(e.get("message", str(e)) for e in errors)
        super().__init__(f"Rafiki GraphQL error(s): {messages}")


# --- GraphQL documents -----------------------------------------------------

_CREATE_ASSET = """
mutation CreateAsset($input: CreateAssetInput!) {
  createAsset(input: $input) {
    asset { id code scale }
  }
}
"""

_CREATE_WALLET_ADDRESS = """
mutation CreateWalletAddress($input: CreateWalletAddressInput!) {
  createWalletAddress(input: $input) {
    walletAddress { id address publicName }
  }
}
"""


class RafikiClient:
    """Thin async GraphQL client. Reuses an injected httpx client if provided."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._external_client = client
        self._url = settings.RAFIKI_GRAPHQL_URL
        self._timeout = 30.0

    # -- Transport ---------------------------------------------------------

    def _signed_headers(self, query: str, variables: dict) -> dict[str, str]:
        """Build headers, signing the request if an Admin API secret is set."""
        headers = {"content-type": "application/json"}

        secret = settings.RAFIKI_API_SECRET

        if secret:
            timestamp = int(time.time() * 1000)

            # Sign the canonical GraphQL request.
            signed_obj = {
                "variables": variables or {},
                "query": query,
            }

            digest = compute_digest(signed_obj, secret, timestamp)
            version = settings.RAFIKI_GRAPHQL_SIGNATURE_VERSION

            headers["signature"] = f"t={timestamp}, v{version}={digest}"

        if settings.RAFIKI_TENANT_ID:
            headers["tenant-id"] = settings.RAFIKI_TENANT_ID

        return headers

    async def execute(
        self,
        query: str,
        variables: dict | None = None,
    ) -> dict[str, Any]:
        """Run a GraphQL operation and return its data object."""
        variables = variables or {}

        body = {
            "query": query,
            "variables": variables,
        }

        headers = self._signed_headers(query, variables)

        client = self._external_client
        owns_client = client is None

        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout)

        try:
            response = await client.post(
                self._url,
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

        except httpx.HTTPError as exc:
            raise RafikiClientError(
                f"HTTP error calling Rafiki: {exc}"
            ) from exc

        finally:
            if owns_client:
                await client.aclose()

        if payload.get("errors"):
            raise RafikiGraphQLError(payload["errors"])

        return payload.get("data") or {}

    async def aclose(self) -> None:
        """Close the injected HTTP client, if one was provided."""
        if self._external_client is not None:
            await self._external_client.aclose()

    # -- Mutations ---------------------------------------------------------

    async def create_asset(self, *, code: str, scale: int) -> dict[str, Any]:
        """Create an asset (currency); returns ``{id, code, scale}``."""
        data = await self.execute(_CREATE_ASSET, {"input": {"code": code, "scale": scale}})
        asset = (data.get("createAsset") or {}).get("asset")
        if not asset:
            raise RafikiClientError("createAsset returned no asset")
        return asset

    async def create_wallet_address(
        self,
        *,
        asset_id: str,
        address: str,
        public_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a wallet address; returns ``{id, address, publicName}``."""
        variables = {
            "input": {
                "assetId": asset_id,
                "address": address,
                "publicName": public_name,
            }
        }
        data = await self.execute(_CREATE_WALLET_ADDRESS, variables)
        logger.info("Response from rafiki :", data)
        wa = (data.get("createWalletAddress") or {}).get("walletAddress")
        if not wa:
            raise RafikiClientError("createWalletAddress returned no walletAddress")
        return wa
