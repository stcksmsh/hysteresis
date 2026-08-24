#!/usr/bin/env node
import { createSocket, type Socket } from 'node:dgram'
import { WebSocketServer } from 'ws'

// A tiny local relay: browsers have no raw UDP API (master-prompt.md §3),
// so every WebSocket-based *-out bridge in this repo (OSC's
// src/osc/osc-out-bridge.ts, Art-Net/sACN's src/dmx/dmx-out-bridge.ts)
// needs something on the other end that CAN speak real UDP to an external
// tool (TouchDesigner, VCV Rack, Ableton, a lighting console). This is that
// something, generic across all of them by design — it does no
// protocol-specific encoding/decoding at all, just forwards bytes to UDP:
//
// - **Binary WebSocket frames** (OSC's `OscOutBridge` — a real, already-
//   encoded OSC packet) forward verbatim to this relay's own fixed
//   `--udp-host`/`--udp-port` destination, unmodified.
// - **Text (JSON) frames** (DMX's `DmxOutBridge`) are parsed as a small
//   `{ host, port, bytes: base64 }` envelope and forwarded to THAT
//   destination instead — needed because Art-Net/sACN address by universe
//   (broadcast/multicast, a different target per universe), unlike OSC's
//   one fixed relay target.
//
// This is a real, working seed of master-prompt.md §3/§8's "Hysteresis
// Bridge daemon" — but only the OSC/Art-Net/sACN slice of it. It does not
// speak DMX-serial or ILDA; those need real serial/DAC framing this simple
// byte-forwarder doesn't attempt.
export interface UdpRelayOptions {
  wsPort: number
  udpHost: string
  udpPort: number
}

export interface UdpRelay {
  wsPort: number
  close(): Promise<void>
}

interface DmxEnvelope {
  host: string
  port: number
  bytes: string
}

function isDmxEnvelope(value: unknown): value is DmxEnvelope {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return typeof v.host === 'string' && typeof v.port === 'number' && typeof v.bytes === 'string'
}

export function createUdpRelay(opts: UdpRelayOptions): UdpRelay {
  const udpSocket: Socket = createSocket('udp4')
  // Needed for Art-Net's broadcast fallback (DmxOutBridge defaults to
  // 255.255.255.255 when no specific node IP is configured) — Node refuses
  // to send to a broadcast address at all (EACCES) until this is set.
  // Harmless for OSC/sACN unicast/multicast sends, which don't need it.
  udpSocket.bind(() => udpSocket.setBroadcast(true))
  const wss = new WebSocketServer({ port: opts.wsPort })

  wss.on('connection', (ws) => {
    ws.on('message', (data: Buffer, isBinary: boolean) => {
      if (!isBinary) {
        // A JSON envelope (DMX) — malformed/unparseable text is dropped
        // silently rather than crashing the relay process over one bad
        // message from a browser tab that could reconnect and retry.
        let parsed: unknown
        try {
          parsed = JSON.parse(data.toString('utf-8'))
        } catch {
          return
        }
        if (!isDmxEnvelope(parsed)) return
        udpSocket.send(Buffer.from(parsed.bytes, 'base64'), parsed.port, parsed.host)
        return
      }
      udpSocket.send(data, opts.udpPort, opts.udpHost)
    })
  })

  return {
    wsPort: opts.wsPort,
    close(): Promise<void> {
      return new Promise((resolveClose) => {
        udpSocket.close()
        wss.close(() => resolveClose())
        for (const client of wss.clients) client.terminate()
      })
    },
  }
}

function main(): void {
  const args = process.argv.slice(2)
  const flag = (name: string, fallback: string) => {
    const i = args.indexOf(`--${name}`)
    return i !== -1 && args[i + 1] ? args[i + 1] : fallback
  }
  const wsPort = Number(flag('ws-port', '9090'))
  const udpHost = flag('udp-host', '127.0.0.1')
  const udpPort = Number(flag('udp-port', '9000'))

  createUdpRelay({ wsPort, udpHost, udpPort })
  console.log(`udp-relay: ws://localhost:${wsPort} -> udp://${udpHost}:${udpPort} (default target — OSC binary frames only; DMX JSON envelopes carry their own per-universe destination)`)
  console.log('usage: npm run udp-relay -- --ws-port 9090 --udp-host 127.0.0.1 --udp-port 9000')
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
