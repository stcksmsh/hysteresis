// MIDI clock sync (master-prompt.md §5's "MIDI clock/beat sync from a
// DAW" use case): MIDI's 0xF8 clock message fires 24 times per quarter
// note, with Start(0xFA)/Continue(0xFB)/Stop(0xFC) framing playback state —
// this tracks real wall-clock inter-tick timing into a live BPM estimate
// plus beat/bar phase, the same shape the live-audio `BeatTracker`
// (src/audio/worklet/brain/beat-tracker.ts) produces from spectral novelty,
// so a future integration point (feeding this into the Conductor instead
// of/alongside the audio-derived tempo) has a compatible shape to target —
// not wired into Conductor in this pass, see AGENTS.md.
//
// MIDI clock carries no time-signature information at all — 4/4 (4 beats
// per bar) is assumed for `barPhase`, same as western dance/electronic
// music defaults everywhere else in this codebase (bar = 4 beats).
export interface MidiClockState {
  bpm: number
  // 0..1, ramps up over the first bar's worth of ticks as the running
  // average has enough samples to trust — mirrors BeatTracker's own
  // tempoConfidence in spirit (a fresh tracker knows nothing yet).
  confidence: number
  beatPhase: number // 0..1 within one quarter-note beat
  barPhase: number // 0..1 within one 4-beat bar
  running: boolean
}

const TICKS_PER_BEAT = 24
const BEATS_PER_BAR = 4
const CONFIDENCE_TICKS = TICKS_PER_BEAT // full confidence after one beat's worth of ticks

export class MidiClockTracker {
  private tickInBeat = 0
  private beatInBar = 0
  private lastTickTimeSec: number | null = null
  private avgTickPeriodSec = 0
  private ticksSeen = 0
  private running = false

  // `timeSec` is the caller's own clock (e.g. `performance.now()/1000` or
  // a MIDIMessageEvent's `timeStamp`) — this class has no notion of real
  // time on its own, which is exactly what makes it deterministically
  // testable with synthetic timestamps.
  onClockTick(timeSec: number): void {
    if (this.lastTickTimeSec !== null) {
      const period = timeSec - this.lastTickTimeSec
      if (period > 0) {
        // Fast convergence for the first beat (a fresh/reset tracker
        // shouldn't need a full smoothing window to get a rough BPM),
        // settling into a steady exponential smoothing after — mirrors
        // BeatTracker's own "converge fast, then stabilize" shape.
        const alpha = this.ticksSeen < TICKS_PER_BEAT ? 1 / (this.ticksSeen + 1) : 0.1
        this.avgTickPeriodSec += (period - this.avgTickPeriodSec) * alpha
      }
    }
    this.lastTickTimeSec = timeSec
    this.ticksSeen++
    this.tickInBeat = (this.tickInBeat + 1) % TICKS_PER_BEAT
    if (this.tickInBeat === 0) this.beatInBar = (this.beatInBar + 1) % BEATS_PER_BAR
  }

  // Resets phase to bar/beat 1 — a real DAW transport restart, not just a
  // pause/resume (see onContinue below for that distinction).
  onStart(): void {
    this.running = true
    this.tickInBeat = 0
    this.beatInBar = 0
    this.lastTickTimeSec = null
    this.avgTickPeriodSec = 0
    this.ticksSeen = 0
  }

  // Resumes without resetting phase/tempo — a DAW un-pausing mid-bar sends
  // Continue, not Start, specifically so downstream listeners don't jump
  // back to beat 1.
  onContinue(): void {
    this.running = true
  }

  onStop(): void {
    this.running = false
  }

  getState(): MidiClockState {
    return {
      bpm: this.avgTickPeriodSec > 0 ? 60 / (this.avgTickPeriodSec * TICKS_PER_BEAT) : 0,
      confidence: Math.min(1, this.ticksSeen / CONFIDENCE_TICKS),
      beatPhase: this.tickInBeat / TICKS_PER_BEAT,
      barPhase: (this.beatInBar + this.tickInBeat / TICKS_PER_BEAT) / BEATS_PER_BAR,
      running: this.running,
    }
  }
}
