import { EnvelopeFollower } from '../envelope'
import { NoveltyRingBuffer } from './novelty'

// SINTEZA_SIGNAL_BUS.md §4b(2) — a drop is "the mix going from sparse to
// full", not "the mix getting louder". The old primitive (fast-minus-slow
// energy jump) can't tell those apart: a pulsing reverb synth over a sparse
// ambient intro produces the same kind of energy-difference spike a real
// drop does (false positive), and a drop following an already-loud
// wall-of-noise build produces *no* jump at all (miss). This replaces it
// with a conjunction of three signals that each measure something a loud-
// but-not-full moment can't fake:
//
// - fullness: energy sustained *continuously* over a multi-second window,
//   with a high crest factor (spiky, not sustained — a reverb tail pulsing
//   between hits) penalized.
// - onset-density jump: rhythmic events/sec rising — a drop introduces or
//   intensifies rhythm; a metronomic sparse intro never changes its density.
// - novelty contrast: the current feature vector reading as dissimilar from
//   the recent past (the same self-similarity math as `familiarity`,
//   SINTEZA_SIGNAL_BUS.md §4.2 — see novelty.ts's header for why this is a
//   second independent instance, not a shared one).
//
// Confirmation (sustained occupancy over a window), refractory, startup
// grace, and beat-snap-lookahead are unchanged from the old detector — only
// the arming primitive changed.
const FAST_MS = 80
const SUSTAIN_MS = 1800 // "much longer than the current 300ms" — this is the actual fix for the miss case
const SLOW_MS = 3000 // deliberately slower than SUSTAIN_MS — lags behind at arm time, giving the confirmation step a real pre-jump baseline to compare against
const CREST_FAST_MS = 60
const CREST_PENALTY_GAIN = 0.6
const FULLNESS_THRESHOLD = 0.5

const ONSET_RATE_MS = 1500
const ONSET_BASELINE_MS = 4000
const ONSET_ACTIVITY_SCALE = 3 // onset activity is normally small/sparse; amplify before comparing (mirrors BreakDetector's own onsetActivitySlow scaling)
// A jump right after track start (near-zero baseline) reads larger than one
// a few seconds after a shorter thinned section, where the slower baseline
// envelope still carries some memory of the section before that — kept
// modest so both still qualify.
const ONSET_JUMP_MIN = 0.06

// Independent of familiarity's own ~12s window (§4.2) — a shorter recent-
// past window on purpose, so a brief thinned section (a few seconds) fully
// displaces the buffer instead of leaving stale full-mix samples in it that
// would suppress novelty at the next transition.
const NOVELTY_WINDOW_SEC = 4
const NOVELTY_THRESHOLD = 0.3 // 1 - max cosine similarity against the recent buffer
// Novelty spikes the instant material changes, then decays fast as the
// buffer re-fills with the new (now-familiar-to-itself) material — but
// fullness/onset-density take ~1-2s to ramp up and confirm a sustained
// change. Held for a few seconds so it's still "hot" once they catch up,
// instead of requiring all three signals to cross their thresholds on the
// exact same hop.
const NOVELTY_HOLD_SEC = 3.0

const CONFIRM_WINDOW_SEC = 0.3
const CONFIRM_ELEVATED_FRACTION = 0.5
const ELEVATED_MARGIN = 0.08

const BEAT_SNAP_LOOKAHEAD_SEC = 0.15
const REFRACTORY_SEC = 8.0
const STARTUP_GRACE_SEC = 4.0

export interface DropEvent {
  strength: number
  t: number
}

// `vec` is a feature vector for the novelty-contrast term — same shape as
// familiarity's (bands + centroid + flatness), not required to be identical
// length/order to any other consumer's, just internally consistent frame to
// frame. `onsetActivity` is the continuous per-hop onset/flux strength
// (e.g. feature-worklet.ts's `novelty`), not a thresholded boolean — a
// rate estimate needs real amplitude to track, the same reason
// BreakDetector smooths continuous novelty rather than a threshold flag.
export interface DropDetectorFeatures {
  lowEnergy: number
  onsetActivity: number
  vec: readonly number[]
}

