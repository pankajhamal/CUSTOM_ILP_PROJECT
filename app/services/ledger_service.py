"""Double-entry ledger engine.

Phase 1 stub. Later phase: implement ``LedgerService`` with balanced postings
(``sum(debits) == sum(credits)``), account provisioning, reserve holds,
settlement, non-negative balance enforcement, and idempotent transactions
(unique reference). This is the only place money is allowed to move.
"""

from __future__ import annotations
