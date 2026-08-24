// A real OSC 1.0 wire-format codec (https://opensoundcontrol.stanford.edu/spec-1_0.html)
// — master-prompt.md §4.3/§6's "OSC-compatible addressing scheme" backlog
// item needs actual byte-level OSC, not just an address-naming convention,
// since the whole point is interop with real external tools (Ableton,
// TouchDesigner, VCV Rack) that speak the wire format, not this codebase.
// Deliberately a real subset, same policy as src/isf/parse-isf.ts: only the
// argument types the signal bus actually needs (float32, int32, string,
// bool) are implemented, and only what's implemented is claimed to work.

export type OscArg = { type: 'f'; value: number } | { type: 'i'; value: number } | { type: 's'; value: string } | { type: 'T' } | { type: 'F' }

export interface OscMessage {
  kind: 'message'
  address: string
  args: OscArg[]
}

export interface OscBundle {
  kind: 'bundle'
  // OSC's 64-bit NTP time tag. `1n` is the spec's reserved "immediately"
  // value — the only time semantics this codec needs (SignalBus values are
  // already "now", there's no scheduling use case here).
  timeTag: bigint
  elements: (OscMessage | OscBundle)[]
}

// OSC strings are null-terminated ASCII, then zero-padded so the total
// (including the terminator) is a multiple of 4 bytes.
function oscStringByteLength(str: string): number {
  const len = str.length + 1 // + null terminator
  return len + ((4 - (len % 4)) % 4)
}

function writeOscString(view: DataView, offset: number, str: string): number {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i) & 0x7f)
  const len = oscStringByteLength(str)
  for (let i = str.length; i < len; i++) view.setUint8(offset + i, 0)
  return offset + len
}

function readOscString(view: DataView, offset: number): { value: string; next: number } {
  let end = offset
  while (end < view.byteLength && view.getUint8(end) !== 0) end++
  const bytes = new Uint8Array(view.buffer, view.byteOffset + offset, end - offset)
  const value = String.fromCharCode(...bytes)
  const len = oscStringByteLength(value)
  return { value, next: offset + len }
}

function argByteLength(arg: OscArg): number {
  switch (arg.type) {
    case 'f':
    case 'i':
      return 4
    case 's':
      return oscStringByteLength(arg.value)
    case 'T':
    case 'F':
      return 0
  }
}

export function encodeOscMessage(address: string, args: OscArg[]): Uint8Array {
  const typeTag = ',' + args.map((a) => a.type).join('')
  const totalLen = oscStringByteLength(address) + oscStringByteLength(typeTag) + args.reduce((sum, a) => sum + argByteLength(a), 0)
  const buf = new ArrayBuffer(totalLen)
  const view = new DataView(buf)
  let offset = writeOscString(view, 0, address)
  offset = writeOscString(view, offset, typeTag)
  for (const arg of args) {
    switch (arg.type) {
      case 'f':
        view.setFloat32(offset, arg.value, false)
        offset += 4
        break
      case 'i':
        view.setInt32(offset, Math.round(arg.value), false)
        offset += 4
        break
      case 's':
        offset = writeOscString(view, offset, arg.value)
        break
      case 'T':
      case 'F':
        break // no bytes — the type tag itself carries the value
    }
  }
  return new Uint8Array(buf)
}

// OSC bundle: "#bundle\0" + 8-byte time tag + repeated (int32 size + element
// bytes). `1n` (the spec's "now") is what every caller in this codebase
// actually needs — see OscBundle's own doc comment.
export function encodeOscBundle(messages: { address: string; args: OscArg[] }[], timeTag = 1n): Uint8Array {
  const encoded = messages.map((m) => encodeOscMessage(m.address, m.args))
  const headerLen = oscStringByteLength('#bundle') + 8
  const bodyLen = encoded.reduce((sum, m) => sum + 4 + m.byteLength, 0)
  const buf = new ArrayBuffer(headerLen + bodyLen)
  const view = new DataView(buf)
  let offset = writeOscString(view, 0, '#bundle')
  view.setBigUint64(offset, timeTag, false)
  offset += 8
  for (const m of encoded) {
    view.setInt32(offset, m.byteLength, false)
    offset += 4
    new Uint8Array(buf, offset, m.byteLength).set(m)
    offset += m.byteLength
  }
  return new Uint8Array(buf)
}

export function decodeOscPacket(bytes: Uint8Array): OscMessage | OscBundle {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const { value: first } = readOscString(view, 0)
  return first === '#bundle' ? decodeOscBundle(view) : decodeOscMessage(view)
}

function decodeOscMessage(view: DataView): OscMessage {
  const { value: address, next: afterAddress } = readOscString(view, 0)
  const { value: typeTag, next: afterTypeTag } = readOscString(view, afterAddress)
  if (!typeTag.startsWith(',')) throw new Error(`OSC message has no type tag string (got "${typeTag}")`)
  let offset = afterTypeTag
  const args: OscArg[] = []
  for (const t of typeTag.slice(1)) {
    switch (t) {
      case 'f':
        args.push({ type: 'f', value: view.getFloat32(offset, false) })
        offset += 4
        break
      case 'i':
        args.push({ type: 'i', value: view.getInt32(offset, false) })
        offset += 4
        break
      case 's': {
        const { value, next } = readOscString(view, offset)
        args.push({ type: 's', value })
        offset = next
        break
      }
      case 'T':
        args.push({ type: 'T' })
        break
      case 'F':
        args.push({ type: 'F' })
        break
      default:
        throw new Error(`Unsupported OSC argument type tag: "${t}"`)
    }
  }
  return { kind: 'message', address, args }
}

function decodeOscBundle(view: DataView): OscBundle {
  const { next: afterHeader } = readOscString(view, 0) // "#bundle"
  const timeTag = view.getBigUint64(afterHeader, false)
  let offset = afterHeader + 8
  const elements: (OscMessage | OscBundle)[] = []
  while (offset < view.byteLength) {
    const size = view.getInt32(offset, false)
    offset += 4
    const elementBytes = new Uint8Array(view.buffer, view.byteOffset + offset, size)
    elements.push(decodeOscPacket(elementBytes))
    offset += size
  }
  return { kind: 'bundle', timeTag, elements }
}
