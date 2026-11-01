# Custom ILP Wallet — Frontend

Minimal React + TypeScript + Tailwind CSS client for the Custom ILP ASE backend.

## Features

- **Create / load account** — register a user (provisions ledger accounts) or
  continue with an existing user id (kept in `localStorage`).
- **Dashboard** — available & reserved balances, wallet address with copy,
  refresh.
- **Create wallet address** — one click, synced with Rafiki.
- **Send money** — receiver URL or `$payment-pointer`, decimal amount
  (converted to integer minor units), quote + payment status feedback.

## Stack

Vite · React 19 · TypeScript (strict) · Tailwind CSS v4 (`@tailwindcss/vite`).
No router, no state library — two screens and `fetch`.

## Develop

```bash
# backend must be running on :8000 (docker compose up -d, or host uvicorn)
npm install
npm run dev          # http://localhost:5173
```

API calls go to `/api/v1/*` and the Vite dev server proxies them to
`http://localhost:8000` (see `vite.config.ts`) — no CORS needed. To point at a
different backend set `VITE_API_BASE`, e.g.:

```bash
VITE_API_BASE=http://localhost:8000/api/v1 npm run dev
```

## Build

```bash
npm run build        # typecheck + bundle to dist/
npm run preview
```

## Layout

```
src/
  lib/api.ts        typed API client (users, wallets, payments)
  lib/money.ts      minor-unit formatting/parsing
  components/ui.tsx Card, Button, Input, Field, Note, Spinner
  screens/Onboard.tsx    register / load account
  screens/Dashboard.tsx  balances, wallet, send money
  App.tsx           session restore + screen switching
```
