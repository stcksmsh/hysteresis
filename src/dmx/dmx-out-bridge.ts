import { encodeArtDmx } from './artnet'
import { encodeSacnDmx, sacnMulticastAddress } from './sacn'
import { encodeWledDrgb, WLED_DEFAULT_PORT } from './wled'

export type DmxProtocol = 'artnet' | 'sacn' | 'wled-drgb'

export interface DmxOutStatus {
  connected: boolean
  message?: string
}

export interface DmxOutOptions {
  protocol: DmxProtocol
  // sACN only — a stable per-source identifier + display name (see
  // sacn.ts's SacnDmxOptions doc comment). Ignored for Art-Net.
  sacnCid?: Uint8Array
  sacnSourceName?: string
}

// The relay side of this (scripts/udp-relay.ts) forwards whatever bytes
// arrive over the WebSocket straight to UDP, unmodified — so unlike
// OscOutBridge, THIS class has to tell the relay which destination to use
// per packet, since Art-Net/sACN both address *by universe*, not a single
// fixed host:port the way OSC's one relay target was. Encoded as a small
// JSON envelope: `{ host, port, bytes: <base64> }`. This means the relay
// needs the small envelope-aware variant, not the byte-passthrough default
// — see docs/dmx-out.md for exactly which relay flag that is.
export interface DmxRelayEnvelope {
  host: string
  port: number
  bytes: string // base64
}

const ARTNET_PORT = 6454
const SACN_PORT = 5568

function toBase64(bytes: Uint8Array): string {
  let binary = ''
  for (const b of bytes) binary += String.fromCharCode(b)
  return btoa(binary)
}

export class DmxOutBridge {
  private ws: WebSocket | null = null
  private sequence = 0

  constructor(
    private opts: DmxOutOptions,
    private onStatus?: (status: DmxOutStatus) => void,
  ) {}

  connect(url: string): void {
    this.disconnect()
    try {
      const ws = new WebSocket(url)
      ws.onopen = () => this.onStatus?.({ connected: true })
      ws.onclose = () => this.onStatus?.({ connected: false })
      ws.onerror = () => this.onStatus?.({ connected: false, message: 'WebSocket error' })
      this.ws = ws
    } catch (err) {
      this.onStatus?.({ connected: false, message: err instanceof Error ? err.message : String(err) })
    }
  }

  disconnect(): void {
    this.ws?.close()
    this.ws = null
  }

  // `universeHost` (optional for artnet/sacn, REQUIRED for wled-drgb) —
  // Art-Net falls back to the local broadcast address (255.255.255.255,
  // the spec's own default discovery-free behavior) and sACN falls back to
  // its standard per-universe multicast group (sacnMulticastAddress); WLED
  // has no such broadcast/multicast convention at all — it's always one
  // specific device's own IP, so a universe with no host given is silently
  // skipped rather than guessing a destination that could be a completely
  // unrelated device on the network.
  //
  // For wled-drgb, each universe's 512-byte buffer is reused verbatim as a
  // sequential RGB pixel stream — this only produces a sane result if the
  // patched `rgb`-type fixtures in that universe start at address 1 and
  // are contiguous (see render-dmx-universe.ts and docs/dmx-out.md);
  // there's no DMX-universe *concept* on the WLED side at all, "universe"
  // here is just this bridge's existing per-destination grouping reused.
  send(universes: Map<number, Uint8Array>, universeHost?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
    this.sequence = (this.sequence + 1) & 0xff

    for (const [universe, data] of universes) {
      if (this.opts.protocol === 'wled-drgb') {
        if (!universeHost) continue
        const envelope: DmxRelayEnvelope = { host: universeHost, port: WLED_DEFAULT_PORT, bytes: toBase64(encodeWledDrgb(data)) }
        this.ws.send(JSON.stringify(envelope))
        continue
      }

      const bytes =
        this.opts.protocol === 'artnet'
          ? encodeArtDmx({ universe, sequence: this.sequence, data })
          : encodeSacnDmx({
              universe,
              sequence: this.sequence,
              data,
              cid: this.opts.sacnCid ?? new Uint8Array(16),
              sourceName: this.opts.sacnSourceName ?? 'Hysteresis',
            })
      const host = universeHost ?? (this.opts.protocol === 'artnet' ? '255.255.255.255' : sacnMulticastAddress(universe))
      const port = this.opts.protocol === 'artnet' ? ARTNET_PORT : SACN_PORT
      const envelope: DmxRelayEnvelope = { host, port, bytes: toBase64(bytes) }
      this.ws.send(JSON.stringify(envelope))
    }
  }
}
