import { describe, it, expect } from 'vitest'
import { parseMidiMessage } from '../../src/midi/midi-messages'

describe('parseMidiMessage', () => {
  it('parses a control change message', () => {
    const msg = parseMidiMessage(new Uint8Array([0xb0 | 3, 74, 100])) // channel 3, CC 74, value 100
    expect(msg).toEqual({ type: 'controlChange', channel: 3, controller: 74, value: 100 })
  })

  it('parses a note-on message', () => {
    const msg = parseMidiMessage(new Uint8Array([0x90 | 0, 60, 127]))
    expect(msg).toEqual({ type: 'noteOn', channel: 0, note: 60, velocity: 127 })
  })

  it('treats a note-on with velocity 0 as a note-off (running-status convention)', () => {
    const msg = parseMidiMessage(new Uint8Array([0x90 | 0, 60, 0]))
    expect(msg).toEqual({ type: 'noteOff', channel: 0, note: 60, velocity: 0 })
  })

  it('parses a real note-off message', () => {
    const msg = parseMidiMessage(new Uint8Array([0x80 | 5, 64, 40]))
    expect(msg).toEqual({ type: 'noteOff', channel: 5, note: 64, velocity: 40 })
  })

  it('parses system realtime messages with no data bytes', () => {
    expect(parseMidiMessage(new Uint8Array([0xf8]))).toEqual({ type: 'clock' })
    expect(parseMidiMessage(new Uint8Array([0xfa]))).toEqual({ type: 'start' })
    expect(parseMidiMessage(new Uint8Array([0xfb]))).toEqual({ type: 'continue' })
    expect(parseMidiMessage(new Uint8Array([0xfc]))).toEqual({ type: 'stop' })
  })

  it('returns unknown for an empty or unrecognized message', () => {
    expect(parseMidiMessage(new Uint8Array([]))).toEqual({ type: 'unknown' })
    expect(parseMidiMessage(new Uint8Array([0xf0, 1, 2]))).toEqual({ type: 'unknown' }) // sysex, not handled
  })
})
