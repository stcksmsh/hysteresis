import type { DropTrigger } from '../../shared/types'

// SINTEZA_SIGNAL_BUS.md §3 — every routable bus signal is tagged with how
// fast it's allowed to move. This is load-bearing for output safety (a
// servo output can refuse transient-tagged signals it physically can't
// follow) and must exist from day one even though only ScreenOutput (which
// accepts every tag) is implemented yet — see patchbay/configs/servo-targets.ts.
export type TimescaleTag = 'transient' | 'beat' | 'bar' | 'section' | 'continuous'

// The Signal Bus (SINTEZA_SIGNAL_BUS.md §3): a flat, named, normalized
// record produced fresh every frame by the Conductor. THE cross-boundary
// contract — patchbay routes read this and only this (R2: the bus is pulled,
// never pushes). `scope` is the one field exempt from the
// normalization/timescale rules (§3.1's pass-through note) and `idle` is
// meta, not a routable signal — both are still carried here since outputs
// pull the whole bus's *shape*, just routed differently (passThrough routes,
// see patchbay/types.ts) rather than through curve/smoothing/range.
export interface SignalBus {
  // continuous — the groove-carriers, alive every frame for a track's entire
  // runtime (SINTEZA_SIGNAL_BUS.md §3.1, §4.1's "aliveness" fix).
  energy: number
  sub: number
  low: number
  mid: number
  presence: number
  air: number
  bandTilt: number // bipolar -1..1, spectral balance (low-heavy <-> high-heavy)
  centroid: number
  flatness: number
  pan: number // bipolar -1..1, whole-mix stereo balance
  familiarity: number // §4.2 — online self-similarity, added in step 4

  // beat
  beatPhase: number
  beatPulse: number // 0..1 decaying pulse re-triggered each beat boundary

  // bar
  barPhase: number
  // 0..1 decaying pulse on beat 1. Computed every frame but NOT currently
  // routed to any screen target in screen-only.ts/screen-targets.ts —
  // present on the bus (per the spec's signal set, §3.1) and available for
  // a future route, but presently dead weight for ScreenOutput specifically.
  downbeatPulse: number

  // section — sparse, dramatic, no longer the *only* drivers
  buildWindup: number // spring-driven integrated build (was ParamBus.windup)
  buildProgress: number // lightly-smoothed raw integrated build
  tension: number
  suspension: number // slow "have we been held" envelope

  // transient — event-derived, never routable to slow/physical outputs
  dropImpulse: number // 0..1, decays from event.strength at a drop, else decays toward 0
  // 0..1, decaying pulse per broadband onset. Same caveat as downbeatPulse
  // above: computed every frame, not currently routed to any screen target.
  onsetImpulse: number

  // Discrete companion to dropImpulse. SINTEZA_SIGNAL_BUS.md §3.1 allows
  // keeping a discrete event internally ("the discrete event may still
  // exist internally for the symmetry snap") — this is that allowance.
  // NOT currently consumed downstream: ScreenParamAssembler re-derives its
  // own drop-trigger by edge-detecting a rise in the routed `dropImpulse`
  // target rather than reading this field (see screen-composites.ts's
  // DROP_EDGE_EPS check), so this sits on the bus unread. Left in place as
  // the sanctioned escape hatch for the day something genuinely needs the
  // exact strength/age shape instead of a re-derived edge — not a general
  // one, no new discrete fields should be added here without the same
  // justification.
  dropTrigger: DropTrigger | null

  // pass-through — not shaped/normalized like the rest, beam-only.
  scope: Float32Array | null

  // meta
  idle: boolean
  tempoBpm: number
  tempoConfidence: number
}

// Every *routable* scalar signal's timescale tag. `scope`/`idle` are
// deliberately absent — they're pass-through/meta, not curve-and-range
// routable (see Route/passThrough in patchbay/types.ts).
export const SIGNAL_TAGS = {
  energy: 'continuous',
  sub: 'continuous',
  low: 'continuous',
  mid: 'continuous',
  presence: 'continuous',
  air: 'continuous',
  bandTilt: 'continuous',
  centroid: 'continuous',
  flatness: 'continuous',
  pan: 'continuous',
  familiarity: 'continuous',

  beatPhase: 'beat',
  beatPulse: 'beat',

  barPhase: 'bar',
  downbeatPulse: 'bar',

  buildWindup: 'section',
  buildProgress: 'section',
  tension: 'section',
  suspension: 'section',

  dropImpulse: 'transient',
  onsetImpulse: 'transient',

  tempoBpm: 'continuous',
  tempoConfidence: 'continuous',
} as const satisfies Partial<Record<keyof SignalBus, TimescaleTag>>

export type RoutableSignalName = keyof typeof SIGNAL_TAGS

// A target an output exposes for the patchbay to route into
// (SINTEZA_SIGNAL_BUS.md §6.1). `acceptsTags` is what makes servo-safety
// structural rather than a comment someone has to remember (§5.3).
export interface TargetDecl {
  id: string
  acceptsTags: TimescaleTag[]
  defaultValue: number
  range: [number, number]
  // Bypasses curve/smoothing/range/clamp entirely — the resolved value is
  // the named bus field copied verbatim (used for `scope`, a Float32Array,
  // and `idle`, a boolean; neither is a curve-shaped scalar). Exempt from
  // timescale-tag validation too, matching §3.1's explicit exemption for
  // `scope`.
  passThrough?: boolean
}

export type ResolvedTargetValue = number | Float32Array | null | DropTrigger | boolean
export type ResolvedTargets = Record<string, ResolvedTargetValue>

// SINTEZA_SIGNAL_BUS.md §6.1 — every output implements this. Pull-model
// (R2): the frame loop resolves the bus through the patchbay per output,
// then hands each output only its own resolved targets; the output never
// sees the raw bus itself.
export interface VizOutput {
  readonly id: string
  readonly targets: TargetDecl[]
  update(dt: number, resolvedTargets: ResolvedTargets): void
  dispose(): void
}
