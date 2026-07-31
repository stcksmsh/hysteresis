import { EnvelopeFollower } from '../envelope'

const FAST_MS = 600
const SLOW_MS = 6000
const INTEGRATION_GAIN = 0.06 // how fast sustained rise winds buildProgress up
const DECAY_PER_HOP = 0.0015 // constant relaxation so progress doesn't stick at 1 forever

// A build is a *trend*, not a level: sustained rising centroid ("filter
// opening") + rising sub, tracked as fast-vs-slow moving-average spread.
// buildProgress integrates that rise over time (winds up in anticipation)
// rather than reading the instantaneous rise rate directly — per the core
// thesis, direct feature reads twitch, driven/integrated signals feel alive.
export class BuildDetector {
  private centroidFast: EnvelopeFollower
  private centroidSlow: EnvelopeFollower
  private subFast: EnvelopeFollower
  private subSlow: EnvelopeFollower
  private progress = 0

  constructor(hopMs: number) {
    this.centroidFast = new EnvelopeFollower(FAST_MS, FAST_MS, hopMs)
    this.centroidSlow = new EnvelopeFollower(SLOW_MS, SLOW_MS, hopMs)
    this.subFast = new EnvelopeFollower(FAST_MS, FAST_MS, hopMs)
    this.subSlow = new EnvelopeFollower(SLOW_MS, SLOW_MS, hopMs)
  }

  update(centroid: number, sub: number): number {
    const centroidRise = Math.max(0, this.centroidFast.update(centroid) - this.centroidSlow.update(centroid))
    const subRise = Math.max(0, this.subFast.update(sub) - this.subSlow.update(sub))
    const rise = (centroidRise + subRise) / 2

    this.progress += rise * INTEGRATION_GAIN - DECAY_PER_HOP
    this.progress = Math.max(0, Math.min(1, this.progress))
    return this.progress
  }

  // Called by the drop detector at the moment a drop fires, so the release
  // is immediate rather than only a slow decay.
  reset(): void {
    this.progress = 0
  }
}
