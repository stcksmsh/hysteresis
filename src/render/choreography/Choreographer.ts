import { SpringDamper } from './spring-damper'
import type { StateFrame, ParamBus, DropTrigger, OnsetPulse } from '../../shared/types'

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

const RELEASE_IMPULSE = 8 // tuned by feel — how hard a drop "pops" the windup value
const BUILD_SMOOTH_SEC = 0.15
const TENSION_SMOOTH_SEC = 0.3
const SUSPENSION_ATTACK_SEC = 2.0 // slower than tension — "have we been held for a while", not "is it true right now"
const SUSPENSION_RELEASE_SEC = 3.0
const HUE_DRIFT_PER_SEC = 0.01

// Memory field (SINTEZA_VIZ.md §4b) — decay (ping-pong retention, 0..1):
// short memory at rest, long memory once a build is loading energy in, and
// a further push during a break/suspension so the last drop's trace lingers
// into the silence rather than fading with everything else.
const FIELD_DECAY_GROOVE = 0.86
const FIELD_DECAY_BUILD = 0.965
const FIELD_DECAY_BREAK_MAX = 0.985

// Flow strength is a multiplier on the memory field's own curl-noise
// advection (MemoryFieldPass), not a raw UV displacement — 1 is the groove
// baseline, climbing with tension/build ("processing" churns harder), with
// a spring impulse on drop for the "shockwave through the flow field".
const FLOW_STRENGTH_STIFFNESS = 40
const FLOW_STRENGTH_DAMPING = 9
const FLOW_STRENGTH_BASE = 1
const FLOW_STRENGTH_BUILD_GAIN = 2.2
const FLOW_SHOCKWAVE_IMPULSE = 30 // tuned by feel, mirrors RELEASE_IMPULSE's role for windup
// energy (RMS loudness) is the one signal continuously available for a
// track's *entire* runtime — buildProgress/tension only exist inside the
// sparse build/break spans the offline section-detector actually finds,
// which for a typical track is a small fraction of the total length. Without
// this, the field (and, below, the Julia scene's own sweep/zoom rate) sat at
// its resting churn for most of a song regardless of how loud/energetic it
// actually was — the real cause behind "doesn't work with the music enough".
const ENERGY_SMOOTH_SEC = 0.25
const FLOW_STRENGTH_ENERGY_GAIN = 0.9

// Earned symmetry (SINTEZA_VIZ.md §4d) — always a response, never a constant
// filter: rises with tension/build, blooms briefly on a sustained tonal
// passage (high spectral flatness), and snaps to 1 for roughly one bar on a
// drop before releasing. Attack is quick (it should read as triggered);
// release is slow enough to read as "for a bar", independent of tempo.
const SYMMETRY_ATTACK_SEC = 0.5
const SYMMETRY_RELEASE_SEC = 2.2
const SYMMETRY_TENSION_GAIN = 0.5
const SYMMETRY_BUILD_GAIN = 0.55
const FLATNESS_BLOOM_THRESHOLD = 0.75
const FLATNESS_BLOOM_GAIN = 0.6
// A single-frame target spike would only ever nudge the (0.5s-attack)
// smoother a fraction of the way toward 1 before reverting — nowhere near
// "for a bar". This holds the target at 1 for the duration instead, tempo-
// independent like SUSPENSION_ATTACK/RELEASE_SEC above.
const SYMMETRY_DROP_HOLD_SEC = 2.0

// Attack/release smoothing driven by an explicit per-call dt (real elapsed
// frame time), rather than the AudioWorklet's EnvelopeFollower which bakes
// in a fixed hop period — the Choreographer runs once per rendered frame,
// not once per fixed-size audio hop.
class DtSmoother {
  private value = 0
  private initialized = false

  constructor(
    private attackSec: number,
    private releaseSec: number,
  ) {}

  update(input: number, dt: number): number {
    if (!this.initialized) {
      this.value = input
      this.initialized = true
      return this.value
    }
    const tau = input > this.value ? this.attackSec : this.releaseSec
    const coeff = Math.exp(-dt / tau)
    this.value = coeff * this.value + (1 - coeff) * input
    return this.value
  }
}

