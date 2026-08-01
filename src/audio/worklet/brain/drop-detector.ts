import { EnvelopeFollower } from '../envelope'

const FAST_MS = 80
const SLOW_MS = 2500
const JUMP_THRESHOLD = 0.22
const JUMP_STRENGTH_NORMALIZER = 0.6

// A drop is the *resolution of a thinned section*, not just a loud moment.
// Credit accrues only while the track is genuinely thinned/tense, decays
// otherwise, and must exceed THINNED_CREDIT_REQUIRED_SEC for a jump to
// qualify at all. A steady groove never accrues credit, so no kick inside
// one can ever read as a drop — this is the main false-positive gate.
const TENSION_FOR_THINNED = 0.2
const THINNED_CREDIT_REQUIRED_SEC = 0.8

// Second qualifying path. Band energies are adaptively normalised, so a
// breakdown does not always register as "thinned" in normalised terms and
// the credit gate alone can reject genuine drops. A jump this large is
// unambiguous on its own: inside a steady groove the slow envelope is
// already high, so kicks can never produce a gap of this size.
const STRONG_JUMP_THRESHOLD = 0.5
const THINNED_CREDIT_MAX_SEC = 6
const THINNED_CREDIT_DECAY_RATE = 0.5 // credit lost per second while not thinned

// A kick spikes and decays within ~150ms; a drop sustains. Requiring the
// elevated level to hold for a confirmation window is what separates them.
const CONFIRM_WINDOW_SEC = 0.3
// Confirmation measures *what fraction of the window stays elevated*, not an
// envelope level. Level-based checks can't separate the two cases: the 80ms
// envelope collapses between kicks (a 120bpm gap is as long as the window,
// so real drops get disarmed), while a slow-release envelope props up a lone
// spike long enough to pass. Occupancy separates them cleanly — a drop holds
// energy up across most of the window, a percussive hit only briefly.
const CONFIRM_ELEVATED_FRACTION = 0.4
const ELEVATED_MARGIN = JUMP_THRESHOLD * 0.5

// The confirm window is already ~1 beat, so waiting for the *next* beat
// boundary would stack latency on top of it. Only wait if one is imminent.
const BEAT_SNAP_LOOKAHEAD_SEC = 0.15

const REFRACTORY_SEC = 8.0

export interface DropEvent {
  strength: number
  t: number
}

export class DropDetector {
  private fastEnergy: EnvelopeFollower
  private slowEnergy: EnvelopeFollower
  private refractoryUntil = 0
  private thinnedCreditSec = 0
  private armedAt: number | null = null
  private armedPeakJump = 0
  private armedBaseline = 0
  private elevatedHops = 0
  private windowHops = 0
  private hopSec: number

  constructor(hopMs: number) {
    this.fastEnergy = new EnvelopeFollower(FAST_MS, FAST_MS, hopMs)
    this.slowEnergy = new EnvelopeFollower(SLOW_MS, SLOW_MS, hopMs)
    this.hopSec = hopMs / 1000
  }

  update(lowEnergy: number, tension: number, beatPhase: number, tempoBpm: number, tNow: number): DropEvent | null {
    const fast = this.fastEnergy.update(lowEnergy)
    const slow = this.slowEnergy.update(lowEnergy)

    this.updateThinnedCredit(tension)

    if (tNow < this.refractoryUntil) {
      this.disarm()
      return null
    }

    const jump = fast - slow

    if (this.armedAt === null) {
      const structural = jump > JUMP_THRESHOLD && this.thinnedCreditSec >= THINNED_CREDIT_REQUIRED_SEC
      const unambiguous = jump > STRONG_JUMP_THRESHOLD
      const qualifies = structural || unambiguous
      if (qualifies) {
        this.armedAt = tNow
        this.armedPeakJump = jump
        this.armedBaseline = slow
        this.elevatedHops = 0
        this.windowHops = 0
      }
      return null
    }

    this.armedPeakJump = Math.max(this.armedPeakJump, jump)
    this.windowHops++
    if (lowEnergy > this.armedBaseline + ELEVATED_MARGIN) this.elevatedHops++

    if (tNow - this.armedAt < CONFIRM_WINDOW_SEC) return null

    // Occupancy check: a drop keeps energy up across the window; a lone
    // percussive hit only spikes briefly.
    if (this.elevatedHops / Math.max(1, this.windowHops) < CONFIRM_ELEVATED_FRACTION) {
      this.disarm()
      return null
    }

    // Confirmed. Hold briefly only if a beat boundary is imminent.
    if (tempoBpm > 0) {
      const beatPeriodSec = 60 / tempoBpm
      const secToNextBeat = (1 - beatPhase) * beatPeriodSec
      if (secToNextBeat > this.hopSec && secToNextBeat <= BEAT_SNAP_LOOKAHEAD_SEC) return null
    }

    const strength = Math.max(0, Math.min(1, this.armedPeakJump / JUMP_STRENGTH_NORMALIZER))
    this.disarm()
    this.thinnedCreditSec = 0
    this.refractoryUntil = tNow + REFRACTORY_SEC
    return { strength, t: tNow }
  }

  private updateThinnedCredit(tension: number): void {
    if (tension >= TENSION_FOR_THINNED) {
      this.thinnedCreditSec = Math.min(THINNED_CREDIT_MAX_SEC, this.thinnedCreditSec + this.hopSec)
    } else {
      this.thinnedCreditSec = Math.max(0, this.thinnedCreditSec - this.hopSec * THINNED_CREDIT_DECAY_RATE)
    }
  }

  private disarm(): void {
    this.armedAt = null
    this.armedPeakJump = 0
  }
}
