#!/usr/bin/env node
import { connect as tcpConnect, type Socket } from 'node:net'
import { WebSocketServer, type WebSocket } from 'ws'

// The TCP analogue of udp-relay.ts, needed for Ether Dream
// (src/ilda/ether-dream.ts) — a laser DAC's actual point/command stream
// rides one persistent TCP connection with bidirectional traffic (the DAC
// ACKs every command), unlike Art-Net/sACN/OSC/WLED's fire-and-forget UDP
// datagrams. Browsers can't open raw TCP sockets any more than raw UDP
// ones, so this duplexes: bytes sent over the WebSocket go out on the TCP
// connection, and bytes that arrive back over TCP (the DAC's responses)
// go back out over the WebSocket. It does no protocol interpretation at
// all — same "dumb forwarder" philosophy as udp-relay.ts — the actual
// Ether Dream command/response state machine lives entirely in the
// browser-side client code, which just sees a duplex byte stream.
//
// One WebSocket connection = one TCP connection to one fixed DAC (the
// `--tcp-host`/`--tcp-port` this process is started with) — unlike
// udp-relay.ts, which can fan out to a different destination per message
// (Art-Net/sACN/WLED all need that; a single Ether Dream session doesn't).
export interface TcpRelayOptions {
  wsPort: number
  tcpHost: string
  tcpPort: number
}

export interface TcpRelay {
  wsPort: number
  close(): Promise<void>
}

export function createTcpRelay(opts: TcpRelayOptions): TcpRelay {
  const wss = new WebSocketServer({ port: opts.wsPort })
  const sockets = new Set<Socket>()

  wss.on('connection', (ws: WebSocket) => {
    const socket = tcpConnect({ host: opts.tcpHost, port: opts.tcpPort })
    sockets.add(socket)

    socket.on('data', (data: Buffer) => {
      if (ws.readyState === ws.OPEN) ws.send(data)
    })
    socket.on('error', (err) => {
      if (ws.readyState === ws.OPEN) ws.close(1011, err.message.slice(0, 123)) // WS close reason is capped at 123 UTF-8 bytes
    })
    socket.on('close', () => {
      sockets.delete(socket)
      if (ws.readyState === ws.OPEN) ws.close()
    })

    ws.on('message', (data: Buffer) => {
      socket.write(data)
    })
    ws.on('close', () => {
      socket.destroy()
      sockets.delete(socket)
    })
  })

  return {
    wsPort: opts.wsPort,
    close(): Promise<void> {
      return new Promise((resolveClose) => {
        for (const socket of sockets) socket.destroy()
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
  const wsPort = Number(flag('ws-port', '9091'))
  const tcpHost = flag('tcp-host', '192.168.1.100')
  const tcpPort = Number(flag('tcp-port', '7765'))

  createTcpRelay({ wsPort, tcpHost, tcpPort })
  console.log(`tcp-relay: ws://localhost:${wsPort} <-> tcp://${tcpHost}:${tcpPort}`)
  console.log('usage: npm run tcp-relay -- --ws-port 9091 --tcp-host 192.168.1.100 --tcp-port 7765')
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
