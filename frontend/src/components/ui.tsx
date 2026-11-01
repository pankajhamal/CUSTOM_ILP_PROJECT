import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      {title && (
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">
          {title}
        </h2>
      )}
      {children}
    </section>
  )
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' }) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50'
  const styles =
    variant === 'primary'
      ? 'bg-indigo-600 text-white hover:bg-indigo-500'
      : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700'
  return <button className={`${base} ${styles} ${className}`} {...props} />
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-zinc-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-zinc-400">{hint}</span>}
    </label>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
      {...props}
    />
  )
}

export function Note({ kind, children }: { kind: 'error' | 'success'; children: ReactNode }) {
  const styles =
    kind === 'error'
      ? 'border-red-200 bg-red-50 text-red-700'
      : 'border-emerald-200 bg-emerald-50 text-emerald-700'
  return <div className={`rounded-lg border px-3 py-2 text-sm break-words ${styles}`}>{children}</div>
}

export function Spinner() {
  return (
    <span
      aria-label="loading"
      className="inline-block size-4 animate-spin rounded-full border-2 border-zinc-300 border-t-indigo-600"
    />
  )
}
