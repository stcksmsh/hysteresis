import { decodeOscPacket, type OscArg, type OscBundle, type OscMessage } from './osc-codec'

export interface OscInStatus {
  connected: boolean
  message?: string
}

// Only float/int/bool coerce to a number a patch graph node can actually
// carry — a string argument has no sane numeric value, so the message is
// dropped rather than guessing (e.g. `parseFloat` on an arbitrary string
// would silently misroute a real string-typed control like an OSC address
// pattern or a text label some tool happens to send on the same address).
function argToNumber(arg: OscArg): number | null {
  switch (arg.type) {
    case 'f':
    case 'i':
      return arg.value
    case 'T':
      return 1
    case 'F':
      return 0
    case 's':
      return null
  }
}

function collectMessages(packet: OscMessage | OscBundle, out: OscMessage[] = []): OscMessage[] {
  if (packet.kind === 'message') {
    out.push(packet)
    return out
  }
  for (const element of packet.elements) collectMessages(element, out)
  return out
}

// Same reconnect-forever posture as OscOutBridge — an optional external
// connection with no natural "give up" point short of the host calling
// disconnect() itself.
const RECONNECT_DELAY_MS = 2000

// The "OSC in" half of master-prompt.md §5's OSC entry (out has existed
// since the ISF/OSC session) — receives real inbound OSC packets a relay
// (scripts/udp-relay.ts's --osc-in-port) forwards from the network over a
// WebSocket, decodes them, and stores each message's own first numeric-ish
// argument keyed by OSC address (see argToNumber's own doc comment for why
// a string-typed argument is dropped rather than coerced). Pull-only, same
// contract as MidiCcInput's own get() — a patch graph's oscIn node reads
// whatever's currently stored once per frame; it never sees individual
// messages arrive.
export class OscInBridge {
  private ws: WebSocket | null = null
  private reconnectHandle: ReturnType<typeof setTimeout> | null = null
  private lastUrl: string | null = null
  private explicitlyDisconnected = false
  readonly values = new Map<string, number>()

  constructor(
    private onStatus?: (status: OscInStatus) => void,
    // Optional observability hook, fired on every real inbound message —
    // same purely-additive role as MidiCcInput's own onChange (e.g. a live
    // "recent OSC activity" debug panel), not needed for routing itself
    // (`get()`/`values` are enough for that).
    private onMessage?: (address: string, value: number) => void,
  ) {}

  connect(url: string): void {
    this.disconnect()
    this.explicitlyDisconnected = false
    this.lastUrl = url
    this.openSocket(url)
  }

  private openSocket(url: string): void {
    try {
      const ws = new WebSocket(url)
      ws.binaryType = 'arraybuffer'
      ws.onopen = () => this.onStatus?.({ connected: true })
      ws.onclose = () => {
        this.onStatus?.({ connected: false })
        this.scheduleReconnect()
      }
      ws.onerror = () => this.onStatus?.({ connected: false, message: 'WebSocket error' })
      ws.onmessage = (e) => this.handleFrame(e.data)
      this.ws = ws
    } catch (err) {
      this.onStatus?.({ connected: false, message: err instanceof Error ? err.message : String(err) })
      this.scheduleReconnect()
    }
  }

  private handleFrame(data: unknown): void {
    // The relay only ever forwards inbound OSC as binary frames (see its
    // own doc comment) — a text frame here would mean something else is
    // talking to this socket, silently ignored rather than crashing.
    if (!(data instanceof ArrayBuffer)) return
    let packet: OscMessage | OscBundle
    try {
      packet = decodeOscPacket(new Uint8Array(data))
    } catch {
      // A malformed packet from the network (a non-OSC sender pointed at
      // the relay's inbound port, a partial/corrupt UDP datagram) must not
      // take the connection down — drop it and keep listening.
      return
    }
    for (const msg of collectMessages(packet)) {
      const value = msg.args.length > 0 ? argToNumber(msg.args[0]) : null
      if (value === null) continue
      this.values.set(msg.address, value)
      this.onMessage?.(msg.address, value)
    }
  }

  private scheduleReconnect(): void {
    if (this.explicitlyDisconnected || this.reconnectHandle !== null || !this.lastUrl) return
    this.reconnectHandle = setTimeout(() => {
      this.reconnectHandle = null
      if (!this.explicitlyDisconnected && this.lastUrl) this.openSocket(this.lastUrl)
    }, RECONNECT_DELAY_MS)
  }

  disconnect(): void {
    this.explicitlyDisconnected = true
    if (this.reconnectHandle !== null) {
      clearTimeout(this.reconnectHandle)
      this.reconnectHandle = null
    }
    this.ws?.close()
    this.ws = null
  }

  get(address: string): number {
    return this.values.get(address) ?? 0
  }
}
