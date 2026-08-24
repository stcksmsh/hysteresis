import { describe, it, expect } from 'vitest'
import { MidiCcInput, ccKey } from '../../src/midi/midi-cc-input'
import type { ControlChangeMessage } from '../../src/midi/midi-messages'

function cc(channel: number, controller: number, value: number): ControlChangeMessage {
  return { type: 'controlChange', channel, controller, value }
}

describe('MidiCcInput', () => {
  it('returns 0 for a CC that has never been seen', () => {
    const input = new MidiCcInput()
    expect(input.get(ccKey(0, 74))).toBe(0)
    expect(input.has(ccKey(0, 74))).toBe(false)
  })

  it('normalizes 0..127 to 0..1', () => {
    const input = new MidiCcInput()
    input.onControlChange(cc(0, 74, 127))
    expect(input.get(ccKey(0, 74))).toBe(1)
    input.onControlChange(cc(0, 74, 0))
    expect(input.get(ccKey(0, 74))).toBe(0)
    input.onControlChange(cc(0, 74, 64))
    expect(input.get(ccKey(0, 74))).toBeCloseTo(64 / 127, 5)
  })

  it('keeps values separate per channel+controller', () => {
    const input = new MidiCcInput()
    input.onControlChange(cc(0, 1, 127))
    input.onControlChange(cc(1, 1, 0))
    expect(input.get(ccKey(0, 1))).toBe(1)
    expect(input.get(ccKey(1, 1))).toBe(0)
  })

  it('MIDI learn resolves with the key of the next CC received, then stops listening', () => {
    const input = new MidiCcInput()
    let learned: string | null = null
    input.learnNext((key) => (learned = key))
    input.onControlChange(cc(2, 7, 100))
    expect(learned).toBe(ccKey(2, 7))

    learned = null
    input.onControlChange(cc(3, 8, 50)) // no active learn — should not fire
    expect(learned).toBe(null)
  })

  it('cancelLearn stops a pending learn from firing', () => {
    const input = new MidiCcInput()
    let learned: string | null = null
    input.learnNext((key) => (learned = key))
    input.cancelLearn()
    input.onControlChange(cc(0, 1, 1))
    expect(learned).toBe(null)
  })
})
