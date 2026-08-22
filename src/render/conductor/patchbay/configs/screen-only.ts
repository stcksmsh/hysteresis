import type { PatchbayConfig, Route } from '../types'

// The default config (SINTEZA_SIGNAL_BUS.md §5.2, §9 step 1): every
// SignalBus field the screen actually uses, routed 1:1 into the identically-
// named `screen.*` target with no curve/smoothing (`curve: 'linear'`) —
// Conductor.ts already produces these "lightly-smoothed, honest" (§4.3), so
// the default config's job is just wiring, not shaping. This is what makes
// step 1's "reproduces today's mapping exactly" claim checkable: every
// number ScreenOutput's composites read traces back to one line here.
const IDENTITY_SIGNALS = [
  'buildWindup',
  'buildProgress',
  'tension',
  'suspension',
  'energy',
  'flatness',
  'centroid',
  'pan',
  'sub',
  'low',
  'mid',
  'presence',
  'air',
  'bandTilt',
  'beatPhase',
  'beatPulse',
  'barPhase',
  'tempoBpm',
  'tempoConfidence',
  'dropImpulse',
  'familiarity',
] as const

const identityRoutes: Route[] = IDENTITY_SIGNALS.map((signal) => ({
  from: signal,
  to: `screen.${signal}`,
  curve: 'linear',
}))

const passThroughRoutes: Route[] = [
  { from: 'idle', to: 'screen.idle', passThrough: true },
  { from: 'scope', to: 'screen.scope', passThrough: true },
]

export const screenOnlyConfig: PatchbayConfig = {
  id: 'screen-only',
  routes: [...identityRoutes, ...passThroughRoutes],
}
