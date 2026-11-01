/** Typed client for the Custom ILP ASE backend.
 *
 * In dev, requests go to `/api/v1/...` and Vite proxies them to :8000, so no
 * CORS configuration is needed. Set VITE_API_BASE to call another origin.
 */

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'

// ---------------------------------------------------------------------------
// Types mirroring the backend's Pydantic schemas
// ---------------------------------------------------------------------------

export interface LedgerAccount {
  id: string
  name: string
  account_type: string
  normal_balance: string
  asset_code: string
  asset_scale: number
  balance: number
}

export interface WalletAddress {
  id: string
  user_id: string
  wallet_address: string
  rafiki_wallet_address_id: string
  asset_code: string
  asset_scale: string // backend stores this as a string column
  created_at: string
}

export interface User {
  id: string
  username: string
  email: string | null
  is_active: boolean
  created_at: string
  ledger_accounts: LedgerAccount[]
  wallet_addresses: WalletAddress[]
}

export interface QuoteInfo {
  quote_id: string
  debit_amount: number
  receive_amount: number
  asset_code: string
  asset_scale: number
}

export interface SendPaymentResult {
  payment_id: string
  status: string
  quote: QuoteInfo
  hold_transaction_id: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail))
        message = body.detail
          .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).join('.')}: ${d.msg}`)
          .join('; ')
    } catch {
      /* non-JSON error body — keep the status text */
    }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export function registerUser(input: {
  username: string
  email?: string
  password: string
}): Promise<User> {
  return request<User>('/users', { method: 'POST', body: JSON.stringify(input) })
}

export function getUser(id: string): Promise<User> {
  return request<User>(`/users/${id}`)
}

export function createWallet(userId: string): Promise<WalletAddress> {
  return request<WalletAddress>('/wallets', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  })
}

export interface FaucetResult {
  credited: number
  available_balance: number
  transaction_id: string
}

/** Dev-only: credit the user with test money (minor units). 403 in production. */
export function devFaucet(userId: string, amount: number): Promise<FaucetResult> {
  return request<FaucetResult>('/dev/faucet', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, amount }),
  })
}

export function sendPayment(input: {
  sender_wallet_address_id: string
  receiver: string
  amount: number
  description?: string
}): Promise<SendPaymentResult> {
  return request<SendPaymentResult>('/payments/send', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}
