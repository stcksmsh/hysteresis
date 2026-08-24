import type { FixtureDocument } from '../render/conductor/patchgraph/fixture-document'
import { getFixtureType, fixtureTargetId } from '../render/conductor/patchgraph/fixture-types'

export const DMX_UNIVERSE_SIZE = 512

// Scales a resolved channel value (in the channel's own declared range,
// e.g. a servo's [0,180] degrees) onto a single DMX byte (0..255) — DMX512
// is always 8-bit per channel at this layer (16-bit "fine" channels are a
// fixture-profile-level concept — coarse+fine channel pairs — not modeled
// here yet, see docs/dmx-out.md's limitations).
function toDmxByte(value: number, range: readonly [number, number]): number {
  const [lo, hi] = range
  const t = hi === lo ? 0 : (value - lo) / (hi - lo)
  return Math.max(0, Math.min(255, Math.round(t * 255)))
}

// Renders every DMX-patched fixture instance's resolved channel values into
// real per-universe 512-byte buffers — the bridge between the patch graph's
// abstract, normalized target values and the actual bytes Art-Net/sACN
// carry. A fixture instance with no `dmxPatch` set (the common case for the
// simulated-only patchbay editor demo fixtures) contributes nothing here —
// this function is additive, never a behavior change for existing
// simulation-only usage.
export function renderDmxUniverses(doc: FixtureDocument, resolved: Record<string, number>): Map<number, Uint8Array> {
  const universes = new Map<number, Uint8Array>()

  for (const fixture of doc.fixtures) {
    if (!fixture.dmxPatch) continue
    const type = getFixtureType(fixture.typeId)
    if (!type) continue

    let buf = universes.get(fixture.dmxPatch.universe)
    if (!buf) {
      buf = new Uint8Array(DMX_UNIVERSE_SIZE)
      universes.set(fixture.dmxPatch.universe, buf)
    }

    type.channels.forEach((channel, i) => {
      const address = fixture.dmxPatch!.startAddress + i // 1-based DMX address
      if (address < 1 || address > DMX_UNIVERSE_SIZE) return // out-of-range patch — silently dropped, same "don't crash on a bad config" posture as PatchGraphEvaluator's own unrouted-target handling
      const value = resolved[fixtureTargetId(fixture.id, channel.key)] ?? channel.defaultValue
      buf![address - 1] = toDmxByte(value, channel.range)
    })
  }

  return universes
}
