import { describe, it, expect } from 'vitest'
import { encodeOscMessage, encodeOscBundle, decodeOscPacket, type OscMessage, type OscBundle } from '../../src/osc/osc-codec'

describe('OSC codec', () => {
  it('round-trips a float message', () => {
    const bytes = encodeOscMessage('/hysteresis/bus/energy', [{ type: 'f', value: 0.5 }])
    const decoded = decodeOscPacket(bytes) as OscMessage
    expect(decoded.kind).toBe('message')
    expect(decoded.address).toBe('/hysteresis/bus/energy')
    expect(decoded.args).toEqual([{ type: 'f', value: 0.5 }])
  })

  it('round-trips an int argument', () => {
    const bytes = encodeOscMessage('/count', [{ type: 'i', value: 42 }])
    const decoded = decodeOscPacket(bytes) as OscMessage
    expect(decoded.args).toEqual([{ type: 'i', value: 42 }])
  })

  it('round-trips a string argument', () => {
    const bytes = encodeOscMessage('/name', [{ type: 's', value: 'hysteresis' }])
    const decoded = decodeOscPacket(bytes) as OscMessage
    expect(decoded.args).toEqual([{ type: 's', value: 'hysteresis' }])
  })

  it('round-trips bool (T/F) arguments, which carry no bytes of their own', () => {
    const bytes = encodeOscMessage('/flags', [{ type: 'T' }, { type: 'F' }])
    const decoded = decodeOscPacket(bytes) as OscMessage
    expect(decoded.args).toEqual([{ type: 'T' }, { type: 'F' }])
  })

  it('round-trips a message with no arguments at all', () => {
    const bytes = encodeOscMessage('/ping', [])
    const decoded = decodeOscPacket(bytes) as OscMessage
    expect(decoded.args).toEqual([])
  })

  it('round-trips an address whose length is already a multiple of 4 (padding edge case)', () => {
    const bytes = encodeOscMessage('/abc', [{ type: 'f', value: 1 }]) // 4 chars + \0 = 5, pads to 8
    const decoded = decodeOscPacket(bytes) as OscMessage
    expect(decoded.address).toBe('/abc')
  })

  it('round-trips a bundle of multiple messages, preserving order', () => {
    const bytes = encodeOscBundle([
      { address: '/a', args: [{ type: 'f', value: 1 }] },
      { address: '/b', args: [{ type: 'f', value: 2 }] },
      { address: '/c', args: [{ type: 's', value: 'three' }] },
    ])
    const decoded = decodeOscPacket(bytes) as OscBundle
    expect(decoded.kind).toBe('bundle')
    expect(decoded.timeTag).toBe(1n)
    expect(decoded.elements).toHaveLength(3)
    expect((decoded.elements[0] as OscMessage).address).toBe('/a')
    expect((decoded.elements[1] as OscMessage).address).toBe('/b')
    expect((decoded.elements[2] as OscMessage).args).toEqual([{ type: 's', value: 'three' }])
  })

  it('rejects a message with a corrupted (non-"," leading) type tag', () => {
    // Hand-build bytes with a type tag that doesn't start with ',' — the codec
    // must reject this rather than silently misparsing arguments.
    const bytes = encodeOscMessage('/x', [])
    const view = new DataView(bytes.buffer)
    // '/x\0\0' is 4 bytes, so the type tag "," starts at offset 4 — corrupt it.
    view.setUint8(4, 'a'.charCodeAt(0))
    expect(() => decodeOscPacket(bytes)).toThrow(/type tag/)
  })
})
