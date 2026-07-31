import { EnvelopeFollower } from '../envelope'

const FAST_MS = 80
const SLOW_MS = 2500
const THINNED_BASELINE_THRESHOLD = 0.45 // slow baseline must be below this — a jump from an already-loud section isn't "a drop"
const JUMP_THRESHOLD = 0.25
const JUMP_STRENGTH_NORMALIZER = 0.6
const BEAT_SNAP_WINDOW = 0.08 // beatPhase distance from 0/1 counted as "on the beat"
const BEAT_SNAP_TIMEOUT_SEC = 1.0 // if no clean beat boundary arrives in time, fire anyway rather than never
const REFRACTORY_SEC = 3.0

export interface DropEvent {
  strength: number
  t: number
}

// A drop is a broadband energy jump *after a thinned section*, snapped to a
// downbeat — not just "a loud frame". Firing is deferred to the next beat
// boundary once the jump condition holds, so the visual release lands on
// the beat instead of mid-note.
export class DropDetector {
  private fastEnergy: EnvelopeFollower
  private slowEnergy: EnvelopeFollower
  private refractoryUntil = 0
  private pendingSince: number | null = null
  private pendingPeakJump = 0

  constructor(hopMs: number) {
    this.fastEnergy = new EnvelopeFollower(FAST_MS, FAST_MS, hopMs)
    this.slowEnergy = new EnvelopeFollower(SLOW_MS, SLOW_MS, hopMs)
  }

  update(broadbandEnergy: number, beatPhase: number, tNow: number): DropEvent | null {
    const fast = this.fastEnergy.update(broadbandEnergy)
    const slow = this.slowEnergy.update(broadbandEnergy)

    if (tNow < this.refractoryUntil) {
      this.pendingSince = null
      return null
    }

    const jump = fast - slow
    const jumpCondition = jump > JUMP_THRESHOLD && slow < THINNED_BASELINE_THRESHOLD

    // A percussive jump is a brief transient (fast decays back down within
    // ~100ms) — once armed, keep waiting for the beat snap/timeout rather
    // than disarming the instant the momentary condition clears, or a real
    // drop would almost never survive long enough to actually fire.
    if (jumpCondition) {
      if (this.pendingSince === null) this.pendingSince = tNow
      this.pendingPeakJump = Math.max(this.pendingPeakJump, jump)
    }

    if (this.pendingSince === null) return null

    const nearBeat = beatPhase < BEAT_SNAP_WINDOW || beatPhase > 1 - BEAT_SNAP_WINDOW
    const timedOut = tNow - this.pendingSince > BEAT_SNAP_TIMEOUT_SEC
    if (!nearBeat && !timedOut) return null

    const strength = Math.max(0, Math.min(1, this.pendingPeakJump / JUMP_STRENGTH_NORMALIZER))
    this.pendingSince = null
    this.pendingPeakJump = 0
    this.refractoryUntil = tNow + REFRACTORY_SEC
    return { strength, t: tNow }
  }
}
