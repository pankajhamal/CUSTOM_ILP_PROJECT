import { useCallback, useState } from 'react'
import {
  createWallet,
  devFaucet,
  getUser,
  sendPayment,
  type SendPaymentResult,
  type User,
} from '../lib/api'
import { formatMinor, parseMajor } from '../lib/money'
import { Button, Card, Field, Input, Note, Spinner } from '../components/ui'

export function Dashboard({ user: initial, onLogout }: { user: User; onLogout: () => void }) {
  const [user, setUser] = useState(initial)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setUser(await getUser(initial.id))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [initial.id])

  const wallet = user.wallet_addresses[0] ?? null
  const available = user.ledger_accounts.find((a) => a.name.endsWith(':available'))
  const reserved = user.ledger_accounts.find((a) => a.name.endsWith(':reserved'))
  const scale = available?.asset_scale ?? 2
  const code = available?.asset_code ?? 'USD'

  return (
    <div className="mx-auto max-w-xl px-4 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-indigo-600 font-bold text-white">
            {user.username.slice(0, 1).toUpperCase()}
          </div>
          <div>
            <h1 className="font-semibold text-zinc-900">{user.username}</h1>
            <p className="text-xs text-zinc-400">{user.email ?? 'no email'}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" onClick={() => void refresh()}>
            Refresh
          </Button>
          <Button variant="ghost" onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </header>

      {error && (
        <div className="mb-4">
          <Note kind="error">{error}</Note>
        </div>
      )}

      <div className="space-y-4">
        {/* Balances */}
        <div className="grid grid-cols-2 gap-4">
          <Card title="Available">
            <p className="text-3xl font-semibold tracking-tight text-zinc-900">
              {available ? formatMinor(available.balance, scale) : '—'}
              <span className="ml-1 text-sm font-normal text-zinc-400">{code}</span>
            </p>
            <FaucetButton userId={user.id} scale={scale} onCredited={refresh} />
          </Card>
          <Card title="Reserved">
            <p className="text-3xl font-semibold tracking-tight text-zinc-900">
              {reserved ? formatMinor(reserved.balance, scale) : '—'}
              <span className="ml-1 text-sm font-normal text-zinc-400">{code}</span>
            </p>
          </Card>
        </div>

        {/* Wallet */}
        <WalletSection userId={user.id} walletAddress={wallet?.wallet_address ?? null} onChanged={refresh} />

        {/* Send */}
        {wallet && (
          <SendSection walletId={wallet.id} scale={scale} code={code} onSent={refresh} />
        )}
      </div>

      <footer className="mt-8 text-center text-xs text-zinc-300">
        user id: <span className="select-all font-mono">{user.id}</span>
      </footer>
    </div>
  )
}

function FaucetButton({
  userId,
  scale,
  onCredited,
}: {
  userId: string
  scale: number
  onCredited: () => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const amount = 100 * 10 ** scale // 100.00 in minor units

  async function credit() {
    setBusy(true)
    setError(null)
    try {
      await devFaucet(userId, amount)
      await onCredited()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2">
      <button
        onClick={() => void credit()}
        disabled={busy}
        className="inline-flex items-center gap-1 text-xs font-medium text-indigo-500 hover:text-indigo-700 disabled:opacity-50"
        title="Dev only: credits test money via the ledger"
      >
        {busy ? <Spinner /> : '+'} Add {formatMinor(amount, scale)} test money
      </button>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  )
}

function WalletSection({
  userId,
  walletAddress,
  onChanged,
}: {
  userId: string
  walletAddress: string | null
  onChanged: () => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  async function create() {
    setBusy(true)
    setError(null)
    try {
      await createWallet(userId)
      await onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function copy() {
    if (!walletAddress) return
    await navigator.clipboard.writeText(walletAddress)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Card title="Wallet address">
      {walletAddress ? (
        <div className="flex items-center justify-between gap-3">
          <code className="truncate text-sm text-zinc-700">{walletAddress}</code>
          <Button variant="ghost" onClick={() => void copy()}>
            {copied ? 'Copied ✓' : 'Copy'}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-zinc-500">
            No wallet address yet. Create one to receive Interledger payments.
          </p>
          {error && <Note kind="error">{error}</Note>}
          <Button onClick={() => void create()} disabled={busy}>
            {busy && <Spinner />}
            Create wallet address
          </Button>
        </div>
      )}
    </Card>
  )
}

function SendSection({
  walletId,
  scale,
  code,
  onSent,
}: {
  walletId: string
  scale: number
  code: string
  onSent: () => Promise<void>
}) {
  const [receiver, setReceiver] = useState('')
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SendPaymentResult | null>(null)

  const minor = parseMajor(amount, scale)
  const canSend = receiver.trim() !== '' && minor !== null && !busy

  async function send() {
    if (minor === null) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await sendPayment({
        sender_wallet_address_id: walletId,
        receiver: receiver.trim(),
        amount: minor,
      })
      setResult(res)
      setReceiver('')
      setAmount('')
      await onSent()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Send money">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (canSend) void send()
        }}
      >
        <Field label="Receiver" hint="wallet address URL or $payment-pointer">
          <Input
            value={receiver}
            onChange={(e) => setReceiver(e.target.value)}
            placeholder="https://rafiki-backend.testnet.test/.well-known/pay/bob"
          />
        </Field>
        <Field label={`Amount (${code})`}>
          <Input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="10.00"
          />
        </Field>

        {error && <Note kind="error">{error}</Note>}
        {result && (
          <Note kind="success">
            Payment <span className="font-mono">{result.payment_id.slice(0, 8)}…</span> created —{' '}
            {result.status}. Debit {formatMinor(result.quote.debit_amount, result.quote.asset_scale)}{' '}
            {result.quote.asset_code}, receiver gets{' '}
            {formatMinor(result.quote.receive_amount, result.quote.asset_scale)}{' '}
            {result.quote.asset_code}.
          </Note>
        )}

        <Button type="submit" disabled={!canSend} className="w-full">
          {busy && <Spinner />}
          Send
        </Button>
      </form>
    </Card>
  )
}
