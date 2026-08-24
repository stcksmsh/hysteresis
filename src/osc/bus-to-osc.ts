import { SIGNAL_TAGS, type RoutableSignalName, type SignalBus } from '../render/conductor/types'
import type { OscArg } from './osc-codec'

// The default address root every bus signal is published under
// (`/hysteresis/bus/<name>`) — a fixed prefix rather than something
// per-host-configurable, since the whole point is a stable, documented
// address a TouchDesigner/VCV Rack patch can hardcode once (docs/osc.md).
export const OSC_BUS_ADDRESS_PREFIX = '/hysteresis/bus'

// Every *routable* bus signal (SIGNAL_TAGS — the same set patch-graph
// `signal` nodes can read, i.e. every real numeric field; `scope`
// (Float32Array), `idle` (boolean-meta), and `dropTrigger` (discrete
// internal state) are deliberately excluded, same exclusion rule
// SIGNAL_TAGS itself already encodes) becomes one OSC float message. One
// message per signal (not one big blob) so a host can subscribe to just the
// addresses it cares about — standard OSC practice.
export function signalBusToOscMessages(bus: SignalBus, prefix = OSC_BUS_ADDRESS_PREFIX): { address: string; args: OscArg[] }[] {
  return (Object.keys(SIGNAL_TAGS) as RoutableSignalName[]).map((name) => ({
    address: `${prefix}/${name}`,
    args: [{ type: 'f', value: bus[name] }],
  }))
}
