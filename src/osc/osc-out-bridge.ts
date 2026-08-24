import type { SignalBus } from '../render/conductor/types'
import { encodeOscBundle } from './osc-codec'
import { signalBusToOscMessages } from './bus-to-osc'

export interface OscOutStatus {
  connected: boolean
  message?: string
}

// Runs inside the render worker (WebSocket is available in a dedicated
// Worker's global scope, same as in a window) — sends the signal bus out as
// a real OSC bundle over a WebSocket connection. Browsers have no raw UDP
// API at all (master-prompt.md §3's core architecture reasoning — this is
// the same gap Art-Net/DMX/ILDA all hit), so real OSC-over-UDP interop with
// something like TouchDesigner/VCV Rack needs a tiny local relay on the
// other end of that WebSocket (see scripts/udp-relay.ts) — this class only
// owns the browser-reachable half of that path.
// How long to wait before retrying a dropped connection — matches
// index.ts's own AUDIO_POLL_INTERVAL_MS philosophy for an optional
// external connection: keep retrying indefinitely rather than giving up
// after N attempts, since the host (or a relay process being restarted)
// may reconnect at any time and there's no natural "stop trying" point
// short of the host calling disconnect() itself.
const RECONNECT_DELAY_MS = 2000

export class OscOutBridge {
  private ws: WebSocket | null = null
  private reconnectHandle: ReturnType<typeof setTimeout> | null = null
  private lastUrl: string | null = null
  // Distinguishes "the host called disconnect()" from "the socket dropped
  // on its own" — only the latter should trigger a reconnect attempt.
  private explicitlyDisconnected = false

  constructor(private onStatus?: (status: OscOutStatus) => void) {}

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
      this.ws = ws
    } catch (err) {
      this.onStatus?.({ connected: false, message: err instanceof Error ? err.message : String(err) })
      this.scheduleReconnect()
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

  // No-op (not an error) when the socket isn't open yet/anymore — this is
  // called every frame from the render loop's throttled tick, so a
  // reconnect-in-progress or a host that never called connect() must not
  // throw or log noise here.
  send(bus: SignalBus): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
    this.ws.send(encodeOscBundle(signalBusToOscMessages(bus)))
  }
}
