import { SpringDamper } from '../../choreography/spring-damper'
import { DtSmoother } from '../dt-smoother'
import type { DropTrigger, ParamBus } from '../../../shared/types'
import type { ResolvedTargets } from '../types'

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

// SINTEZA_SIGNAL_BUS.md's route model (§5.1) is 1-signal-in -> 1-target-out;
// three of today's screen params (flowStrength, symmetry, fieldDecay) are
// genuinely nonlinear composites of several bus signals (max()s, a discrete
// hold, a spring with an event-triggered impulse) and don't reduce to that
// model or to the "sum, then clamp" multi-route combine mode. Rather than
// bend the patchbay's route model to fit three special cases, this module
// computes them explicitly, reading only *resolved, routed* target values
// (never the raw bus — R2 still holds, ScreenOutput never sees SignalBus
// directly) — a deliberate, documented deviation from "patchbay owns all
// routing logic", not an oversight. Pure/GL-free so it's unit-testable
// without a WebGL context (see tests/unit/conductor.spec.ts). buildWindup's
// own spring/impulse stays in Conductor.ts, since it's a genuine bus signal
// (§3.1 lists it as one) computed from raw StateFrame.events — not this
// module's concern.

const FIELD_DECAY_GROOVE = 0.86
const FIELD_DECAY_BUILD = 0.965
const FIELD_DECAY_BREAK_MAX = 0.985
const BAR_BREATH_AMPLITUDE = 0.01 // step 3: barPhase -> slow breathing, subtle so it never fights build/break

const FLOW_STRENGTH_STIFFNESS = 40
const FLOW_STRENGTH_DAMPING = 9
const FLOW_STRENGTH_BASE = 1
const FLOW_STRENGTH_BUILD_GAIN = 2.2
const FLOW_STRENGTH_ENERGY_GAIN = 0.9
const FLOW_SHOCKWAVE_IMPULSE = 30
const BEAT_THROB_GAIN = 0.14 // step 3: beatPulse -> field throb, modest so groove reads as a pulse not a strobe

const SYMMETRY_ATTACK_SEC = 0.5
const SYMMETRY_RELEASE_SEC = 2.2
const SYMMETRY_TENSION_GAIN = 0.5
const SYMMETRY_BUILD_GAIN = 0.55
const SYMMETRY_FLOOR = 0.18
const FLATNESS_BLOOM_THRESHOLD = 0.75
const FLATNESS_BLOOM_GAIN = 0.6
const SYMMETRY_DROP_HOLD_SEC = 2.0
// Reported "too psychedelic": tension/buildProgress/flatness/familiarity
// could all combine to push ambient symmetry all the way to full mirror —
// and since decay (persistence/brightness) rises off the same tension/build
// signals, a build or break got maximally mirrored AND maximally bright at
// once, for as long as that section lasted (which can be many seconds/tens
// of seconds — a build isn't a one-shot event). Capped below full so the
// screen never fully organizes into a pure kaleidoscope from ambient
// tension/build alone, no matter how long the section runs. The drop's
// snap-to-1 hold (symmetryHoldSec below) is untouched — that's a brief,
// deliberate, earned "punch" distinct from ambient organization, not the
// thing that was reported as overused.
const SYMMETRY_AMBIENT_CEILING = 0.72
const FAMILIARITY_SYMMETRY_GAIN = 0.15 // §4.2: familiarity gently blooms organization, distinct from the drop's snap

const HUE_DRIFT_PER_SEC = 0.01

const DROP_EDGE_EPS = 0.05 // dropImpulse rising by more than this in one frame reads as "a drop just happened"

const FLOW_DIRECTION_SMOOTH_SEC = 1.5 // step 3: bandTilt -> flow direction, eased so the drift axis doesn't jitter

export interface AssembledScreenParams extends ParamBus {
  // Not part of ParamBus/Scene (the Scene interface is unchanged, §6.2) —
  // fed straight into MemoryFieldPass alongside fieldDecay/flowStrength/
  // symmetry, bypassing Scene like those three already do today.
  flowDirection: number // bipolar -1..1, biases the memory field's curl-noise drift axis
}

function num(v: unknown, fallback = 0): number {
  return typeof v === 'number' ? v : fallback
}

// Owns every piece of per-frame state the composites need (springs, hold
// timers, hue drift, drop-edge detection) — one instance per ScreenOutput,
// constructed once and updated every frame, exactly like the old
// Choreographer instance it replaces for these specific fields.
export class ScreenParamAssembler {
  private flowStrengthSpring = new SpringDamper(FLOW_STRENGTH_STIFFNESS, FLOW_STRENGTH_DAMPING, FLOW_STRENGTH_BASE)
  private symmetrySmooth = new DtSmoother(SYMMETRY_ATTACK_SEC, SYMMETRY_RELEASE_SEC)
  private flowDirectionSmooth = new DtSmoother(FLOW_DIRECTION_SMOOTH_SEC, FLOW_DIRECTION_SMOOTH_SEC)
  private symmetryHoldSec = 0
  private hue = 0
  private prevDropImpulse = 0

