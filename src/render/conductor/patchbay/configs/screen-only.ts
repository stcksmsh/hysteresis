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

// Reproduces the previously-hardcoded palette formulas exactly (moved out of
// screen-composites.ts so they're real routes instead — see
// screen-targets.ts's comment on why): hueShift was `hueDrift + centroid*0.1`
// — two routes summing into the same target (the patchbay's documented
// default combine mode, §5.1) does the same arithmetic. paletteMix was a
// straight passthrough of buildWindup. Editing/replacing any of these three
// routes is now the actual palette-automation control surface — swap
// `centroid` for a different signal's gain, or route something else into
// `screen.paletteMix` entirely, all without touching this file by hand
// (that's the whole point of the patchbay editor).
const paletteRoutes: Route[] = [
  { from: 'hueDrift', to: 'screen.hueShift', curve: 'linear' },
  { from: 'centroid', to: 'screen.hueShift', curve: 'linear', gain: 0.1 },
  { from: 'buildWindup', to: 'screen.paletteMix', curve: 'linear' },
]

const passThroughRoutes: Route[] = [
  { from: 'idle', to: 'screen.idle', passThrough: true },
  { from: 'scope', to: 'screen.scope', passThrough: true },
]

export const screenOnlyConfig: PatchbayConfig = {
  id: 'screen-only',
  routes: [...identityRoutes, ...paletteRoutes, ...passThroughRoutes],
}