export class DropDetector {
  private fastEnergy: EnvelopeFollower
  private sustainedEnergy: EnvelopeFollower
  private slowEnergy: EnvelopeFollower
  private crestPeak: EnvelopeFollower
  private onsetRate: EnvelopeFollower
  private onsetBaseline: EnvelopeFollower
  private novelty: NoveltyRingBuffer
  private noveltyPeak = 0

  private refractoryUntil = 0
  private armedAt: number | null = null
  private armedBaseline = 0
  private armedPeakFullness = 0
  private elevatedHops = 0
  private windowHops = 0
  private hopSec: number
  private startedAt: number | null = null

  constructor(hopMs: number) {
    this.fastEnergy = new EnvelopeFollower(FAST_MS, FAST_MS, hopMs)
    this.sustainedEnergy = new EnvelopeFollower(SUSTAIN_MS, SUSTAIN_MS, hopMs)
    this.slowEnergy = new EnvelopeFollower(SLOW_MS, SLOW_MS, hopMs)
    this.crestPeak = new EnvelopeFollower(CREST_FAST_MS, CREST_FAST_MS, hopMs)
    this.onsetRate = new EnvelopeFollower(ONSET_RATE_MS, ONSET_RATE_MS, hopMs)
    this.onsetBaseline = new EnvelopeFollower(ONSET_BASELINE_MS, ONSET_BASELINE_MS, hopMs)
    this.novelty = new NoveltyRingBuffer(Math.max(1, Math.round((NOVELTY_WINDOW_SEC * 1000) / hopMs)))
    this.hopSec = hopMs / 1000
  }

  update(features: DropDetectorFeatures, beatPhase: number, tempoBpm: number, tNow: number): DropEvent | null {
    if (this.startedAt === null) this.startedAt = tNow

    const fast = this.fastEnergy.update(features.lowEnergy)
    const sustained = this.sustainedEnergy.update(features.lowEnergy)
    const slow = this.slowEnergy.update(features.lowEnergy)
    const peak = this.crestPeak.update(fast)
    // crest ~= 1 when the signal is steady; it strays from 1 right after a
    // spike (fast momentarily above/below its own recent peak) — a pulsing
    // source (reverb tail between hits) keeps producing this, a
    // continuously full signal doesn't.
    const crest = peak > 1e-6 ? fast / peak : 1
    const crestPenalty = Math.min(1, Math.abs(crest - 1) * CREST_PENALTY_GAIN)
    const fullness = Math.max(0, sustained * (1 - crestPenalty))

    const onsetRate = this.onsetRate.update(features.onsetActivity)
    const onsetBaseline = this.onsetBaseline.update(features.onsetActivity)
    const onsetJump = onsetRate * ONSET_ACTIVITY_SCALE - onsetBaseline * ONSET_ACTIVITY_SCALE

    const noveltyValue = 1 - this.novelty.maxSimilarity(features.vec)
    this.novelty.push(features.vec)
    this.noveltyPeak = Math.max(noveltyValue, this.noveltyPeak * Math.exp(-this.hopSec / NOVELTY_HOLD_SEC))

    if (tNow - this.startedAt < STARTUP_GRACE_SEC || tNow < this.refractoryUntil) {
      this.disarm()
      return null
    }

    if (this.armedAt === null) {
      const qualifies = fullness > FULLNESS_THRESHOLD && onsetJump > ONSET_JUMP_MIN && this.noveltyPeak > NOVELTY_THRESHOLD
      if (qualifies) {
        this.armedAt = tNow
        this.armedBaseline = slow
        this.armedPeakFullness = fullness
        this.elevatedHops = 0
        this.windowHops = 0
      }
      return null
    }

    this.armedPeakFullness = Math.max(this.armedPeakFullness, fullness)
    this.windowHops++
    if (features.lowEnergy > this.armedBaseline + ELEVATED_MARGIN) this.elevatedHops++

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

    const strength = Math.max(0, Math.min(1, this.armedPeakFullness))
    this.disarm()
    this.refractoryUntil = tNow + REFRACTORY_SEC
    return { strength, t: tNow }
  }

  private disarm(): void {
    this.armedAt = null
    this.armedPeakFullness = 0
  }
}
