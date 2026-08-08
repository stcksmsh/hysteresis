import type { StateFrame, StructuralEvent } from '../shared/types'
import type { Sidecar } from '../shared/sidecar'

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// Beat/bar phase at `t` from the sidecar's beat grid — assumes 4/4 (bar
// boundary every 4th beat), same assumption the live BarTracker makes.
function beatPositionAt(beats: number[], t: number): { beatPhase: number; barPhase: number } {
  if (beats.length < 2) return { beatPhase: 0, barPhase: 0 }
  let i = 0
  while (i < beats.length - 2 && beats[i + 1] <= t) i++
  const b0 = beats[i]
  const b1 = beats[i + 1]
  const period = Math.max(1e-3, b1 - b0)
  const beatPhase = clamp01((t - b0) / period)
  const barPhase = ((i % 4) + beatPhase) / 4
  return { beatPhase, barPhase }
}

// Eased ramp across whichever 'build' section contains `t`, 0 outside one —
// synthesized on the fly rather than stored, since the sidecar only carries
// section spans (SINTEZA_VIZ.md §6), not a baked curve.
function buildProgressAt(sidecar: Sidecar, t: number): number {
  for (const s of sidecar.sections) {
    if (s.kind === 'build' && t >= s.start && t <= s.end) {
      const lin = clamp01((t - s.start) / Math.max(1e-3, s.end - s.start))
      return lin * lin
    }
  }
  return 0
}

const BREAK_TENSION_RAMP_SEC = 2

function tensionAt(sidecar: Sidecar, t: number): number {
  for (const s of sidecar.sections) {
    if (s.kind === 'break' && t >= s.start && t <= s.end) {
      return clamp01((t - s.start) / BREAK_TENSION_RAMP_SEC)
    }
  }
  return 0
}

// Fuses precomputed sidecar structure onto live StateFrames (SINTEZA_VIZ.md
// §5's fusion rule): structure — tempo/beatPhase/barPhase/buildProgress/
// tension/drop|break|downbeat events — comes from the sidecar once loaded;
// detail — bands, onsets, energy, the scope buffer — always stays live.
export class StructureSource {
  private sidecar: Sidecar | null = null
  private nextEventIndex = 0
  private lastPosition = 0

  get active(): boolean {
    return this.sidecar !== null
  }

  load(sidecar: Sidecar): void {
    this.sidecar = sidecar
    this.nextEventIndex = 0
    this.lastPosition = 0
  }

  clear(): void {
    this.sidecar = null
  }

  // Called on every host setPosition/seek so the event scan tracks the live
  // clock instead of replaying history after a jump.
  resyncTo(seconds: number): void {
    this.lastPosition = seconds
    if (!this.sidecar) return
    let idx = this.sidecar.events.findIndex((e) => e.t >= seconds)
    if (idx < 0) idx = this.sidecar.events.length
    this.nextEventIndex = idx
  }

  fuse(frame: StateFrame, positionSec: number): StateFrame {
    if (!this.sidecar) return frame
    const sidecar = this.sidecar
    const { beatPhase, barPhase } = beatPositionAt(sidecar.beats, positionSec)
    const structuralEvents = this.collectEvents(positionSec)
    const liveDetailEvents = frame.events.filter((e) => e.type === 'onset')
    this.lastPosition = positionSec

    return {
      ...frame,
      tempo: sidecar.tempo,
      tempoConfidence: 1,
      beatPhase,
      barPhase,
      buildProgress: buildProgressAt(sidecar, positionSec),
      tension: tensionAt(sidecar, positionSec),
      events: [...liveDetailEvents, ...structuralEvents],
    }
  }

  // Structural events due in the half-open window [lastPosition, t).
  private collectEvents(t: number): StructuralEvent[] {
    if (!this.sidecar) return []
    const events: StructuralEvent[] = []
    while (this.nextEventIndex < this.sidecar.events.length && this.sidecar.events[this.nextEventIndex].t < t) {
      const e = this.sidecar.events[this.nextEventIndex]
      this.nextEventIndex++
      if (e.t < this.lastPosition) continue
      events.push({ type: e.type, strength: e.strength, t: e.t })
    }
    return events
  }
}
