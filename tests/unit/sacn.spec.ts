import { describe, it, expect } from 'vitest'
import { encodeSacnDmx, sacnMulticastAddress } from '../../src/dmx/sacn'

const CID = new Uint8Array(16).map((_, i) => i)

describe('encodeSacnDmx', () => {
  it('writes the ACN packet identifier at the expected root-layer offset', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'Hysteresis', sequence: 1, universe: 1, data: new Uint8Array(3) })
    // Preamble(2) + Post-amble(2) = offset 4 for the 12-byte ACN ID.
    const id = new TextDecoder().decode(bytes.subarray(4, 16))
    expect(id).toBe('ASC-E1.17\0\0\0')
  })

  it('writes the root vector (VECTOR_ROOT_E131_DATA = 4) after the CID field position', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', sequence: 1, universe: 1, data: new Uint8Array(1) })
    // offset 16: flags&length(2), then root vector at 18..21
    const view = new DataView(bytes.buffer)
    expect(view.getUint32(18, false)).toBe(4)
  })

  it('writes the CID verbatim at its root-layer offset (22)', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', sequence: 1, universe: 1, data: new Uint8Array(1) })
    expect(Array.from(bytes.subarray(22, 38))).toEqual(Array.from(CID));
  })

  it('writes the framing vector (VECTOR_E131_DATA_PACKET = 2) right after the CID', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', sequence: 1, universe: 1, data: new Uint8Array(1) })
    const view = new DataView(bytes.buffer)
    // offset 38: framing flags&length(2), then vector at 40..43
    expect(view.getUint32(40, false)).toBe(2)
  })

  it('writes and null-pads the source name into the 64-byte field', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'Hysteresis', sequence: 1, universe: 1, data: new Uint8Array(1) })
    const nameField = bytes.subarray(44, 44 + 64)
    const decoded = new TextDecoder().decode(nameField.subarray(0, 'Hysteresis'.length))
    expect(decoded).toBe('Hysteresis')
    expect(nameField[63]).toBe(0) // last byte of the fixed field is null padding
  })

  it('writes priority, sequence, and universe at their framing-layer offsets', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', priority: 150, sequence: 77, universe: 42, data: new Uint8Array(1) })
    // 44 (name start) + 64 (name field) = 108: priority(1), syncAddr(2), sequence(1), options(1), universe(2)
    expect(bytes[108]).toBe(150) // priority
    const view = new DataView(bytes.buffer)
    expect(view.getUint16(109, false)).toBe(0) // sync address
    expect(bytes[111]).toBe(77) // sequence
    expect(bytes[112]).toBe(0) // options
    expect(view.getUint16(113, false)).toBe(42) // universe
  })

  it('defaults priority to 100 when omitted', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', sequence: 1, universe: 1, data: new Uint8Array(1) })
    expect(bytes[108]).toBe(100)
  })

  it('prepends the DMX start code (0x00) and carries the channel data verbatim', () => {
    const data = new Uint8Array([10, 20, 30])
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', sequence: 1, universe: 1, data })
    // DMP layer starts at offset 115: flags&len(2), vector(1), addrType(1), firstProp(2), increment(2), count(2) = 10 bytes -> property values at 125
    expect(bytes[125]).toBe(0) // DMX start code
    expect(Array.from(bytes.subarray(126, 129))).toEqual([10, 20, 30])
  })

  it('produces a total length consistent with a 512-channel universe', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', sequence: 1, universe: 1, data: new Uint8Array(512) })
    // 125 bytes of header/layers + 1 start code + 512 channels
    expect(bytes.byteLength).toBe(125 + 1 + 512)
  })

  it('truncates data longer than 512 channels', () => {
    const bytes = encodeSacnDmx({ cid: CID, sourceName: 'x', sequence: 1, universe: 1, data: new Uint8Array(600) })
    expect(bytes.byteLength).toBe(125 + 1 + 512)
  })
})

describe('sacnMulticastAddress', () => {
  it('computes 239.255.<hi>.<lo> from the universe number', () => {
    expect(sacnMulticastAddress(1)).toBe('239.255.0.1')
    expect(sacnMulticastAddress(256)).toBe('239.255.1.0')
    expect(sacnMulticastAddress(63999)).toBe('239.255.249.255')
  })
})
