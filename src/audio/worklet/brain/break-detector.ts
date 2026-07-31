import { EnvelopeFollower } from '../envelope'
import type { StructuralEvent } from '../../../shared/types'

const LOW_ENERGY_MS = 2000
const ONSET_ACTIVITY_MS = 1500
const TENSION_ATTACK_MS = 500
const TENSION_RELEASE_MS = 1200
const ONSET_ACTIVITY_SCALE = 3 // novelty is normally small/sparse; amplify before treating it as "activity"
const BREAK_ENTER_THRESHOLD = 0.4
const BREAK_EXIT_THRESHOLD = 0.25 // hysteresis band around ENTER, avoids chattering at the boundary

export interface BreakDetectorOutput {
  tension: number
  event: StructuralEvent | null
}

// A break is tension, not silence: sub collapsing + onsets stopping. tension
// rises smoothly as both conditions persist and relaxes once either returns,
// with hysteresis around the breakStart/breakEnd transition so it doesn't
// chatter right at the threshold.
export class BreakDetector {
  private lowEnergySlow: EnvelopeFollower
  private onsetActivitySlow: EnvelopeFollower
  private tensionEnv: EnvelopeFollower
  private inBreak = false

  constructor(hopMs: number) {
    this.lowEnergySlow = new EnvelopeFollower(LOW_ENERGY_MS, LOW_ENERGY_MS, hopMs)
    this.onsetActivitySlow = new EnvelopeFollower(ONSET_ACTIVITY_MS, ONSET_ACTIVITY_MS, hopMs)
    this.tensionEnv = new EnvelopeFollower(TENSION_ATTACK_MS, TENSION_RELEASE_MS, hopMs)
  }

  update(lowEnergy: number, novelty: number, tNow: number): BreakDetectorOutput {
    const low = this.lowEnergySlow.update(lowEnergy)
    const onsetActivity = this.onsetActivitySlow.update(novelty)
    const rawTension = (1 - low) * (1 - Math.min(1, onsetActivity * ONSET_ACTIVITY_SCALE))
    const tension = this.tensionEnv.update(Math.max(0, rawTension))

    let event: StructuralEvent | null = null
    if (!this.inBreak && tension > BREAK_ENTER_THRESHOLD) {
      this.inBreak = true
      event = { type: 'breakStart', strength: tension, t: tNow }
    } else if (this.inBreak && tension < BREAK_EXIT_THRESHOLD) {
      this.inBreak = false
      event = { type: 'breakEnd', strength: 1 - tension, t: tNow }
    }

    return { tension, event }
  }
}
