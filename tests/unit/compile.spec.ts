import { describe, it, expect, afterAll } from 'vitest'
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { compile } from '../../tools/compile/index'
import { decodeEnvelope } from '../../src/shared/timeline'

const SR = 44100
const DUR = 4
const N = SR * DUR

function writeMonoWav(path: string, samples: Float32Array): void {
  const dataSize = samples.length * 2
  const buf = Buffer.alloc(44 + dataSize)
  buf.write('RIFF', 0, 'ascii')
  buf.writeUInt32LE(36 + dataSize, 4)
  buf.write('WAVE', 8, 'ascii')
  buf.write('fmt ', 12, 'ascii')
  buf.writeUInt32LE(16, 16)
  buf.writeUInt16LE(1, 20)
  buf.writeUInt16LE(1, 22)
  buf.writeUInt32LE(SR, 24)
  buf.writeUInt32LE(SR * 2, 28)
  buf.writeUInt16LE(2, 32)
  buf.writeUInt16LE(16, 34)
  buf.write('data', 36, 'ascii')
  buf.writeUInt32LE(dataSize, 40)
  let off = 44
  for (let i = 0; i < samples.length; i++) {
    const v = Math.max(-1, Math.min(1, samples[i]))
    buf.writeInt16LE(Math.round(v * 32767), off)
    off += 2
  }
  writeFileSync(path, buf)
}

const dir = mkdtempSync(join(tmpdir(), 'hysteresis-compile-test-'))
afterAll(() => rmSync(dir, { recursive: true, force: true }))

// A low periodic thump (kick-like) and a bright noisy burst (hat-like),
// pulsing on alternating beats at 120bpm, each in its own stem — the same
// shape as a real REAPER export, just synthetic.
const beatSec = 0.5
const kick = new Float32Array(N)
const hat = new Float32Array(N)
for (let t = 0; t < DUR; t += beatSec) {
  const start = Math.floor(t * SR)
  for (let i = 0; i < SR * 0.1; i++) {
    if (start + i >= N) break
    const env = Math.exp(-i / (SR * 0.02))
    kick[start + i] += Math.sin(2 * Math.PI * 55 * (i / SR)) * env
  }
}
for (let t = beatSec / 2; t < DUR; t += beatSec) {
  const start = Math.floor(t * SR)
  for (let i = 0; i < SR * 0.02; i++) {
    if (start + i >= N) break
    const env = Math.exp(-i / (SR * 0.005))
    hat[start + i] += (Math.random() * 2 - 1) * env
  }
}
writeMonoWav(join(dir, 'kick.wav'), kick)
writeMonoWav(join(dir, 'hat.wav'), hat)

const project = {
  duration: DUR,
  tempoMap: [{ t: 0, bpm: 120, num: 4, den: 4 }],
  markers: [{ t: 0, name: 'Drop' }],
  tracks: [
    { name: 'Kick', pan: 0, stem: 'kick.wav' },
    { name: 'Hat', pan: 0.9, stem: 'hat.wav' },
  ],
  mix: 'kick.wav', // unused by compile(), just needs to be present
}
const projectPath = join(dir, 'project.json')
writeFileSync(projectPath, JSON.stringify(project))

describe('compile', () => {
  it('carries project structure through untouched', () => {
    const timeline = compile(projectPath)
    expect(timeline.duration).toBe(DUR)
    expect(timeline.tempoMap).toEqual(project.tempoMap)
    expect(timeline.markers).toEqual(project.markers)
    expect(timeline.tracks).toHaveLength(2)
  })

  it('gives each track its exact project pan, not an inferred one', () => {
    const timeline = compile(projectPath)
    expect(timeline.tracks[0].pan).toBe(0)
    expect(timeline.tracks[1].pan).toBe(0.9)
  })

  it('separates low and bright stems by measured tone', () => {
    const timeline = compile(projectPath)
    const [kickTrack, hatTrack] = timeline.tracks
    expect(kickTrack.tone).toBeLessThan(0.2)
    expect(hatTrack.tone).toBeGreaterThan(kickTrack.tone)
  })

  it('detects roughly one onset per hit, tagged with the right track', () => {
    const timeline = compile(projectPath)
    const kickEvents = timeline.events.filter((e) => e.track === 0)
    const hatEvents = timeline.events.filter((e) => e.track === 1)
    // 8 beats over 4s at 120bpm — allow slack for edge effects at the tail.
    expect(kickEvents.length).toBeGreaterThanOrEqual(6)
    expect(kickEvents.length).toBeLessThanOrEqual(9)
    expect(hatEvents.length).toBeGreaterThanOrEqual(6)
    expect(hatEvents.length).toBeLessThanOrEqual(9)
    for (const e of kickEvents) expect(e.pan).toBe(0)
    for (const e of hatEvents) expect(e.pan).toBe(0.9)
  })

  it('emits events in time order across merged stems', () => {
    const timeline = compile(projectPath)
    for (let i = 1; i < timeline.events.length; i++) {
      expect(timeline.events[i].t).toBeGreaterThanOrEqual(timeline.events[i - 1].t)
    }
  })

  it('decodes to a non-trivial, monotonically-sane envelope', () => {
    const timeline = compile(projectPath)
    expect(timeline.envelopes).toBeDefined()
    const level = decodeEnvelope(timeline.envelopes!.tracks[0].level)
    expect(level.length).toBeGreaterThan(0)
    let sawNonZero = false
    for (const v of level) if (v > 0) sawNonZero = true
    expect(sawNonZero).toBe(true)
  })

  it('is a v2 file', () => {
    expect(compile(projectPath).version).toBe(2)
  })
})

