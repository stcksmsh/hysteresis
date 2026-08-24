import { describe, it, expect } from 'vitest'
import { encodeEnttecDmxPacket } from '../../src/dmx/enttec-usb-pro'

describe('encodeEnttecDmxPacket', () => {
  it('wraps data in the Enttec Widget API frame (START, Label 6, length, END)', () => {
    const bytes = encodeEnttecDmxPacket(new Uint8Array([10, 20, 30]))
    expect(bytes[0]).toBe(0x7e) // START
    expect(bytes[1]).toBe(6) // Label: Output Only Send DMX Packet
    // payload = start code (1) + 3 channels = 4
    expect(bytes[2]).toBe(4) // length LSB
    expect(bytes[3]).toBe(0) // length MSB
    expect(bytes[bytes.length - 1]).toBe(0xe7) // END
  })

  it('prepends the DMX start code (0x00) and carries channel data verbatim', () => {
    const bytes = encodeEnttecDmxPacket(new Uint8Array([10, 20, 30]))
    expect(bytes[4]).toBe(0) // start code
    expect(Array.from(bytes.subarray(5, 8))).toEqual([10, 20, 30])
  })

  it('produces a total length of header(4) + startcode(1) + channels + end(1)', () => {
    const bytes = encodeEnttecDmxPacket(new Uint8Array(100))
    expect(bytes.byteLength).toBe(4 + 1 + 100 + 1)
  })

  it('computes a correct 16-bit length for a full 512-channel universe', () => {
    const bytes = encodeEnttecDmxPacket(new Uint8Array(512))
    // payload = 1 + 512 = 513 = 0x0201
    expect(bytes[2]).toBe(0x01)
    expect(bytes[3]).toBe(0x02)
    expect(bytes.byteLength).toBe(4 + 513 + 1)
  })

  it('truncates data longer than 512 channels', () => {
    const bytes = encodeEnttecDmxPacket(new Uint8Array(600))
    expect(bytes.byteLength).toBe(4 + 1 + 512 + 1)
  })
})
