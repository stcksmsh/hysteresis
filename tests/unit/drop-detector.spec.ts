import { describe, it, expect } from 'vitest'
import { DropDetector } from '../../src/audio/worklet/brain/drop-detector'
import { HOP_SIZE } from '../../src/shared/constants'

const SAMPLE_RATE = 48000
const HOP_MS = (HOP_SIZE / SAMPLE_RATE) * 1000
const HOP_SEC = HOP_MS / 1000
const TEMPO = 120

interface Step {
  lowEnergy: number
  tension: number
}

// Drives the detector across a synthetic timeline and returns every drop
// emitted. beatPhase advances on a real 120bpm grid so the beat-snap path
// is exercised the same way it is in the worklet.
function run(steps: (t: number) => Step, durationSec: number): number[] {
  const detector = new DropDetector(HOP_MS)
  const beatPeriodSec = 60 / TEMPO
  const drops: number[] = []
  for (let t = 0; t < durationSec; t += HOP_SEC) {
    const { lowEnergy, tension } = steps(t)
    const beatPhase = (t % beatPeriodSec) / beatPeriodSec
    const event = detector.update(lowEnergy, tension, beatPhase, TEMPO, t)
    if (event) drops.push(event.t)
  }
  return drops
}

describe('DropDetector', () => {
  it('emits nothing for a steady groove with no thinned section', () => {
    // Kick every half second, energy always high, tension always low —
    // exactly the case that produced a false drop every 3s in v1.
    const drops = run((t) => {
      const phase = t % 0.5
      return { lowEnergy: phase < 0.1 ? 0.9 : 0.45, tension: 0.05 }
    }, 30)
    expect(drops).toHaveLength(0)
  })

  it('emits exactly one drop for quiet section -> sustained jump', () => {
    // 4s thinned (low energy, high tension), then sustained high energy.
    const drops = run((t) => (t < 4 ? { lowEnergy: 0.05, tension: 0.8 } : { lowEnergy: 0.9, tension: 0.05 }), 20)
    expect(drops).toHaveLength(1)
    expect(drops[0]).toBeGreaterThan(4)
    expect(drops[0]).toBeLessThan(5.5) // fires shortly after the jump, not much later
  })

  it('ignores a lone transient spike that decays immediately', () => {
    // Thinned section builds credit, but the "jump" is a single 100ms blip
    // that collapses — a kick, not a drop.
    const drops = run((t) => {
      if (t < 4) return { lowEnergy: 0.05, tension: 0.8 }
      const spiking = t >= 4 && t < 4.1
      return { lowEnergy: spiking ? 0.9 : 0.05, tension: 0.8 }
    }, 20)
    expect(drops).toHaveLength(0)
  })

  it('does not emit a second drop without another thinned section', () => {
    // One real drop, then sustained high energy for a long time — well past
    // the refractory window. Credit was consumed, so nothing more should fire.
    const drops = run((t) => (t < 4 ? { lowEnergy: 0.05, tension: 0.8 } : { lowEnergy: 0.9, tension: 0.05 }), 40)
    expect(drops).toHaveLength(1)
  })

  it('emits again after a second genuine thinned section', () => {
    const drops = run((t) => {
      if (t < 4) return { lowEnergy: 0.05, tension: 0.8 } // thinned
      if (t < 20) return { lowEnergy: 0.9, tension: 0.05 } // drop + groove
      if (t < 26) return { lowEnergy: 0.05, tension: 0.8 } // second breakdown
      return { lowEnergy: 0.9, tension: 0.05 } // second drop
    }, 40)
    expect(drops).toHaveLength(2)
    expect(drops[1]).toBeGreaterThan(26)
  })
})
