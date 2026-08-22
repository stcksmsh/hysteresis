import { describe, it, expect } from 'vitest'
import { DropDetector, type DropDetectorFeatures } from '../../src/audio/worklet/brain/drop-detector'
import { HOP_SIZE } from '../../src/shared/constants'

const SAMPLE_RATE = 48000
const HOP_MS = (HOP_SIZE / SAMPLE_RATE) * 1000
const HOP_SEC = HOP_MS / 1000
const TEMPO = 120

// Feature vectors deliberately dissimilar (SINTEZA_SIGNAL_BUS.md §4b(2)'s
// novelty-contrast term needs a real transition to detect) — QUIET reads as
// a sparse/dim mix, LOUD as a full, brighter one.
const QUIET_VEC = [0.05, 0.05, 0.05, 0.05, 0.05, 0.3, 0.5]
const LOUD_VEC = [0.9, 0.9, 0.5, 0.4, 0.3, 0.5, 0.3]

// Drives the detector across a synthetic timeline and returns every drop
// emitted. beatPhase advances on a real 120bpm grid so the beat-snap path is
// exercised the same way it is in the worklet.
function run(steps: (t: number) => DropDetectorFeatures, durationSec: number): number[] {
  const detector = new DropDetector(HOP_MS)
  const beatPeriodSec = 60 / TEMPO
  const drops: number[] = []
  for (let t = 0; t < durationSec; t += HOP_SEC) {
    const beatPhase = (t % beatPeriodSec) / beatPeriodSec
    const event = detector.update(steps(t), beatPhase, TEMPO, t)
    if (event) drops.push(event.t)
  }
  return drops
}

describe('DropDetector (fullness + onset-density jump + novelty contrast)', () => {
  it('emits nothing for a steady groove with no thinned section', () => {
    // Kick every half second at a steady rate, forever — pulsing energy (so
    // fullness's crest penalty keeps it below threshold most of the time)
    // and a constant onset-activity rate (no jump) and a constant repeating
    // feature pattern (no novelty) — exactly the case that produced a false
    // drop every 3s with the old fast-minus-slow-energy primitive.
    const drops = run((t) => {
      const phase = t % 0.5
      const kick = phase < 0.1
      return {
        lowEnergy: kick ? 0.9 : 0.45,
        onsetActivity: kick ? 0.8 : 0.05,
        vec: kick ? LOUD_VEC : QUIET_VEC,
      }
    }, 30)
    expect(drops).toHaveLength(0)
  })

  it('emits exactly one drop for quiet section -> sustained jump', () => {
    // 4s thinned (low, sparse, no onset activity), then sustained full
    // energy with a steady new onset-activity rate — the mix going from
    // sparse to full, not just louder.
    const drops = run((t): DropDetectorFeatures => {
      if (t < 4) return { lowEnergy: 0.05, onsetActivity: 0.02, vec: QUIET_VEC }
      const onBeat = (t - 4) % 0.25 < HOP_SEC
      return { lowEnergy: 0.9, onsetActivity: onBeat ? 0.8 : 0.1, vec: LOUD_VEC }
    }, 20)
    expect(drops).toHaveLength(1)
    expect(drops[0]).toBeGreaterThan(4)
    expect(drops[0]).toBeLessThan(9) // fires within a few seconds of the transition, not much later
  })

  it('ignores a lone transient spike that decays immediately', () => {
    // Thinned section, then a single 100ms blip that collapses back to
    // quiet — a kick, not a drop. The multi-second fullness window barely
    // moves for a blip this short.
    const drops = run((t): DropDetectorFeatures => {
      const spiking = t >= 4 && t < 4.1
      if (spiking) return { lowEnergy: 0.9, onsetActivity: 0.8, vec: LOUD_VEC }
      return { lowEnergy: 0.05, onsetActivity: 0.02, vec: QUIET_VEC }
    }, 20)
    expect(drops).toHaveLength(0)
  })

  it('does not emit a second drop without another thinned section', () => {
    // One real drop, then sustained fullness/onset-rate/vec for a long time
    // — well past the refractory window. Nothing changes again, so nothing
    // more should fire.
    const drops = run((t): DropDetectorFeatures => {
      if (t < 4) return { lowEnergy: 0.05, onsetActivity: 0.02, vec: QUIET_VEC }
      const onBeat = (t - 4) % 0.25 < HOP_SEC
      return { lowEnergy: 0.9, onsetActivity: onBeat ? 0.8 : 0.1, vec: LOUD_VEC }
    }, 40)
    expect(drops).toHaveLength(1)
  })

  it('emits again after a second genuine thinned section', () => {
    const drops = run((t): DropDetectorFeatures => {
      if (t < 4) return { lowEnergy: 0.05, onsetActivity: 0.02, vec: QUIET_VEC } // thinned
      if (t < 20) {
        const onBeat = (t - 4) % 0.25 < HOP_SEC
        return { lowEnergy: 0.9, onsetActivity: onBeat ? 0.8 : 0.1, vec: LOUD_VEC } // drop + groove
      }
      if (t < 26) return { lowEnergy: 0.05, onsetActivity: 0.02, vec: QUIET_VEC } // second breakdown
      const onBeat = (t - 26) % 0.25 < HOP_SEC
      return { lowEnergy: 0.9, onsetActivity: onBeat ? 0.8 : 0.1, vec: LOUD_VEC } // second drop
    }, 40)
    expect(drops).toHaveLength(2)
    expect(drops[1]).toBeGreaterThan(26)
  })
})
