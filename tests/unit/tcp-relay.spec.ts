import { describe, it, expect, afterEach } from 'vitest'
import { createServer, type Server, type Socket } from 'node:net'
import { createSocket } from 'node:dgram'
import { WebSocket } from 'ws'
import { createTcpRelay, type TcpRelay } from '../../scripts/tcp-relay'

// Real end-to-end check: a real `ws` client, a real relay, and a real
// TCP server standing in for the DAC — proves bytes actually cross the
// WebSocket<->TCP boundary in both directions, not just that the code
// compiles.

let relay: TcpRelay | null = null
let fakeDac: Server | null = null

afterEach(async () => {
  await relay?.close()
  relay = null
  await new Promise<void>((r) => (fakeDac ? fakeDac.close(() => r()) : r()))
  fakeDac = null
})

function findFreePort(): Promise<number> {
  return new Promise((resolveFree) => {
    const probe = createSocket('udp4')
    probe.bind(0, () => {
      const port = (probe.address() as { port: number }).port
      probe.close(() => resolveFree(port))
    })
  })
}

describe('tcp-relay', () => {
  it('forwards a WebSocket message to the TCP server, and the TCP reply back to the WebSocket client', async () => {
    const tcpPort = await findFreePort()
    const wsPort = await findFreePort()

    const dacReceived = new Promise<Buffer>((resolveReceived) => {
      fakeDac = createServer((socket: Socket) => {
        socket.on('data', (data) => {
          resolveReceived(data)
          socket.write(Buffer.from('ack-from-dac'))
        })
      })
      fakeDac.listen(tcpPort, '127.0.0.1')
    })
    await new Promise<void>((r) => fakeDac!.once('listening', r))

    relay = createTcpRelay({ wsPort, tcpHost: '127.0.0.1', tcpPort })

    const clientReceived = await new Promise<Buffer>((resolveClientReceived, reject) => {
      const ws = new WebSocket(`ws://127.0.0.1:${wsPort}`)
      ws.on('open', () => ws.send(Buffer.from('prepare-command')))
      ws.on('message', (data: Buffer) => {
        resolveClientReceived(data)
        ws.close()
      })
      ws.on('error', reject)
    })

    expect((await dacReceived).toString()).toBe('prepare-command')
    expect(clientReceived.toString()).toBe('ack-from-dac')
  })

  it('closes the WebSocket when the TCP connection closes', async () => {
    const tcpPort = await findFreePort()
    const wsPort = await findFreePort()

    fakeDac = createServer((socket: Socket) => {
      socket.end() // close immediately
    })
    fakeDac.listen(tcpPort, '127.0.0.1')
    await new Promise<void>((r) => fakeDac!.once('listening', r))

    relay = createTcpRelay({ wsPort, tcpHost: '127.0.0.1', tcpPort })

    await new Promise<void>((resolveClosed, reject) => {
      const ws = new WebSocket(`ws://127.0.0.1:${wsPort}`)
      ws.on('close', () => resolveClosed())
      ws.on('error', reject)
    })
  })
})
