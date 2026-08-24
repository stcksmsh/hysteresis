// Ether Dream laser DAC protocol — the live-streaming counterpart to
// ilda-format.ts's file format (master-prompt.md §5's "ILDA / laser DAC
// support," the "Bridge-mediated" real-time half). Ether Dream is the most
// widely used OPEN laser DAC protocol (the hardware/firmware behind many
// open-source laser projects) with an actually-published spec:
// https://ether-dream.com/protocol.html.
//
// Every field/offset/size below is cross-checked against TWO independent,
// real, maintained implementations (not just the spec page in isolation,
// since an initial AI-summarized read of that page got the DacStatus size
// wrong — 18 vs. the real 20 bytes — which this cross-check caught):
// - https://github.com/tgreiser/etherdream (Go) — dac.go/point.go/status.go
// - https://github.com/echelon/etherdream.rs (Rust) — src/protocol.rs
// Both agree on every constant used here EXCEPT the queue-rate-change
// command ('q'/0x71 below): neither reference implementation actually
// implements it (the Go one has an `Update` method using byte 'u' instead,
// with its own author's comment "Maybe this is the 'q' command now.",
// i.e. genuinely unsure) — that ONE command is real spec-page-only,
// unverified against a second source, unlike everything else here.
//
// ALL multi-byte fields are little-endian (unlike ILDA's file format
// above, which is big-endian — a real, confirmed difference between the
// two, not an inconsistency in this module).
//
// TCP (port 7765, one persistent connection per DAC) carries the actual
// command/point stream; UDP broadcast (port 7654) is DAC discovery/status.
// Browsers can do neither directly — see scripts/tcp-relay.ts for the
// relay this needs, the TCP analogue of udp-relay.ts's UDP forwarding.

export const ETHERDREAM_TCP_PORT = 7765
export const ETHERDREAM_UDP_BROADCAST_PORT = 7654

export interface DacStatus {
  protocol: number
  lightEngineState: number
  playbackState: number
  source: number
  lightEngineFlags: number
  playbackFlags: number
  sourceFlags: number
  bufferFullness: number
  pointRate: number
  pointCount: number
}

const DAC_STATUS_SIZE = 20

export function decodeDacStatus(bytes: Uint8Array, offset = 0): DacStatus {
  const view = new DataView(bytes.buffer, bytes.byteOffset + offset, DAC_STATUS_SIZE)
  return {
    protocol: view.getUint8(0),
    lightEngineState: view.getUint8(1),
    playbackState: view.getUint8(2),
    source: view.getUint8(3),
    lightEngineFlags: view.getUint16(4, true),
    playbackFlags: view.getUint16(6, true),
    sourceFlags: view.getUint16(8, true),
    bufferFullness: view.getUint16(10, true),
    pointRate: view.getUint32(12, true),
    pointCount: view.getUint32(16, true),
  }
}

export interface DacBroadcast {
  macAddress: Uint8Array // 6 bytes
  hwRevision: number
  swRevision: number
  bufferCapacity: number
  maxPointRate: number
  status: DacStatus
}

export function decodeDacBroadcast(bytes: Uint8Array): DacBroadcast {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  return {
    macAddress: bytes.subarray(0, 6),
    hwRevision: view.getUint16(6, true),
    swRevision: view.getUint16(8, true),
    bufferCapacity: view.getUint16(10, true),
    maxPointRate: view.getUint32(12, true),
    status: decodeDacStatus(bytes, 16),
  }
}

export interface DacResponse {
  response: number // 'a' (ACK), 'F' (buffer full/NAK), 'I' (invalid), or '!' (E-stop)
  command: number // echoes the command byte this responds to
  status: DacStatus
}

export function decodeDacResponse(bytes: Uint8Array): DacResponse {
  return { response: bytes[0], command: bytes[1], status: decodeDacStatus(bytes, 2) }
}

export const DAC_RESPONSE_ACK = 0x61 // 'a'
export const DAC_RESPONSE_BUFFER_FULL = 0x46 // 'F'
export const DAC_RESPONSE_INVALID = 0x49 // 'I'
export const DAC_RESPONSE_ESTOP = 0x21 // '!'

export interface DacPoint {
  control: number // bitfield — 0 is a normal lit/positioned point; no control bits are defined by this module's callers today
  x: number // -32768..32767
  y: number
  r: number // 0..65535 (16-bit color, unlike ILDA's 8-bit — a real protocol difference)
  g: number
  b: number
  i: number // intensity, independent of RGB
  u1: number // "user" channels — undefined meaning, DAC-specific
  u2: number
}

const DAC_POINT_SIZE = 18

export function encodeDacPoint(p: DacPoint): Uint8Array {
  const buf = new Uint8Array(DAC_POINT_SIZE)
  const view = new DataView(buf.buffer)
  view.setUint16(0, p.control, true)
  view.setInt16(2, p.x, true)
  view.setInt16(4, p.y, true)
  view.setUint16(6, p.r, true)
  view.setUint16(8, p.g, true)
  view.setUint16(10, p.b, true)
  view.setUint16(12, p.i, true)
  view.setUint16(14, p.u1, true)
  view.setUint16(16, p.u2, true)
  return buf
}

export function decodeDacPoint(bytes: Uint8Array, offset = 0): DacPoint {
  const view = new DataView(bytes.buffer, bytes.byteOffset + offset, DAC_POINT_SIZE)
  return {
    control: view.getUint16(0, true),
    x: view.getInt16(2, true),
    y: view.getInt16(4, true),
    r: view.getUint16(6, true),
    g: view.getUint16(8, true),
    b: view.getUint16(10, true),
    i: view.getUint16(12, true),
    u1: view.getUint16(14, true),
    u2: view.getUint16(16, true),
  }
}

// ---- Command encoders (single-byte commands are exported as plain
// constants — no encode function needed for a fixed one-byte message). ----
export const CMD_PREPARE_STREAM = 0x70 // 'p'
export const CMD_STOP = 0x73 // 's'
export const CMD_EMERGENCY_STOP = 0xff // NOT 0x00 — confirmed against both reference implementations (Go's EmergencyStop() sends "\xFF" specifically)
export const CMD_CLEAR_ESTOP = 0x63 // 'c'
export const CMD_PING = 0x3f // '?'

export function encodeBeginCommand(lowWaterMark: number, pointRate: number): Uint8Array {
  const buf = new Uint8Array(7)
  const view = new DataView(buf.buffer)
  buf[0] = 0x62 // 'b'
  view.setUint16(1, lowWaterMark, true)
  view.setUint32(3, pointRate, true)
  return buf
}

// LOWER CONFIDENCE than every other command in this file — see this
// module's header comment: neither reference implementation actually
// exercises a 'q' command, so this is spec-page-only. Confirm against a
// real DAC (or a newer spec revision) before depending on it.
export function encodeQueueRateChangeCommand(pointRate: number): Uint8Array {
  const buf = new Uint8Array(5)
  const view = new DataView(buf.buffer)
  buf[0] = 0x71 // 'q'
  view.setUint32(1, pointRate, true)
  return buf
}

export function encodeDataCommand(points: DacPoint[]): Uint8Array {
  const buf = new Uint8Array(3 + points.length * DAC_POINT_SIZE)
  const view = new DataView(buf.buffer)
  buf[0] = 0x64 // 'd'
  view.setUint16(1, points.length, true)
  points.forEach((p, i) => buf.set(encodeDacPoint(p), 3 + i * DAC_POINT_SIZE))
  return buf
}
