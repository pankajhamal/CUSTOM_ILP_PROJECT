import { useState } from 'react'
import { getUser, registerUser, type User } from '../lib/api'
import { Button, Card, Field, Input, Note, Spinner } from '../components/ui'

type Mode = 'register' | 'load'

export function Onboard({ onReady }: { onReady: (user: User) => void }) {
  const [mode, setMode] = useState<Mode>('register')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [userId, setUserId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const user =
        mode === 'register'
          ? await registerUser({
              username: username.trim(),
              email: email.trim() || undefined,
              password,
            })
          : await getUser(userId.trim())
      onReady(user)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const canSubmit =
    mode === 'register' ? username.trim().length >= 3 && password.length >= 8 : userId.trim() !== ''

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 px-4 py-10">
      <header className="text-center">
        <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-2xl bg-indigo-600 text-xl font-bold text-white">
          ⬡
        </div>
        <h1 className="text-xl font-semibold text-zinc-900">Custom ILP Wallet</h1>
        <p className="mt-1 text-sm text-zinc-500">Interledger payments on Rafiki</p>
      </header>

      <Card>
        <div className="mb-4 grid grid-cols-2 rounded-lg bg-zinc-100 p-1 text-sm font-medium">
          {(['register', 'load'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-md py-1.5 transition-colors ${
                mode === m ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500'
              }`}
            >
              {m === 'register' ? 'Create account' : 'Existing account'}
            </button>
          ))}
        </div>

        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (canSubmit && !busy) void submit()
          }}
        >
          {mode === 'register' ? (
            <>
              <Field label="Username" hint="lowercase, 3+ characters">
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="alice"
                  autoFocus
                />
              </Field>
              <Field label="Email (optional)">
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alice@example.com"
                />
              </Field>
              <Field label="Password" hint="8+ characters">
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </Field>
            </>
          ) : (
            <Field label="User ID" hint="the UUID returned when the account was created">
              <Input
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-…"
                autoFocus
              />
            </Field>
          )}

          {error && <Note kind="error">{error}</Note>}

          <Button type="submit" disabled={!canSubmit || busy} className="w-full">
            {busy && <Spinner />}
            {mode === 'register' ? 'Create account' : 'Continue'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
