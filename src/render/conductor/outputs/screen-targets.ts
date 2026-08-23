import type { TargetDecl, TimescaleTag } from '../types'

// ScreenOutput's targets (SINTEZA_SIGNAL_BUS.md §6.2): the screen's raw
// routable inputs. Screen accepts every timescale tag (§5.1: "screen
// targets accept all tags") — nothing here is safety-gated the way a servo
// target would be (see patchbay/configs/servo-targets.ts). The three
// genuinely nonlinear screen params (flowStrength, symmetry, fieldDecay)
// are NOT targets themselves — they're computed in
// patchbay/screen-composites.ts from these routed inputs; see that file's
// header comment for why.
const ALL_TAGS: TimescaleTag[] = ['transient', 'beat', 'bar', 'section', 'continuous']

export const SCREEN_TARGETS: TargetDecl[] = [
  { id: 'screen.buildWindup', acceptsTags: ALL_TAGS, defaultValue: 0, range: [-2, 3] },
  { id: 'screen.buildProgress', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.tension', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.suspension', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.energy', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.flatness', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.centroid', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.pan', acceptsTags: ALL_TAGS, defaultValue: 0, range: [-1, 1] },
  { id: 'screen.sub', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.low', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.mid', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.presence', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.air', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.bandTilt', acceptsTags: ALL_TAGS, defaultValue: 0, range: [-1, 1] },
  { id: 'screen.beatPhase', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.beatPulse', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.barPhase', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.tempoBpm', acceptsTags: ALL_TAGS, defaultValue: 120, range: [0, 300] },
  { id: 'screen.tempoConfidence', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.dropImpulse', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.familiarity', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  // Newly routable (previously hardcoded formulas inside screen-composites.ts,
  // never a target at all — no way to automate palette from the patchbay).
  // hueDrift's own default 0..1 sawtooth wraps via `% 1` where it's actually
  // read (screen-composites.ts), so clamping to this target's range only
  // matters if a route pushes the sum past it, a rare/minor edge case.
  { id: 'screen.hueShift', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.paletteMix', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1] },
  { id: 'screen.idle', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 1], passThrough: true },
  { id: 'screen.scope', acceptsTags: ALL_TAGS, defaultValue: 0, range: [0, 0], passThrough: true },
]
