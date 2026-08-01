import { SpringDamper } from './spring-damper'
import type { StateFrame, ParamBus, DropTrigger, OnsetPulse } from '../../shared/types'

const RELEASE_IMPULSE = 8 // tuned by feel — how hard a drop "pops" the windup value
const BUILD_SMOOTH_SEC = 0.15
const TENSION_SMOOTH_SEC = 0.3
const SUSPENSION_ATTACK_SEC = 2.0 // slower than tension — "have we been held for a while", not "is it true right now"
const SUSPENSION_RELEASE_SEC = 3.0
const HUE_DRIFT_PER_SEC = 0.01

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
  private hue = 0

  update(frame: StateFrame, dt: number): ParamBus {
    let dropTrigger: DropTrigger | null = null
    const onsetPulses: OnsetPulse[] = []

    for (const event of frame.events) {
      if (event.type === 'drop') {
        dropTrigger = { active: true, strength: event.strength, age: 0 }
        this.windupSpring.addImpulse(RELEASE_IMPULSE * (0.5 + event.strength))
        this.windupSpring.setTarget(0)
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

    this.hue = (this.hue + dt * HUE_DRIFT_PER_SEC) % 1
    const hueShift = (this.hue + frame.centroid * 0.1) % 1
    const paletteMix = windup

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
      energy: frame.energy,
      pan: frame.pan,

      paletteMix,
      hueShift,
    }
  }
}
