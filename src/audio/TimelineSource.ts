import type { BandEnergies, SpectralHit, StateFrame, StructuralEvent } from '../shared/types'
import { type Timeline, type TimelineEvent, decodeEnvelope, musicalPositionAt } from '../shared/timeline'

export type StateFrameListener = (frame: StateFrame) => void

const BAND_KEYS: (keyof BandEnergies)[] = ['sub', 'low', 'mid', 'presence', 'air']

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// Replays a baked .hyst Timeline as a live StateFrame stream, so it can drop
// into the same dispatchFrame path the worklet uses and Choreographer/scenes
// need no changes to consume it.
//
// This is still a forward-playback-only sampler: `bandsRaw`/`centroid`/`pan`
// are reconstructed from per-track envelopes rather than measured directly,
// and event lookup is a forward scan that assumes `t` only ever increases —
// it does not yet support seeking to an arbitrary timestamp (that needs a
// deterministic reseed of Choreographer's own spring/smoother state, not
// just this class — see the seek-safety design in the project plan).
// `buildProgress`/`tension` do come from the compiler's baked curves when
// present (tools/compile/structure.ts); a v1-shaped or hand-authored file
// without them just samples 0, same as before those curves existed.
export class TimelineSource {
  private readonly timeline: Timeline
  private readonly getCurrentTime: () => number
  private readonly listeners = new Set<StateFrameListener>()
  private readonly levelEnvelopes: Uint8Array[]
  private readonly toneEnvelopes: Uint8Array[]
  private readonly buildProgressEnvelope: Uint8Array | undefined
  private readonly tensionEnvelope: Uint8Array | undefined
  private readonly sortedEvents: TimelineEvent[]
  private readonly sortedStructuralEvents: StructuralEvent[]

  private rafHandle: number | null = null
  private lastEmittedT = 0
  private nextEventIndex = 0
  private nextStructuralEventIndex = 0

  constructor(timeline: Timeline, getCurrentTime: () => number) {
    this.timeline = timeline
    this.getCurrentTime = getCurrentTime
    this.levelEnvelopes = (timeline.envelopes?.tracks ?? []).map((t) => decodeEnvelope(t.level))
    this.toneEnvelopes = (timeline.envelopes?.tracks ?? []).map((t) => decodeEnvelope(t.tone))
    this.buildProgressEnvelope = timeline.envelopes?.buildProgress
      ? decodeEnvelope(timeline.envelopes.buildProgress)
      : undefined
    this.tensionEnvelope = timeline.envelopes?.tension ? decodeEnvelope(timeline.envelopes.tension) : undefined
    // compile() already emits events in time order, but nothing enforces
    // that a hand-edited or third-party-produced .hyst file does — the
    // forward scan below silently drops/duplicates events if it isn't.
    this.sortedEvents = [...timeline.events].sort((a, b) => a.t - b.t)
    this.sortedStructuralEvents = [...(timeline.structuralEvents ?? [])].sort((a, b) => a.t - b.t)
  }

  onStateFrame(listener: StateFrameListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  start(): void {
    this.lastEmittedT = this.getCurrentTime()
    const loop = () => {
      this.tick()
      this.rafHandle = requestAnimationFrame(loop)
    }
    this.rafHandle = requestAnimationFrame(loop)
  }

  stop(): void {
    if (this.rafHandle !== null) cancelAnimationFrame(this.rafHandle)
    this.rafHandle = null
  }

  // One sampling step: reads the clock, emits a StateFrame. Split out from
  // start()'s rAF loop so it can be driven directly (with a fake clock) in
  // tests, without a real animation-frame scheduler.
  tick(): void {
    const t = this.getCurrentTime()
    const frame = this.frameAt(t, this.lastEmittedT)
    this.lastEmittedT = t
    for (const listener of this.listeners) listener(frame)
  }

  private frameAt(t: number, lastT: number): StateFrame {
    const { bpm, beatPhase, barPhase } = musicalPositionAt(this.timeline.tempoMap, t)

    const bands: BandEnergies = { sub: 0, low: 0, mid: 0, presence: 0, air: 0 }
    let energySum = 0
    let centroidWeighted = 0
    let panWeighted = 0
    let weightSum = 0

    const tracks = this.timeline.tracks
    for (let i = 0; i < tracks.length; i++) {
      const level = this.sampleEnvelope(this.levelEnvelopes[i], t)
      if (level <= 0) continue
      const tone = this.sampleEnvelope(this.toneEnvelopes[i], t)
      energySum += level
      centroidWeighted += tone * level
      panWeighted += tracks[i].pan * level
      weightSum += level
      bands[BAND_KEYS[Math.min(BAND_KEYS.length - 1, Math.floor(clamp01(tone) * BAND_KEYS.length))]] += level
    }
    for (const key of BAND_KEYS) bands[key] = clamp01(bands[key])

    const { events, spectralHits } = this.collectEvents(lastT, t)

    return {
      t,
      tempo: bpm,
      tempoConfidence: this.timeline.tempoMap.length > 0 ? 1 : 0,
      beatPhase,
      barPhase,
      buildProgress: this.sampleEnvelope(this.buildProgressEnvelope, t),
      tension: this.sampleEnvelope(this.tensionEnvelope, t),
      energy: clamp01(energySum / Math.max(1, tracks.length)),
      bandsRaw: bands,
      centroid: weightSum > 0 ? centroidWeighted / weightSum : 0,
      flatness: 0.3,
      pan: weightSum > 0 ? panWeighted / weightSum : 0,
      spectralHits,
      events,
    }
  }

  // Per-instrument onsets plus baked structural events (drop/break/downbeat),
  // both in the half-open window [lastT, t). Assumes t only moves forward —
  // see the class comment.
  private collectEvents(lastT: number, t: number): { events: StructuralEvent[]; spectralHits: SpectralHit[] } {
    const events: StructuralEvent[] = []
    const spectralHits: SpectralHit[] = []
    while (this.nextEventIndex < this.sortedEvents.length && this.sortedEvents[this.nextEventIndex].t < t) {
      const e = this.sortedEvents[this.nextEventIndex]
      this.nextEventIndex++
      if (e.t < lastT) continue
      events.push({ type: 'onset', strength: e.level, t: e.t, tone: e.tone, pan: e.pan })
      spectralHits.push({ tone: e.tone, pan: e.pan, strength: e.level })
    }
    while (
      this.nextStructuralEventIndex < this.sortedStructuralEvents.length &&
      this.sortedStructuralEvents[this.nextStructuralEventIndex].t < t
    ) {
      const e = this.sortedStructuralEvents[this.nextStructuralEventIndex]
      this.nextStructuralEventIndex++
      if (e.t < lastT) continue
      events.push(e)
    }
    return { events, spectralHits }
  }

  private sampleEnvelope(arr: Uint8Array | undefined, t: number): number {
    const rate = this.timeline.envelopes?.rate ?? 0
    if (!arr || arr.length === 0 || rate <= 0) return 0
    const pos = Math.max(0, t * rate)
    const i0 = Math.min(Math.floor(pos), arr.length - 1)
    const i1 = Math.min(i0 + 1, arr.length - 1)
    const frac = pos - Math.floor(pos)
    return clamp01((arr[i0] + (arr[i1] - arr[i0]) * frac) / 255)
  }
}
