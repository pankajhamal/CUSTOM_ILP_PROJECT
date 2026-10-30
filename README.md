# Custom ILP ASE

A production-grade **Account Servicing Entity (ASE)** for the Interledger Protocol,
built on [Rafiki](https://rafiki.dev). It owns user accounts, wallet-address
provisioning, and a **double-entry ledger** that is the single source of truth for
balances. Rafiki handles ILP packet clearing and settlement; this service handles
accounting, authentication, and webhook processing.

> Rafiki does **not** store balances. It talks to us only over its GraphQL Admin
> API (outbound, HMAC-signed) and HTTP webhooks (inbound, HMAC-verified). We are
> the source of truth for money.

## Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Basic setup (config, DB, security, telemetry, health) | ✅ |
| 2 | Data model (users, wallets, ledger, webhook events) + migrations | ✅ |
| 3 | Provisioning (register user + ledger accounts + Rafiki wallet sync) | ✅ verified live |
| 4 | Incoming payments (signed webhooks, idempotency, ledger credit, /rates) | ✅ |
| 5 | Outgoing payments (reserve hold, receiver+quote+payment, settle/release) | ✅ verified live |
| 6 | Hardening (test suite, webhook simulator) | ✅ (auth/observability ongoing) |

## API surface

```
GET  /api/v1/health            liveness        GET  /api/v1/health/ready   readiness
POST /api/v1/users             register + provision ledger accounts
GET  /api/v1/users/{id}
POST /api/v1/wallets           create wallet address (synced with Rafiki)
GET  /api/v1/wallets/{id}
POST /api/v1/payments/send     reserve hold + receiver + quote + outgoing payment

# Rafiki callbacks (root-mounted — Rafiki calls these without /api/v1):
POST /webhooks/rafiki          HMAC-verified (rafiki-signature), idempotent
GET  /rates?base=USD           exchange-rate provider for quoting
```

## Ledger invariants

- Money never moves via `balance = balance + X`; every movement is a balanced
  transaction (`sum(debits) == sum(credits)`) with immutable entries.
- Amounts are **integers** in asset minor units (`assetScale=2` → `1000` = 10.00).
- Cached per-account counters update atomically with entries under
  `SELECT … FOR UPDATE`; spendable accounts enforce a non-negative floor.
- Webhooks are deduplicated by Rafiki's event id (unique constraint) — retries
  never double-post.

Flow postings: incoming → `DEBIT clearing:rafiki / CREDIT liability:<user>:available`;
send → hold `available → reserved`; settled → `reserved → clearing:rafiki`;
failed → hold released back to `available`.

## Quick start

```bash
cp .env.example .env            # fill in Rafiki secrets + asset (see below)
docker compose up -d db         # Postgres
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Swagger: http://localhost:8000/docs
```

Or fully in Docker: `docker compose up --build` (API + Postgres + Jaeger;
CloudBeaver on :8978 if enabled).

### Rafiki testnet integration

The ASE is wired to the Interledger **testnet** running locally (Cloud Nine
Wallet). Key facts:

- Admin API: `RAFIKI_GRAPHQL_URL=http://localhost:3011/graphql` (host) or
  `http://host.docker.internal:3011/graphql` (from the API container).
- Admin calls are signed: HMAC-SHA256 over `{ts}.{canonicalize({variables,query})}`,
  headers `signature` + `tenant-id`. Secrets must match the testnet `local/.env`
  (`ADMIN_API_SECRET` → `RAFIKI_API_SECRET`, `OPERATOR_TENANT_ID` → `RAFIKI_TENANT_ID`,
  `RAFIKI_SIGNATURE_SECRET` shared for webhooks).
- `RAFIKI_ASSET_ID` must be an asset created **under our tenant** (create via the
  Admin API; using another tenant's asset yields "unknown asset"). The testnet
  resets periodically — recreate the asset and update `.env` when it does.
- Wallet addresses must start with the backend's `WALLET_ADDRESS_URL`
  (`https://rafiki-backend.testnet.test/.well-known/pay`).

## Testing

```bash
poetry run pytest          # 37 tests, in-memory SQLite + mocked Rafiki, ~3s
```

Covers HMAC verification, double-entry invariants (balance, overdraft,
duplicate-reference, asset mismatch), webhook idempotency/auth/settlement, and
the send flow (hold, pointer normalization, 402/404/422 paths).

## Simulating webhooks

With the API running (no Rafiki needed):

```bash
poetry run python scripts/simulate_webhook.py \
  --event incoming_payment.completed \
  --wallet-address-id <rafiki-wallet-address-id> \
  --amount 1000
```

Events: `incoming_payment.completed`, `outgoing_payment.created|completed|failed`.
Replays with the same `--event-id` are acknowledged as duplicates without
touching the ledger.

## Project layout

```
app/
  core/      config (UPPERCASE env settings), async DB, HMAC + bcrypt, OTel
  models/    users, wallet_addresses, ledger (accounts/transactions/entries), webhook_events
  schemas/   Pydantic request/response + webhook envelope
  services/  ledger engine, Rafiki GraphQL client, wallet/payment/webhook services
  api/       v1 routers + root-mounted Rafiki callbacks (webhooks, rates)
alembic/     async migrations (4 revisions)
scripts/     simulate_webhook.py
tests/       pytest suite (conftest with SQLite SAVEPOINT workaround)
docs/        architecture.md + architecture.pdf
```

## Migrations

```bash
poetry run alembic revision --autogenerate -m "describe change"
poetry run alembic upgrade head
```

## License

MIT
