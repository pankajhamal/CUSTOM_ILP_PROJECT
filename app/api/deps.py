"""Shared FastAPI dependencies.

Phase 1 ships the DB session dependency. Later phases add the Rafiki Admin API
client and the HMAC webhook-verification dependency (the HMAC helpers already
live in ``app.core.security``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session

# Async DB session, one per request.
DBSession = Annotated[AsyncSession, Depends(get_session)]
