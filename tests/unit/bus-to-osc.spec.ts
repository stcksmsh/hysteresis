import { describe, it, expect } from 'vitest'
import { signalBusToOscMessages, OSC_BUS_ADDRESS_PREFIX } from '../../src/osc/bus-to-osc'
import { SIGNAL_TAGS, type SignalBus } from '../../src/render/conductor/types'

function makeBus(overrides: Partial<SignalBus> = {}): SignalBus {
  return {
    energy: 0.1,
    sub: 0.2,
    low: 0.3,
    mid: 0.4,
    presence: 0.5,
    air: 0.6,
    bandTilt: 0,
    centroid: 0.7,
    flatness: 0.8,
    pan: 0,
    familiarity: 0.9,
    noveltyLocal: 0,
    noveltySection: 0,
    fullness: 0,
    onsetDensity: 0,
    harmonicNovelty: 0,
    chromaRootHue: 0,
    vocalPresence: 0,
    drumsPresence: 0,
    bassPresence: 0,
    otherPresence: 0,
    leadPresence: 0,
    hueDrift: 0.15,
    beatPhase: 0.25,
    beatPulse: 0,
    barPhase: 0.5,
    downbeatPulse: 0,
    buildWindup: 0,
    buildProgress: 0,
    tension: 0,
    suspension: 0,
    dropImpulse: 0,
    onsetImpulse: 0,
    dropTrigger: null,
    scope: null,
    chroma: null,
    idle: false,
    tempoBpm: 120,
    tempoConfidence: 1,
    ...overrides,
  }
}

describe('signalBusToOscMessages', () => {
  it('emits exactly one message per routable (SIGNAL_TAGS) signal', () => {
    const messages = signalBusToOscMessages(makeBus())
    expect(messages).toHaveLength(Object.keys(SIGNAL_TAGS).length)
  })

  it('addresses each message under the bus prefix by signal name', () => {
    const messages = signalBusToOscMessages(makeBus())
    const byAddress = Object.fromEntries(messages.map((m) => [m.address, m]))
    expect(byAddress[`${OSC_BUS_ADDRESS_PREFIX}/energy`].args).toEqual([{ type: 'f', value: 0.1 }])
    expect(byAddress[`${OSC_BUS_ADDRESS_PREFIX}/tempoBpm`].args).toEqual([{ type: 'f', value: 120 }])
  })

  it('never emits scope/idle/dropTrigger — they are not in SIGNAL_TAGS', () => {
    const messages = signalBusToOscMessages(makeBus())
    const addresses = messages.map((m) => m.address)
    expect(addresses.some((a) => a.endsWith('/scope'))).toBe(false)
    expect(addresses.some((a) => a.endsWith('/idle'))).toBe(false)
    expect(addresses.some((a) => a.endsWith('/dropTrigger'))).toBe(false)
  })

  it('honors a custom address prefix', () => {
    const messages = signalBusToOscMessages(makeBus(), '/custom/root')
    expect(messages[0].address.startsWith('/custom/root/')).toBe(true)
  })
})