  update(dt: number, resolved: ResolvedTargets): AssembledScreenParams {
    const buildWindup = num(resolved['screen.buildWindup'])
    const buildProgress = num(resolved['screen.buildProgress'])
    const tension = num(resolved['screen.tension'])
    const suspension = num(resolved['screen.suspension'])
    const energy = num(resolved['screen.energy'])
    const flatness = num(resolved['screen.flatness'])
    const centroid = num(resolved['screen.centroid'])
    const pan = num(resolved['screen.pan'])
    const dropImpulse = num(resolved['screen.dropImpulse'])
    const beatPulse = num(resolved['screen.beatPulse'])
    const barPhase = num(resolved['screen.barPhase'])
    const bandTilt = num(resolved['screen.bandTilt'])
    const familiarity = num(resolved['screen.familiarity'])
    const bands = {
      sub: num(resolved['screen.sub']),
      low: num(resolved['screen.low']),
      mid: num(resolved['screen.mid']),
      presence: num(resolved['screen.presence']),
      air: num(resolved['screen.air']),
    }

    // Drop edge: dropImpulse is a continuous decaying pulse (SignalBus, R2 —
    // no pushed event reaches ScreenOutput), so "a drop just happened" is
    // reconstructed from a rise in that pulse rather than from a discrete
    // message, reproducing the old one-frame-true DropTrigger exactly.
    let dropTrigger: DropTrigger | null = null
    if (dropImpulse > this.prevDropImpulse + DROP_EDGE_EPS) {
      dropTrigger = { active: true, strength: dropImpulse, age: 0 }
      this.flowStrengthSpring.addImpulse(FLOW_SHOCKWAVE_IMPULSE * (0.5 + dropImpulse))
      this.symmetryHoldSec = SYMMETRY_DROP_HOLD_SEC
    }
    this.prevDropImpulse = dropImpulse

    this.hue = (this.hue + dt * HUE_DRIFT_PER_SEC) % 1
    const hueShift = (this.hue + centroid * 0.1) % 1
    const paletteMix = buildWindup

    const barBreath = Math.sin(barPhase * 2 * Math.PI) * BAR_BREATH_AMPLITUDE
    const fieldDecay = clamp(
      Math.max(
        FIELD_DECAY_GROOVE + (FIELD_DECAY_BUILD - FIELD_DECAY_GROOVE) * buildProgress,
        FIELD_DECAY_GROOVE + (FIELD_DECAY_BREAK_MAX - FIELD_DECAY_GROOVE) * suspension,
      ) + barBreath,
      0,
      0.999,
    )

    this.flowStrengthSpring.setTarget(
      FLOW_STRENGTH_BASE +
        FLOW_STRENGTH_BUILD_GAIN * Math.max(buildWindup, tension) +
        FLOW_STRENGTH_ENERGY_GAIN * energy +
        BEAT_THROB_GAIN * beatPulse,
    )
    const flowStrength = Math.max(0, this.flowStrengthSpring.update(dt))

    this.symmetryHoldSec = Math.max(0, this.symmetryHoldSec - dt)
    const flatnessBloom =
      flatness > FLATNESS_BLOOM_THRESHOLD
        ? ((flatness - FLATNESS_BLOOM_THRESHOLD) / (1 - FLATNESS_BLOOM_THRESHOLD)) * FLATNESS_BLOOM_GAIN
        : 0
    let symmetryTarget = clamp(
      tension * SYMMETRY_TENSION_GAIN +
        buildProgress * SYMMETRY_BUILD_GAIN +
        flatnessBloom +
        familiarity * FAMILIARITY_SYMMETRY_GAIN,
      SYMMETRY_FLOOR,
      SYMMETRY_AMBIENT_CEILING,
    )
    if (this.symmetryHoldSec > 0) symmetryTarget = 1
    const symmetry = clamp(this.symmetrySmooth.update(symmetryTarget, dt), SYMMETRY_FLOOR, 1)

    const flowDirection = clamp(this.flowDirectionSmooth.update(bandTilt, dt), -1, 1)

    return {
      beatPhase: num(resolved['screen.beatPhase']),
      barPhase,
      tempoBpm: num(resolved['screen.tempoBpm']),
      tempoConfidence: num(resolved['screen.tempoConfidence']),

      windup: buildWindup,
      buildProgress,
      tension,
      suspension,

      dropTrigger,

      bands,
      centroid,
      flatness,
      energy,
      pan,

      paletteMix,
      hueShift,

      fieldDecay,
      flowStrength,
      symmetry,

      scope: (resolved['screen.scope'] as Float32Array | null) ?? null,
      idle: Boolean(resolved['screen.idle']),

      flowDirection,
    }
  }
}
