"""Double-entry ledger models: accounts, transactions, and entries.

Phase 1 stub. Later phase: define ``LedgerAccount`` (with cached debit/credit
counters), ``LedgerTransaction`` (a balanced journal), and the immutable
``LedgerEntry`` postings, plus the ``AccountType`` / ``NormalBalance`` /
``EntryDirection`` enums. Monetary amounts are integer minor units
(``Amount`` from ``app.models.base``). Register the models in
``app.models.__init__``.
"""

from __future__ import annotations