// A second fixture, purpose-built to exercise offline structure detection
// end-to-end: a genuine two-sided silence (both stems drop out together,
// 4-6s, matching a named "Breakdown" region so marker-based and per-stem
// detection can be cross-checked) and a genuine multi-stem coincident level
// jump (~9s, no marker — this one only per-stem detection can find).
const DUR2 = 12
const N2 = SR * DUR2

function ampAt(t: number): number {
  if (t >= 4 && t < 6) return 0
  if (t >= 9) return 1.8
  return 1
}

const kick2 = new Float32Array(N2)
const hat2 = new Float32Array(N2)
for (let t = 0; t < DUR2; t += beatSec) {
  const amp = ampAt(t)
  if (amp === 0) continue
  const start = Math.floor(t * SR)
  for (let i = 0; i < SR * 0.1; i++) {
    if (start + i >= N2) break
    const env = Math.exp(-i / (SR * 0.02))
    kick2[start + i] += Math.sin(2 * Math.PI * 55 * (i / SR)) * env * amp
  }
}
for (let t = beatSec / 2; t < DUR2; t += beatSec) {
  const amp = ampAt(t)
  if (amp === 0) continue
  const start = Math.floor(t * SR)
  for (let i = 0; i < SR * 0.02; i++) {
    if (start + i >= N2) break
    const env = Math.exp(-i / (SR * 0.005))
    hat2[start + i] += (Math.random() * 2 - 1) * env * amp
  }
}

const dir2 = mkdtempSync(join(tmpdir(), 'hysteresis-compile-structure-test-'))
afterAll(() => rmSync(dir2, { recursive: true, force: true }))
writeMonoWav(join(dir2, 'kick.wav'), kick2)
writeMonoWav(join(dir2, 'hat.wav'), hat2)
writeMonoWav(join(dir2, 'mix.wav'), kick2.map((v, i) => v + hat2[i]))

const project2 = {
  duration: DUR2,
  tempoMap: [{ t: 0, bpm: 120, num: 4, den: 4 }],
  markers: [{ t: 4, end: 6, name: 'Breakdown' }],
  tracks: [
    { name: 'Kick', pan: 0, stem: 'kick.wav' },
    { name: 'Hat', pan: 0.9, stem: 'hat.wav' },
  ],
  mix: 'mix.wav',
}
const projectPath2 = join(dir2, 'project.json')
writeFileSync(projectPath2, JSON.stringify(project2))

describe('compile — offline structure detection', () => {
  it('turns a named region into a classified section', () => {
    const timeline = compile(projectPath2)
    const breakSection = timeline.sections?.find((s) => s.kind === 'break')
    expect(breakSection).toBeDefined()
    expect(breakSection!.start).toBeCloseTo(4, 0)
    expect(breakSection!.end).toBeCloseTo(6, 0)
  })

  it('detects the coincident multi-stem jump as a drop, with no marker to hint it', () => {
    const timeline = compile(projectPath2)
    const drops = timeline.structuralEvents?.filter((e) => e.type === 'drop') ?? []
    expect(drops.length).toBeGreaterThan(0)
    expect(drops.some((e) => Math.abs(e.t - 9) < 1.5)).toBe(true)
  })

  it('bakes a buildProgress envelope that anticipates the detected drop', () => {
    const timeline = compile(projectPath2)
    expect(timeline.envelopes?.buildProgress).toBeDefined()
    const curve = decodeEnvelope(timeline.envelopes!.buildProgress!)
    const rate = timeline.envelopes!.rate
    const early = curve[Math.round(1 * rate)]
    const nearDrop = curve[Math.round(8.5 * rate)]
    expect(nearDrop).toBeGreaterThan(early)
  })

  it('bakes a tension envelope that is higher during the breakdown than during the busy section', () => {
    const timeline = compile(projectPath2)
    expect(timeline.envelopes?.tension).toBeDefined()
    const curve = decodeEnvelope(timeline.envelopes!.tension!)
    const rate = timeline.envelopes!.rate
    const duringBreak = curve[Math.round(5 * rate)]
    const duringGroove = curve[Math.round(1 * rate)]
    expect(duringBreak).toBeGreaterThan(duringGroove)
  })

  it('emits downbeats from the tempo map alone', () => {
    const timeline = compile(projectPath2)
    const downbeats = timeline.structuralEvents?.filter((e) => e.type === 'downbeat') ?? []
    // 120bpm 4/4 over 12s: a downbeat every 2s, ~6 of them.
    expect(downbeats.length).toBeGreaterThanOrEqual(4)
    expect(downbeats.length).toBeLessThanOrEqual(7)
  })
})
