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
})
