import { describe, it, expect } from 'vitest'
import { BeatTracker } from '../../src/audio/worklet/brain/beat-tracker'
import { HOP_SIZE } from '../../src/shared/constants'

const SAMPLE_RATE = 48000
const HOP_SEC = HOP_SIZE / SAMPLE_RATE

// Deterministic synthetic signal: a metronome click train at a known BPM
// (spectral-flux novelty spikes on a fixed grid, zero between clicks) — the
// beat tracker should lock onto its true tempo without ever seeing music.
function runClickTrain(bpm: number, durationSec: number): BeatTracker {
  const tracker = new BeatTracker(HOP_SEC)
  const periodSec = 60 / bpm
  let t = 0
  let lastOutput = { tempoBpm: 0, tempoConfidence: 0, beatPhase: 0 }
  while (t < durationSec) {
    const phaseInPeriod = t % periodSec
    const novelty = phaseInPeriod < HOP_SEC ? 1.0 : 0.0
    lastOutput = tracker.update(novelty, t)
    t += HOP_SEC
  }
  void lastOutput
  return tracker
}

describe('BeatTracker', () => {
  it('locks onto the true tempo of a 120 BPM click train', () => {
    const tracker = runClickTrain(120, 12)
    const result = tracker.update(0, 12)
    expect(result.tempoBpm).toBeGreaterThan(110)
    expect(result.tempoBpm).toBeLessThan(130)
    expect(result.tempoConfidence).toBeGreaterThan(0.1)
  })

  it('locks onto a different tempo (90 BPM) just as well', () => {
    const tracker = runClickTrain(90, 12)
    const result = tracker.update(0, 12)
    expect(result.tempoBpm).toBeGreaterThan(80)
    expect(result.tempoBpm).toBeLessThan(100)
  })

  it('keeps beatPhase advancing smoothly through a silent gap (no onsets)', () => {
    const tracker = runClickTrain(120, 8)
    const before = tracker.update(0, 8)
    // 2 seconds of silence — no onsets to correct phase, it must free-run
    let t = 8
    let after = before
    while (t < 10) {
      after = tracker.update(0, t)
      t += HOP_SEC
    }
    // tempo estimate should be unchanged by silence (no new novelty to shift it)
    expect(after.tempoBpm).toBeCloseTo(before.tempoBpm, 0)
  })
})
