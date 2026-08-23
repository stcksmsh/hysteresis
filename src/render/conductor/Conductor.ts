// R1 (SINTEZA_SIGNAL_BUS.md): this module and familiarity.ts must import
// nothing output-shaped — no gl/canvas/Scene/WebGL/servo/Serial/port. Grep
// test: `grep -E 'gl|canvas|Scene|WebGL|servo|Serial|port' Conductor.ts
// familiarity.ts` must return nothing. The Conductor knows StateFrame in,
// SignalBus out — never what consumes the bus.
import { SpringDamper } from '../choreography/spring-damper'
import { DtSmoother } from './dt-smoother'
import { computeFamiliarity, FamiliarityTracker } from './familiarity'
import type { DropTrigger, StateFrame } from '../../shared/types'
import type { SignalBus } from './types'

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

const RELEASE_IMPULSE = 8 // tuned by feel — how hard a drop "pops" the windup value
const BUILD_SMOOTH_SEC = 0.15
const TENSION_SMOOTH_SEC = 0.3
const SUSPENSION_ATTACK_SEC = 2.0 // slower than tension — "have we been held for a while", not "is it true right now"
const SUSPENSION_RELEASE_SEC = 3.0
const ENERGY_SMOOTH_SEC = 0.25
const HUE_DRIFT_PER_SEC = 0.01 // was screen-composites.ts-internal — see SignalBus.hueDrift's doc comment

// dropImpulse (SINTEZA_SIGNAL_BUS.md §3.1): a continuous, decaying view of
// the discrete drop event, alive on the bus every frame (0 most of the
// time) instead of a one-frame-true flag — so a pull-model output can
// edge-detect "a drop just happened" from bus data alone (R2) without the
// Conductor pushing an event at it. Decays fast (transient tag): a few
// hundred ms, not the multi-second field-decay timescale.
const DROP_IMPULSE_DECAY_SEC = 0.4
const ONSET_IMPULSE_DECAY_SEC = 0.15
const BEAT_PULSE_DECAY_SEC = 0.18
const DOWNBEAT_PULSE_DECAY_SEC = 0.25

// bandTilt: cheap derived spectral-balance signal (SINTEZA_SIGNAL_BUS.md
// §3.1) — how much of the mix's energy sits in the high bands (presence air)
// vs the low bands (sub low), bipolar. mid is deliberately excluded from
// both sides so it doesn't cancel itself out of the comparison.
function computeBandTilt(sub: number, low: number, presence: number, air: number): number {
  const lowEnergy = sub + low
  const highEnergy = presence + air
  const total = lowEnergy + highEnergy + 1e-6
  return clamp((highEnergy - lowEnergy) / total, -1, 1)
}

// The Conductor (renamed/widened Choreographer, SINTEZA_SIGNAL_BUS.md §1-4):
// reads StateFrame (Layer 2 output) only, never raw audio or Layer 1
// internals, and produces the Signal Bus — the one thing downstream
// (Patchbay -> Outputs) ever reads. Owns every spring/envelope that shapes a
// bus signal into something "lightly-smoothed, honest" (§4.3); anything more
// output-specific belongs downstream in a patchbay route or in the output
// itself, never here.
export class Conductor {
  private windupSpring = new SpringDamper(90, 10)
  private buildSmooth = new DtSmoother(BUILD_SMOOTH_SEC, BUILD_SMOOTH_SEC)
  private tensionSmooth = new DtSmoother(TENSION_SMOOTH_SEC, TENSION_SMOOTH_SEC)
  private suspensionEnv = new DtSmoother(SUSPENSION_ATTACK_SEC, SUSPENSION_RELEASE_SEC)
  private energySmooth = new DtSmoother(ENERGY_SMOOTH_SEC, ENERGY_SMOOTH_SEC)

  private dropImpulseValue = 0
  private onsetImpulseValue = 0
  private beatPulseValue = 0
  private downbeatPulseValue = 0
  private lastBeatPhase = 0

  private familiarityTracker = new FamiliarityTracker()
  private hueDrift = 0

  update(frame: StateFrame, dt: number): SignalBus {
    let dropTrigger: DropTrigger | null = null

    // Beat/downbeat pulses: a decaying pulse re-triggered on each boundary
    // crossing — survives silence because beatPhase/barPhase free-run off
    // the PLL/BarTracker regardless of section detection (§4.1's "carriers").
    this.beatPulseValue *= Math.exp(-dt / BEAT_PULSE_DECAY_SEC)
    if (frame.beatPhase < this.lastBeatPhase - 0.5) this.beatPulseValue = 1
    this.lastBeatPhase = frame.beatPhase
    this.downbeatPulseValue *= Math.exp(-dt / DOWNBEAT_PULSE_DECAY_SEC)

    this.dropImpulseValue *= Math.exp(-dt / DROP_IMPULSE_DECAY_SEC)
    this.onsetImpulseValue *= Math.exp(-dt / ONSET_IMPULSE_DECAY_SEC)

    for (const event of frame.events) {
      if (event.type === 'drop') {
        dropTrigger = { active: true, strength: event.strength, age: 0 }
        this.windupSpring.addImpulse(RELEASE_IMPULSE * (0.5 + event.strength))
        this.dropImpulseValue = Math.max(this.dropImpulseValue, event.strength)
      } else if (event.type === 'onset') {
        this.onsetImpulseValue = Math.max(this.onsetImpulseValue, event.strength)
      } else if (event.type === 'downbeat') {
        this.downbeatPulseValue = Math.max(this.downbeatPulseValue, event.strength)
      }
    }

    this.windupSpring.setTarget(frame.buildProgress)
    const buildWindup = this.windupSpring.update(dt)

    const buildProgress = this.buildSmooth.update(frame.buildProgress, dt)
    const tension = this.tensionSmooth.update(frame.tension, dt)
    const suspension = this.suspensionEnv.update(frame.tension, dt)
    const energy = clamp(this.energySmooth.update(frame.energy, dt), 0, 1)

    const { sub, low, mid, presence, air } = frame.bandsRaw
    const bandTilt = computeBandTilt(sub, low, presence, air)

    const familiarity = computeFamiliarity(this.familiarityTracker, frame, dt)

    this.hueDrift = (this.hueDrift + dt * HUE_DRIFT_PER_SEC) % 1

    return {
      energy,
      sub,
      low,
      mid,
      presence,
      air,
      bandTilt,
      centroid: frame.centroid,
      flatness: frame.flatness,
      pan: frame.pan,
      familiarity,
      hueDrift: this.hueDrift,

      beatPhase: frame.beatPhase,
      beatPulse: this.beatPulseValue,

      barPhase: frame.barPhase,
      downbeatPulse: this.downbeatPulseValue,

      buildWindup,
      buildProgress,
      tension,
      suspension,

      dropImpulse: this.dropImpulseValue,
      onsetImpulse: this.onsetImpulseValue,
      dropTrigger,

      scope: frame.scope,

      idle: frame.idle ?? false,
      tempoBpm: frame.tempo,
      tempoConfidence: frame.tempoConfidence,
    }
  }
}
