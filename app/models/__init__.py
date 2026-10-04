"""SQLAlchemy ORM models.

Phase 1 ships only the declarative ``Base`` and shared column types. Concrete
models (users, wallets, ledger, webhook events) arrive in later phases; import
them here as they land so Alembic autogenerate discovers their tables.
"""

from app.models.base import Base

__all__ = ["Base"]
