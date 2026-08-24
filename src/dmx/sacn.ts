// sACN / E1.31 Data Packet encoder (real subset — DMX data packets only, no
// sync/discovery packets) — master-prompt.md §5's #3 priority protocol,
// alongside Art-Net. Reference: ANSI E1.31-2016 §4 (Data Packet framing:
// Root Layer -> Framing Layer -> DMP Layer). Sent over UDP, typically
// multicast to 239.255.<universe hi>.<universe lo> — see
// sacnMulticastAddress() below and docs/dmx-out.md.

export interface SacnDmxOptions {
  // 16-byte component identifier (a UUID) — stable per *sending component*
  // (i.e. per Hysteresis instance/session), not per packet or per universe.
  // Callers own generating/persisting this; the codec just places it.
  cid: Uint8Array
  // Human-readable source name, UTF-8, truncated to 63 bytes (the 64th is
  // always the null terminator/padding) if longer.
  sourceName: string
  // 0..200 (E1.31's data priority range), default 100 per spec.
  priority?: number
  // Wraps 0..255 — same duplicate/reorder-detection role as Art-Net's
  // sequence number, incrementing it every packet is the caller's job.
  sequence: number
  // 1..63999 per spec.
  universe: number
  // Up to 512 DMX channel values (0..255 each) — the DMX start code (0x00,
  // "no special meaning, plain DMX512-A data") is prepended by this
  // encoder, callers only ever supply channel data.
  data: Uint8Array
}

const ACN_PACKET_IDENTIFIER = new TextEncoder().encode('ASC-E1.17\0\0\0') // 12 bytes, per spec
const VECTOR_ROOT_E131_DATA = 0x00000004
const VECTOR_E131_DATA_PACKET = 0x00000002
const VECTOR_DMP_SET_PROPERTY = 0x02
const ADDRESS_AND_DATA_TYPE = 0xa1
const DMX_START_CODE = 0x00
const SOURCE_NAME_BYTES = 64

function flagsAndLength(length: number): number {
  // Top 4 bits are the ACN PDU flags nibble (0x7 = "length is 12-bit,
  // vector present, data present" — every layer here sets all three);
  // bottom 12 bits are the length itself (this field through the end of
  // the PDU, inclusive).
  return (0x7 << 12) | (length & 0x0fff)
}

export function encodeSacnDmx(opts: SacnDmxOptions): Uint8Array {
  const priority = opts.priority ?? 100
  const dmxData = opts.data.subarray(0, 512)
  const propertyValues = new Uint8Array(1 + dmxData.length)
  propertyValues[0] = DMX_START_CODE
  propertyValues.set(dmxData, 1)

  const dmpLength = 2 + 1 + 1 + 2 + 2 + 2 + propertyValues.length
  const framingLength = 2 + 4 + SOURCE_NAME_BYTES + 1 + 2 + 1 + 1 + 2 + dmpLength
  const rootLength = 2 + 4 + 16 + framingLength
  const totalLength = 2 + 2 + ACN_PACKET_IDENTIFIER.length + rootLength

  const buf = new Uint8Array(totalLength)
  const view = new DataView(buf.buffer)
  let offset = 0

  // Root Layer
  view.setUint16(offset, 0x0010, false)
  offset += 2 // Preamble Size
  view.setUint16(offset, 0x0000, false)
  offset += 2 // Post-amble Size
  buf.set(ACN_PACKET_IDENTIFIER, offset)
  offset += ACN_PACKET_IDENTIFIER.length
  view.setUint16(offset, flagsAndLength(rootLength), false)
  offset += 2
  view.setUint32(offset, VECTOR_ROOT_E131_DATA, false)
  offset += 4
  buf.set(opts.cid.subarray(0, 16), offset)
  offset += 16

  // Framing Layer
  view.setUint16(offset, flagsAndLength(framingLength), false)
  offset += 2
  view.setUint32(offset, VECTOR_E131_DATA_PACKET, false)
  offset += 4
  const nameBytes = new TextEncoder().encode(opts.sourceName).subarray(0, SOURCE_NAME_BYTES - 1)
  buf.set(nameBytes, offset) // remainder of the 64-byte field stays zero (Uint8Array default) — the spec's null-padding
  offset += SOURCE_NAME_BYTES
  view.setUint8(offset, priority)
  offset += 1
  view.setUint16(offset, 0, false)
  offset += 2 // Synchronization Address — 0, no sync used
  view.setUint8(offset, opts.sequence & 0xff)
  offset += 1
  view.setUint8(offset, 0)
  offset += 1 // Options — no preview/terminate/force-sync flags
  view.setUint16(offset, opts.universe & 0xffff, false)
  offset += 2

  // DMP Layer
  view.setUint16(offset, flagsAndLength(dmpLength), false)
  offset += 2
  view.setUint8(offset, VECTOR_DMP_SET_PROPERTY)
  offset += 1
  view.setUint8(offset, ADDRESS_AND_DATA_TYPE)
  offset += 1
  view.setUint16(offset, 0x0000, false)
  offset += 2 // First Property Address
  view.setUint16(offset, 0x0001, false)
  offset += 2 // Address Increment
  view.setUint16(offset, propertyValues.length, false)
  offset += 2 // Property Value Count
  buf.set(propertyValues, offset)

  return buf
}

// sACN's conventional transport: multicast to 239.255.<universe hi
// byte>.<universe lo byte> — a receiver (lighting console, TouchDesigner's
// sACN node) that "joins universe N" is listening on exactly this address,
// so a caller normally sends here rather than to a specific unicast host.
export function sacnMulticastAddress(universe: number): string {
  const u = universe & 0xffff
  return `239.255.${(u >> 8) & 0xff}.${u & 0xff}`
}
