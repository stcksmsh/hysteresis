import { describe, it, expect, afterEach } from 'vitest'
import { createSocket, type Socket } from 'node:dgram'
import { WebSocket } from 'ws'
import { createUdpRelay, type UdpRelay } from '../../scripts/udp-relay'
import { encodeOscBundle } from '../../src/osc/osc-codec'
import { encodeArtDmx } from '../../src/dmx/artnet'
import type { DmxRelayEnvelope } from '../../src/dmx/dmx-out-bridge'

// Real end-to-end checks, not mocks: a real `ws` client, a real relay bound
// to ephemeral ports, and a real loopback UDP socket on the receiving end.

let relay: UdpRelay | null = null
let udpSocket: Socket | null = null

afterEach(async () => {
  udpSocket?.close()
  udpSocket = null
  await relay?.close()
  relay = null
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

async function sendOverWs(wsPort: number, payload: Buffer | string): Promise<void> {
  await new Promise<void>((resolveOpen, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${wsPort}`)
    ws.on('open', () => {
      ws.send(payload)
      ws.close()
      resolveOpen()
    })
    ws.on('error', reject)
  })
}

describe('udp-relay', () => {
  it('forwards a binary WebSocket frame to the fixed default UDP destination unchanged (OSC path)', async () => {
    const wsPort = await findFreePort()
    const udpPort = await findFreePort()
    relay = createUdpRelay({ wsPort, udpHost: '127.0.0.1', udpPort })

    const received = new Promise<Buffer>((resolveReceived) => {
      udpSocket = createSocket('udp4')
      udpSocket.on('message', (msg) => resolveReceived(msg))
      udpSocket.bind(udpPort, '127.0.0.1')
    })

    const sentBytes = encodeOscBundle([{ address: '/hysteresis/bus/energy', args: [{ type: 'f', value: 0.42 }] }])
    await sendOverWs(wsPort, Buffer.from(sentBytes))

    const receivedBytes = await received
    expect(Buffer.from(receivedBytes)).toEqual(Buffer.from(sentBytes))
  })

  it('forwards a JSON envelope text frame to ITS OWN host:port, distinct per message (DMX path)', async () => {
    const wsPort = await findFreePort()
    const udpPortA = await findFreePort()
    const udpPortB = await findFreePort()
    relay = createUdpRelay({ wsPort, udpHost: '127.0.0.1', udpPort: 1 }) // deliberately wrong default — envelopes must override it

    const receivedA = new Promise<Buffer>((resolveReceived) => {
      const s = createSocket('udp4')
      s.on('message', (msg) => resolveReceived(msg))
      s.bind(udpPortA, '127.0.0.1')
    })
    const receivedB = new Promise<Buffer>((resolveReceived) => {
      const s = createSocket('udp4')
      s.on('message', (msg) => resolveReceived(msg))
      s.bind(udpPortB, '127.0.0.1')
    })

    const packetA = encodeArtDmx({ universe: 1, sequence: 1, data: new Uint8Array([1, 2]) })
    const packetB = encodeArtDmx({ universe: 2, sequence: 1, data: new Uint8Array([3, 4]) })
    const envelopeA: DmxRelayEnvelope = { host: '127.0.0.1', port: udpPortA, bytes: Buffer.from(packetA).toString('base64') }
    const envelopeB: DmxRelayEnvelope = { host: '127.0.0.1', port: udpPortB, bytes: Buffer.from(packetB).toString('base64') }

    await sendOverWs(wsPort, JSON.stringify(envelopeA))
    await sendOverWs(wsPort, JSON.stringify(envelopeB))

    expect(Buffer.from(await receivedA)).toEqual(Buffer.from(packetA))
    expect(Buffer.from(await receivedB)).toEqual(Buffer.from(packetB))
  })

  it('forwards an inbound UDP datagram to a connected WS client unchanged (OSC in path)', async () => {
    const wsPort = await findFreePort()
    const oscInPort = await findFreePort()
    relay = createUdpRelay({ wsPort, udpHost: '127.0.0.1', udpPort: 1, oscInPort })

    const sentBytes = encodeOscBundle([{ address: '/1/fader1', args: [{ type: 'f', value: 0.65 }] }])

    const received = await new Promise<Buffer>((resolveReceived, reject) => {
      const ws = new WebSocket(`ws://127.0.0.1:${wsPort}`)
      ws.binaryType = 'arraybuffer'
      ws.on('open', () => {
        const sender = createSocket('udp4')
        sender.send(Buffer.from(sentBytes), oscInPort, '127.0.0.1', (err) => {
          if (err) reject(err)
          sender.close()
        })
      })
      ws.on('message', (data) => resolveReceived(Buffer.from(data as Buffer)))
      ws.on('error', reject)
    })

    expect(received).toEqual(Buffer.from(sentBytes))
  })

  it('never opens an inbound socket when oscInPort is omitted (pre-existing out-only behavior unchanged)', async () => {
    const wsPort = await findFreePort()
    relay = createUdpRelay({ wsPort, udpHost: '127.0.0.1', udpPort: 1 })
    expect(relay.oscInPort).toBeNull()
  })

  it('drops a malformed JSON text frame without crashing the relay', async () => {
    const wsPort = await findFreePort()
    relay = createUdpRelay({ wsPort, udpHost: '127.0.0.1', udpPort: 1 })
    await expect(sendOverWs(wsPort, 'not json at all')).resolves.toBeUndefined()
    // Relay is still alive: a subsequent well-formed message still works.
    const udpPort = await findFreePort()
    const received = new Promise<Buffer>((resolveReceived) => {
      udpSocket = createSocket('udp4')
      udpSocket.on('message', (msg) => resolveReceived(msg))
      udpSocket.bind(udpPort, '127.0.0.1')
    })
    const envelope: DmxRelayEnvelope = { host: '127.0.0.1', port: udpPort, bytes: Buffer.from([1, 2, 3]).toString('base64') }
    await sendOverWs(wsPort, JSON.stringify(envelope))
    expect(Array.from(await received)).toEqual([1, 2, 3])
  })
})
