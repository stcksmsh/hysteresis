import { EnvelopeFollower } from '../envelope'

// AGENTS.md §4.2/§4.5 step 3 — fullness and onset-density were previously
// computed only inside DropDetector's own internals (see drop-detector.ts's
// header for the full rationale: "the mix going sparse to full", not "the
// mix getting louder"). Extracted here so feature-worklet.ts can expose them
// as always-alive, generally-routable bus signals (not just a detector's
// private arming primitive) — DropDetector keeps its own separate instance
// of each (same "separate instance per consumer" precedent novelty.ts's
// header already documents for NoveltyRingBuffer/familiarity.ts, since the
// two run at different cadences/lifecycles and DropDetector's is gated by
// `detectorsEnabled` while the bus-level one must not be).

const FAST_MS = 80
const SUSTAIN_MS = 1800 // "much longer than the old 300ms" — the actual fix for the loud-build-miss case
const SLOW_MS = 3000 // deliberately slower than SUSTAIN_MS — lags behind, giving a real pre-jump baseline
const CREST_FAST_MS = 60
const CREST_PENALTY_GAIN = 0.6

const ONSET_RATE_MS = 1500
const ONSET_BASELINE_MS = 4000
const ONSET_ACTIVITY_SCALE = 3 // onset activity is normally small/sparse; amplify before comparing

export interface FullnessResult {
  fullness: number // 0..1, sustained energy, crest-penalized
  slow: number // the slow-envelope baseline (DropDetector uses this as its armedBaseline)
}

export class FullnessTracker {
  private fastEnergy: EnvelopeFollower
  private sustainedEnergy: EnvelopeFollower
  private slowEnergy: EnvelopeFollower
  private crestPeak: EnvelopeFollower

  constructor(hopMs: number) {
    this.fastEnergy = new EnvelopeFollower(FAST_MS, FAST_MS, hopMs)
    this.sustainedEnergy = new EnvelopeFollower(SUSTAIN_MS, SUSTAIN_MS, hopMs)
    this.slowEnergy = new EnvelopeFollower(SLOW_MS, SLOW_MS, hopMs)
    this.crestPeak = new EnvelopeFollower(CREST_FAST_MS, CREST_FAST_MS, hopMs)
  }

  update(lowEnergy: number): FullnessResult {
    const fast = this.fastEnergy.update(lowEnergy)
    const sustained = this.sustainedEnergy.update(lowEnergy)
    const slow = this.slowEnergy.update(lowEnergy)
    const peak = this.crestPeak.update(fast)
    // crest ~= 1 when the signal is steady; it strays from 1 right after a
    // spike (fast momentarily above/below its own recent peak) — a pulsing
    // source (reverb tail between hits) keeps producing this, a
    // continuously full signal doesn't.
    const crest = peak > 1e-6 ? fast / peak : 1
    const crestPenalty = Math.min(1, Math.abs(crest - 1) * CREST_PENALTY_GAIN)
    const fullness = Math.max(0, sustained * (1 - crestPenalty))
    return { fullness, slow }
  }
}

export class OnsetDensityTracker {
  private onsetRate: EnvelopeFollower
  private onsetBaseline: EnvelopeFollower

  constructor(hopMs: number) {
    this.onsetRate = new EnvelopeFollower(ONSET_RATE_MS, ONSET_RATE_MS, hopMs)
    this.onsetBaseline = new EnvelopeFollower(ONSET_BASELINE_MS, ONSET_BASELINE_MS, hopMs)
  }

  // `jump` is DropDetector's arming primitive (rate minus baseline);
  // `rate` alone (scaled) is what's actually exposed on the bus as
  // `onsetDensity` — a continuous "how busy is the rhythm right now"
  // reading, not just the jump.
  update(onsetActivity: number): { rate: number; jump: number } {
    const rate = this.onsetRate.update(onsetActivity)
    const baseline = this.onsetBaseline.update(onsetActivity)
    const jump = rate * ONSET_ACTIVITY_SCALE - baseline * ONSET_ACTIVITY_SCALE
    return { rate: rate * ONSET_ACTIVITY_SCALE, jump }
  }
}
