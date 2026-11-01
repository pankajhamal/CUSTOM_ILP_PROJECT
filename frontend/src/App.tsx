import { useEffect, useState } from 'react'
import { getUser, type User } from './lib/api'
import { Onboard } from './screens/Onboard'
import { Dashboard } from './screens/Dashboard'
import { Spinner } from './components/ui'

const STORAGE_KEY = 'ilp.userId'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [restoring, setRestoring] = useState(true)

  // Restore the session from the stored user id, if any.
  useEffect(() => {
    const id = localStorage.getItem(STORAGE_KEY)
    if (!id) {
      setRestoring(false)
      return
    }
    getUser(id)
      .then(setUser)
      .catch(() => localStorage.removeItem(STORAGE_KEY))
      .finally(() => setRestoring(false))
  }, [])

  function handleReady(u: User) {
    localStorage.setItem(STORAGE_KEY, u.id)
    setUser(u)
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY)
    setUser(null)
  }

  if (restoring) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      {user ? (
        <Dashboard key={user.id} user={user} onLogout={handleLogout} />
      ) : (
        <Onboard onReady={handleReady} />
      )}
    </div>
  )
}
