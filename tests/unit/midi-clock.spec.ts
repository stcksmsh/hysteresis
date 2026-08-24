import { describe, it, expect } from 'vitest'
import { MidiClockTracker } from '../../src/midi/midi-clock'

// 24 ticks per quarter note is the MIDI spec's own constant — a steady
// 120 BPM clock ticks every (60/120)/24 = 0.02083...s.
function runClock(tracker: MidiClockTracker, bpm: number, beats: number, startAtSec = 0): void {
  const tickPeriod = 60 / bpm / 24
  let t = startAtSec
  for (let i = 0; i < beats * 24; i++) {
    tracker.onClockTick(t)
    t += tickPeriod
  }
}

describe('MidiClockTracker', () => {
  it('starts with zero confidence and not running', () => {
    const tracker = new MidiClockTracker()
    const state = tracker.getState()
    expect(state.confidence).toBe(0)
    expect(state.running).toBe(false)
    expect(state.bpm).toBe(0)
  })

  it('locks onto a steady 120 BPM clock', () => {
    const tracker = new MidiClockTracker()
    tracker.onStart()
    runClock(tracker, 120, 8)
    const state = tracker.getState()
    expect(state.bpm).toBeGreaterThan(119)
    expect(state.bpm).toBeLessThan(121)
    expect(state.confidence).toBe(1)
    expect(state.running).toBe(true)
  })

  it('locks onto a different tempo just as well', () => {
    const tracker = new MidiClockTracker()
    tracker.onStart()
    runClock(tracker, 90, 8)
    const state = tracker.getState()
    expect(state.bpm).toBeGreaterThan(89)
    expect(state.bpm).toBeLessThan(91)
  })

  it('wraps beatPhase every 24 ticks and barPhase every 4 beats (assumed 4/4)', () => {
    const tracker = new MidiClockTracker()
    tracker.onStart()
    // After exactly 24 ticks, one full beat has elapsed — phase wraps to 0.
    for (let i = 0; i < 24; i++) tracker.onClockTick(i * 0.02)
    expect(tracker.getState().beatPhase).toBe(0)
    expect(tracker.getState().barPhase).toBeCloseTo(0.25, 5) // 1 of 4 beats into the bar

    // After 4 full beats (96 ticks), a full bar has elapsed — both wrap to 0.
    for (let i = 24; i < 96; i++) tracker.onClockTick(i * 0.02)
    expect(tracker.getState().beatPhase).toBe(0)
    expect(tracker.getState().barPhase).toBe(0)
  })

  it('onStart resets phase and tempo estimate', () => {
    const tracker = new MidiClockTracker()
    tracker.onStart()
    runClock(tracker, 120, 4)
    tracker.onStart()
    const state = tracker.getState()
    expect(state.confidence).toBe(0)
    expect(state.beatPhase).toBe(0)
    expect(state.barPhase).toBe(0)
  })

  it('onStop marks not running without resetting phase/tempo', () => {
    const tracker = new MidiClockTracker()
    tracker.onStart()
    runClock(tracker, 120, 4)
    const bpmBeforeStop = tracker.getState().bpm
    tracker.onStop()
    const state = tracker.getState()
    expect(state.running).toBe(false)
    expect(state.bpm).toBeCloseTo(bpmBeforeStop, 5)
  })

  it('onContinue resumes without resetting phase (unlike onStart)', () => {
    const tracker = new MidiClockTracker()
    tracker.onStart()
    runClock(tracker, 120, 1) // one full beat + a bit
    tracker.onClockTick(1) // one more tick into the next beat
    const phaseBeforeStop = tracker.getState().beatPhase
    tracker.onStop()
    tracker.onContinue()
    expect(tracker.getState().beatPhase).toBe(phaseBeforeStop)
    expect(tracker.getState().running).toBe(true)
  })
})
