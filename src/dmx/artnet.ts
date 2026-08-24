// Art-Net 4 ArtDMX packet encoder (real subset — DMX output only, no
// ArtPoll/ArtSync/etc.) — master-prompt.md §5's #3 priority protocol
// ("network DMX — most common in modern lighting rigs"). Reference:
// https://art-net.org.uk/resources/art-net-specification/ §ArtDmx.
// Sent over UDP (browsers have no raw UDP — see docs/osc.md's relay
// pattern, reused as-is here, this module just produces the bytes).
export interface ArtDmxOptions {
  // 0..32767 (15-bit Port-Address = Net(7 bits) | Sub-Net(4 bits) |
  // Universe(4 bits), packed by this encoder — callers pass the whole
  // combined port-address, matching how Art-Net-speaking software
  // (lighting consoles, TouchDesigner's Art-Net node) usually expose it).
  universe: number
  // Wraps 0..255; the spec makes this the receiver's duplicate/reorder
  // detection field, incrementing it every packet is the caller's job
  // (ArtNetOutBridge does this).
  sequence: number
  // Input port this data notionally came from — 0 unless multiple DMX
  // ports on one physical node need distinguishing, which nothing in this
  // codebase does today.
  physical?: number
  // Up to 512 DMX channel values (0..255 each). Art-Net requires an EVEN
  // length of at least 2 — see ARTDMX_MIN_LENGTH's comment.
  data: Uint8Array
}

const ARTNET_ID = [0x41, 0x72, 0x74, 0x2d, 0x4e, 0x65, 0x74, 0x00] // "Art-Net\0"
const OPCODE_ARTDMX = 0x5000
const PROTOCOL_VERSION = 14
// Per spec, ArtDmx's data length must be even and at least 2 — pad a lone
// odd/short universe rather than reject it (a fixture set that happens to
// use an odd channel count, e.g. one RGB fixture at 3 channels, is common
// and shouldn't need the caller to think about this padding rule).
const ARTDMX_MIN_LENGTH = 2

export function encodeArtDmx(opts: ArtDmxOptions): Uint8Array {
  const universe = opts.universe & 0x7fff
  const subUni = universe & 0xff // Sub-Net (high nibble) | Universe (low nibble)
  const net = (universe >> 8) & 0x7f

  let length = opts.data.length
  if (length < ARTDMX_MIN_LENGTH) length = ARTDMX_MIN_LENGTH
  if (length % 2 !== 0) length += 1

  const buf = new Uint8Array(18 + length)
  buf.set(ARTNET_ID, 0)
  const view = new DataView(buf.buffer)
  view.setUint16(8, OPCODE_ARTDMX, true) // little-endian, per spec
  view.setUint8(10, 0) // ProtVerHi
  view.setUint8(11, PROTOCOL_VERSION) // ProtVerLo — big-endian 16-bit value, low byte carries it
  view.setUint8(12, opts.sequence & 0xff)
  view.setUint8(13, opts.physical ?? 0)
  view.setUint8(14, subUni)
  view.setUint8(15, net)
  view.setUint16(16, length, false) // big-endian
  buf.set(opts.data.subarray(0, length), 18)
  return buf
}
