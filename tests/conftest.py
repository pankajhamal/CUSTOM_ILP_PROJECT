"""Pytest fixtures: in-memory async SQLite DB, app client, fake Rafiki.

Environment is configured BEFORE importing anything from ``app`` so the cached
settings pick these values up (real env vars take precedence over ``.env``).

Why the event listeners: pysqlite (under aiosqlite) mismanages transaction BEGIN,
which breaks SAVEPOINT / ``begin_nested`` — exactly what the ledger and webhook
idempotency rely on. The documented workaround is to disable pysqlite's implicit
BEGIN and emit it ourselves.
"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["DEBUG"] = "false"
os.environ["OTEL_ENABLED"] = "false"
os.environ.setdefault("RAFIKI_SIGNATURE_SECRET", "test-webhook-secret")
os.environ.setdefault("RAFIKI_API_SECRET", "test-admin-secret")
os.environ.setdefault("RAFIKI_TENANT_ID", "test-tenant")
os.environ.setdefault("RAFIKI_ASSET_ID", "test-asset-id")
os.environ.setdefault("RAFIKI_ASSET_CODE", "USD")
os.environ.setdefault("RAFIKI_ASSET_SCALE", "2")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.deps import get_rafiki_client  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


class FakeRafikiClient:
    """Canned Rafiki Admin API responses for offline tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.deposit_success = True

    async def create_receiver(self, **kw):
        self.calls.append(("create_receiver", kw))
        return {
            "id": f"{kw['wallet_address_url']}/incoming-payments/recv-1",
            "walletAddressUrl": kw["wallet_address_url"],
        }

    async def create_quote(self, **kw):
        self.calls.append(("create_quote", kw))
        amt = {
            "value": str(kw["debit_amount"]),
            "assetCode": kw["asset_code"],
            "assetScale": kw["asset_scale"],
        }
        return {
            "id": "quote-1",
            "walletAddressId": kw["wallet_address_id"],
            "receiver": kw["receiver"],
            "debitAmount": amt,
            "receiveAmount": amt,
        }

    async def create_outgoing_payment(self, **kw):
        self.calls.append(("create_outgoing_payment", kw))
        return {"id": "payment-1", "walletAddressId": kw["wallet_address_id"], "state": "FUNDING"}

    async def deposit_event_liquidity(self, **kw):
        self.calls.append(("deposit_event_liquidity", kw))
        return self.deposit_success

    async def withdraw_event_liquidity(self, **kw):
        self.calls.append(("withdraw_event_liquidity", kw))
        return True

    async def aclose(self) -> None:
        pass


@pytest_asyncio.fixture
async def engine():
    """A fresh in-memory SQLite engine with schema created, per test."""
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng.sync_engine, "connect")
    def _disable_pysqlite_begin(dbapi_connection, _record):
        dbapi_connection.isolation_level = None

    @event.listens_for(eng.sync_engine, "begin")
    def _emit_begin(conn):
        conn.exec_driver_sql("BEGIN")

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
def sessionmaker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(sessionmaker):
    """A session for exercising services directly."""
    async with sessionmaker() as s:
        yield s


@pytest_asyncio.fixture
def fake_rafiki():
    return FakeRafikiClient()


@pytest_asyncio.fixture
async def client(sessionmaker, fake_rafiki):
    """An HTTP client bound to the app, with DB + Rafiki dependencies overridden."""

    async def _override_get_session():
        async with sessionmaker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    async def _override_get_rafiki():
        yield fake_rafiki

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_rafiki_client] = _override_get_rafiki
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
