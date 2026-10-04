"""Declarative base, timestamp mixin, and cross-database column types.

Models use database-agnostic types so the same ORM works against PostgreSQL in
production and SQLite (aiosqlite) in the test suite:

  * ``GUID``      — native ``UUID`` on PostgreSQL, ``CHAR(32)`` elsewhere
    (provided by SQLAlchemy 2.0's :class:`~sqlalchemy.Uuid`).
  * ``JSONB``     — ``JSONB`` on PostgreSQL, generic ``JSON`` elsewhere.
  * ``Amount``    — ``BigInteger`` (integer minor units, Open Payments style).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, MetaData, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

# Portable column types -----------------------------------------------------

#: UUID primary/foreign keys — native on PG, CHAR(32) elsewhere.
GUID = Uuid(as_uuid=True)

#: JSON blobs — JSONB on PG (indexable), generic JSON on SQLite.
JSONB = JSON().with_variant(PG_JSONB(astext_type=None), "postgresql")

#: Monetary amounts as integer minor units.
Amount = BigInteger

# Consistent constraint naming so Alembic autogenerate produces stable names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    """A UUID primary key column with a Python-side ``uuid4`` default."""
    return mapped_column(GUID, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` managed by the database clock."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
