import { describe, it, expect } from 'vitest'
import { labelSections } from '../../scripts/structure'
import type { SidecarEvent, SidecarSection, SidecarStemPresence } from '../../src/shared/sidecar'

const ENVELOPE_RATE = 20

function flatPresence(value: number, length: number): SidecarStemPresence {
  const arr = new Array(length).fill(value)
  return { vocals: arr, drums: arr, bass: arr, other: arr, leadPresence: arr }
}

describe('labelSections (AGENTS.md §4.3/§4.5 step 6, heuristic — not ML)', () => {
  it('labels a build-kind section "build" and a break-kind section "breakdown"', () => {
    const sections: SidecarSection[] = [
      { start: 10, end: 14, kind: 'build' },
      { start: 20, end: 24, kind: 'break' },
    ]
    const labeled = labelSections(sections, [], 30, ENVELOPE_RATE)
    expect(labeled.find((s) => s.kind === 'build')?.label).toBe('build')
    expect(labeled.find((s) => s.kind === 'break')?.label).toBe('breakdown')
  })

  it('synthesizes an intro span before the first detected section/event', () => {
    const sections: SidecarSection[] = [{ start: 10, end: 14, kind: 'build' }]
    const labeled = labelSections(sections, [], 30, ENVELOPE_RATE)
    const intro = labeled.find((s) => s.label === 'intro')
    expect(intro).toBeDefined()
    expect(intro?.start).toBe(0)
    expect(intro?.end).toBe(10)
  })

  it('synthesizes an outro span after the last detected section/event', () => {
    const events: SidecarEvent[] = [{ type: 'drop', t: 20, strength: 1 }]
    const labeled = labelSections([], events, 30, ENVELOPE_RATE)
    const outro = labeled.find((s) => s.label === 'outro')
    expect(outro).toBeDefined()
    expect(outro?.start).toBe(20)
    expect(outro?.end).toBe(30)
  })

  it('does not synthesize an intro/outro shorter than the minimum span', () => {
    const events: SidecarEvent[] = [{ type: 'drop', t: 1, strength: 1 }]
    const labeled = labelSections([], events, 2, ENVELOPE_RATE) // 1s gap on each side — below the 2s minimum
    expect(labeled.some((s) => s.label === 'intro' || s.label === 'outro')).toBe(false)
  })

  it('skips a positionally-plausible intro when stem presence shows the mix is actually loud there (not a real intro)', () => {
    const events: SidecarEvent[] = [{ type: 'drop', t: 10, strength: 1 }]
    const loudThroughout = flatPresence(0.9, 40)
    const labeled = labelSections([], events, 20, ENVELOPE_RATE, loudThroughout)
    expect(labeled.some((s) => s.label === 'intro')).toBe(false)
  })

  it('keeps a positionally-plausible intro when stem presence confirms it is genuinely sparse', () => {
    const events: SidecarEvent[] = [{ type: 'drop', t: 10, strength: 1 }]
    const sparseIntro = flatPresence(0.05, 40)
    const labeled = labelSections([], events, 20, ENVELOPE_RATE, sparseIntro)
    expect(labeled.some((s) => s.label === 'intro')).toBe(true)
  })

  it('returns sections sorted by start time, including synthesized ones', () => {
    const sections: SidecarSection[] = [{ start: 10, end: 14, kind: 'build' }]
    const events: SidecarEvent[] = [{ type: 'drop', t: 14, strength: 1 }]
    const labeled = labelSections(sections, events, 30, ENVELOPE_RATE)
    for (let i = 1; i < labeled.length; i++) {
      expect(labeled[i].start).toBeGreaterThanOrEqual(labeled[i - 1].start)
    }
  })
})
