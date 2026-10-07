"""Shared FastAPI dependencies.

Provides the DB session and the Rafiki Admin API client. (The HMAC
webhook-verification dependency arrives with the webhook phase; the HMAC helpers
already live in ``app.core.security``.)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.rafiki_client import RafikiClient

# Async DB session, one per request.
DBSession = Annotated[AsyncSession, Depends(get_session)]


async def get_rafiki_client() -> AsyncIterator[RafikiClient]:
    """Provide a Rafiki Admin API client for the request."""
    client = RafikiClient()
    try:
        yield client
    finally:
        await client.aclose()


RafikiDep = Annotated[RafikiClient, Depends(get_rafiki_client)]
