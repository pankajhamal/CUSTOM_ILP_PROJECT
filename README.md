# Custom ILP ASE

A production-grade **Account Servicing Entity (ASE)** for the Interledger Protocol,
designed to sit in front of a [Rafiki](https://rafiki.dev) node. It owns user
accounts, wallet-address provisioning, and a **double-entry ledger** that is the
single source of truth for balances. Rafiki handles ILP packet clearing and
settlement; this service handles accounting, authentication, and webhook
processing.

> Rafiki does **not** store balances. It talks to us only over its GraphQL Admin
> API (outbound) and HTTP webhooks (inbound). We are the source of truth for money.

## Status — Phase 1: basic setup

This repository currently contains the **runnable skeleton** only:

- ✅ Project structure, dependencies (`pyproject.toml`), Docker + Compose
- ✅ Config (`pydantic-settings`), async SQLAlchemy engine/session, telemetry wiring
- ✅ HMAC-SHA256 helpers in `app/core/security.py`
- ✅ FastAPI app that boots, with a working **health** endpoint
- ✅ Alembic configured (no migrations generated yet)
- 🚧 Models, schemas, services, and the user/wallet/payment/webhook endpoints are
  **stubs** — filled in during later phases
- 🚧 Tests and the webhook simulator — later phases

## Architecture (target)

```
External Network  ──ILP/STREAM──►  Rafiki Node  ──GraphQL Admin API──►  This ASE
                                       │                                   │
                                       └────────── HTTP webhooks ──────────┘
                                         (HMAC-SHA256 signed, idempotent)
```

Three core flows (built out in later phases):

1. **Provisioning** — register a user, create local ledger accounts, create a
   wallet address in Rafiki, store the returned `walletAddressId`.
2. **Incoming payment** — Rafiki clears an inbound STREAM, then fires
   `incoming_payment.completed`; we verify the signature, check idempotency, and
   post `DEBIT clearing:rafiki` / `CREDIT liability:<user>:available`.
3. **Outgoing payment** — place a reserve hold (`available → reserved`), quote +
   create an outgoing payment in Rafiki, fund liquidity on
   `outgoing_payment.created`, finalize on `outgoing_payment.completed`.

## Project layout

```
app/
  core/      config, async DB engine, HMAC security, telemetry   (implemented)
  models/    base.py + stubs                                     (base only)
  schemas/   stubs                                               (later phase)
  services/  ledger / Rafiki client / webhook dispatch stubs     (later phase)
  api/       health endpoint; users/wallets/payments/webhooks    (health only)
alembic/     migration environment (no migrations yet)
scripts/     developer tooling                                   (later phase)
tests/       test suite                                          (later phase)
```

## Quick start

### With Docker

```bash
cp .env.example .env            # edit secrets
docker compose up --build
# API docs:   http://localhost:8000/docs
# Health:     http://localhost:8000/api/v1/health
# Jaeger:     http://localhost:16686
```

> Note: the Compose `api` service runs `alembic upgrade head` on start. Until the
> first migration is generated (a later phase) there are no tables to create;
> the app's health endpoint still comes up.

### Local (Poetry)

```bash
poetry install
cp .env.example .env            # point DATABASE_URL at a running Postgres (or leave default)
poetry run uvicorn app.main:app --reload
# then open http://localhost:8000/api/v1/health
```

## Configuration

All settings load from the environment / `.env`; see `.env.example` for the full
list (database, Rafiki Admin API, webhook HMAC secret, default asset, telemetry).

## Migrations (once models land)

```bash
poetry run alembic revision --autogenerate -m "describe change"
poetry run alembic upgrade head
```

## License

MIT
