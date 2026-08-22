import type { Curve } from './types'

// Response shapes a route may apply before gain/offset/invert
// (SINTEZA_SIGNAL_BUS.md §5.1). Operate directly on the bus signal's own
// domain (0..1 unipolar, -1..1 bipolar) — callers pick a curve that makes
// sense for the signal's actual domain; there's no automatic renormalization
// here.
export function applyCurve(curve: Curve | undefined, v: number): number {
  if (!curve) return v
  if (typeof curve === 'object') return v >= curve.cut ? 1 : 0
  switch (curve) {
    case 'linear':
      return v
    case 'exp':
      return Math.sign(v) * v * v
    case 'log':
      return Math.sign(v) * Math.log1p(Math.abs(v) * (Math.E - 1))
    case 'smoothstep': {
      const t = Math.min(1, Math.max(0, v))
      return t * t * (3 - 2 * t)
    }
  }
}
