/** Integer minor-unit money helpers (Open Payments style). */

/** 1234 @ scale 2 -> "12.34" */
export function formatMinor(value: number, scale: number): string {
  const factor = 10 ** scale
  const major = Math.trunc(value / factor)
  const frac = Math.abs(value % factor)
  return scale > 0 ? `${major}.${String(frac).padStart(scale, '0')}` : String(major)
}

/** "12.34" @ scale 2 -> 1234. Returns null for invalid/negative input. */
export function parseMajor(input: string, scale: number): number | null {
  const trimmed = input.trim()
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return null
  const [whole, frac = ''] = trimmed.split('.')
  if (frac.length > scale) return null
  const minor = Number(whole) * 10 ** scale + Number(frac.padEnd(scale, '0') || '0')
  return Number.isSafeInteger(minor) && minor > 0 ? minor : null
}