// Reads StateFrame (Layer 2 output) only, never raw audio or Layer 1
// internals. Produces the ParamBus — the only thing scenes ever see.
export class Choreographer {
  private windupSpring = new SpringDamper(90, 10)
  private buildSmooth = new DtSmoother(BUILD_SMOOTH_SEC, BUILD_SMOOTH_SEC)
  private tensionSmooth = new DtSmoother(TENSION_SMOOTH_SEC, TENSION_SMOOTH_SEC)
  private suspensionEnv = new DtSmoother(SUSPENSION_ATTACK_SEC, SUSPENSION_RELEASE_SEC)
  private flowStrengthSpring = new SpringDamper(FLOW_STRENGTH_STIFFNESS, FLOW_STRENGTH_DAMPING, FLOW_STRENGTH_BASE)
  private symmetrySmooth = new DtSmoother(SYMMETRY_ATTACK_SEC, SYMMETRY_RELEASE_SEC)
  private energySmooth = new DtSmoother(ENERGY_SMOOTH_SEC, ENERGY_SMOOTH_SEC)
  private symmetryHoldSec = 0
  private hue = 0

  update(frame: StateFrame, dt: number): ParamBus {
    let dropTrigger: DropTrigger | null = null
    const onsetPulses: OnsetPulse[] = []

    this.symmetryHoldSec = Math.max(0, this.symmetryHoldSec - dt)

    for (const event of frame.events) {
      if (event.type === 'drop') {
        dropTrigger = { active: true, strength: event.strength, age: 0 }
        this.windupSpring.addImpulse(RELEASE_IMPULSE * (0.5 + event.strength))
        this.windupSpring.setTarget(0)
        this.flowStrengthSpring.addImpulse(FLOW_SHOCKWAVE_IMPULSE * (0.5 + event.strength))
        this.symmetryHoldSec = SYMMETRY_DROP_HOLD_SEC
      }
    }

    // Every band that moved becomes its own pulse, each carrying its own
    // stereo position — that is what spreads a dense arrangement across the
    // field instead of collapsing it onto one whole-mix position.
    for (const hit of frame.spectralHits) {
      onsetPulses.push({ strength: hit.strength, tone: hit.tone, pan: hit.pan })
    }

    this.windupSpring.setTarget(frame.buildProgress)
    const windup = this.windupSpring.update(dt)

    const buildProgress = this.buildSmooth.update(frame.buildProgress, dt)
    const tension = this.tensionSmooth.update(frame.tension, dt)
    const suspension = this.suspensionEnv.update(frame.tension, dt)
    const energy = clamp(this.energySmooth.update(frame.energy, dt), 0, 1)

    this.hue = (this.hue + dt * HUE_DRIFT_PER_SEC) % 1
    const hueShift = (this.hue + frame.centroid * 0.1) % 1
    const paletteMix = windup

    // Memory field decay: short at rest, long once a build is loading
    // energy in, pushed further still by a break/suspension so the last
    // drop's trace lingers into the silence instead of fading with
    // everything else (SINTEZA_VIZ.md §3a "Break").
    const fieldDecay = Math.max(
      FIELD_DECAY_GROOVE + (FIELD_DECAY_BUILD - FIELD_DECAY_GROOVE) * buildProgress,
      FIELD_DECAY_GROOVE + (FIELD_DECAY_BREAK_MAX - FIELD_DECAY_GROOVE) * suspension,
    )

    this.flowStrengthSpring.setTarget(
      FLOW_STRENGTH_BASE + FLOW_STRENGTH_BUILD_GAIN * Math.max(windup, tension) + FLOW_STRENGTH_ENERGY_GAIN * energy,
    )
    const flowStrength = Math.max(0, this.flowStrengthSpring.update(dt))

    const flatnessBloom =
      frame.flatness > FLATNESS_BLOOM_THRESHOLD
        ? ((frame.flatness - FLATNESS_BLOOM_THRESHOLD) / (1 - FLATNESS_BLOOM_THRESHOLD)) * FLATNESS_BLOOM_GAIN
        : 0
    let symmetryTarget = clamp(tension * SYMMETRY_TENSION_GAIN + buildProgress * SYMMETRY_BUILD_GAIN + flatnessBloom, 0, 1)
    if (this.symmetryHoldSec > 0) symmetryTarget = 1
    const symmetry = clamp(this.symmetrySmooth.update(symmetryTarget, dt), 0, 1)

    return {
      beatPhase: frame.beatPhase,
      barPhase: frame.barPhase,
      tempoBpm: frame.tempo,
      tempoConfidence: frame.tempoConfidence,

      windup,
      buildProgress,
      tension,
      suspension,

      dropTrigger,
      onsetPulses,

      bands: frame.bandsRaw,
      centroid: frame.centroid,
      flatness: frame.flatness,
      energy,
      pan: frame.pan,

      paletteMix,
      hueShift,

      fieldDecay,
      flowStrength,
      symmetry,

      scope: frame.scope,
      idle: frame.idle ?? false,
    }
  }
}
