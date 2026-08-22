import type { TimescaleTag } from '../types'

export type Curve = 'linear' | 'exp' | 'log' | 'smoothstep' | { kind: 'threshold'; cut: number }

export interface SmoothingSpec {
  attackSec: number
  releaseSec: number
}

// A route is data (SINTEZA_SIGNAL_BUS.md §5.1): which bus signal drives
// which output target, and how. Rerouting = editing this object, never code
// (R4). `from` names a bus signal (SignalBus's routable fields, or a
// pass-through field like `scope`/`idle` when `passThrough` is set — see
// TargetDecl.passThrough, which the route must match for a pass-through
// target). `curve`/`smoothing`/`gain`/`offset`/`invert` are the "personality
// of the show" knobs; a target with no route holds its `defaultValue`.
export interface Route {
  from: string
  to: string
  curve?: Curve
  smoothing?: SmoothingSpec
  invert?: boolean
  gain?: number
  offset?: number
  passThrough?: boolean
}

// A saved patchbay config is the whole mapping for one "personality"
// (§5.2) — `screen-only` is the only one built in this pass.
export interface PatchbayConfig {
  id: string
  routes: Route[]
}

export type { TimescaleTag }
