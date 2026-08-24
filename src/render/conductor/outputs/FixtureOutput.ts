import { DmxOutBridge, type DmxOutOptions, type DmxOutStatus } from '../../../dmx/dmx-out-bridge'
import { renderDmxUniverses } from '../../../dmx/render-dmx-universe'
import { emptyFixtureDocument, fixtureTargetCatalog, type FixtureDocument } from '../patchgraph/fixture-document'
import type { PatchTargetDecl } from '../patchgraph/types'

export interface FixtureOutConfig {
  protocol: DmxOutOptions['protocol']
  wsUrl: string
  // Required for wled-drgb (one specific device's IP), optional/falls back
  // to Art-Net broadcast / sACN multicast otherwise — see DmxOutBridge.send.
  universeHost?: string
}

// Production-side counterpart to the patchbay editor's DmxOutPanel +
// ephemeral React-state fixture evaluation (AGENTS.md's "unify screen +
// physical patch graphs" / DMX sessions) — lives inside the render worker
// so a host's own setFixtureDocument/setFixtureGraph/setFixtureOut calls
// (src/index.ts) reach real hardware, not just the dev tool. USB (Web
// Serial) deliberately isn't handled here: DmxSerialOutput.connect() needs
// a user-gesture requestPort() call, which only works on the main thread —
// out of scope for a worker-resident output. Art-Net/sACN/WLED all reach a
// real destination over the same WebSocket relay OSC uses (docs/dmx-out.md).
export class FixtureOutput {
  private doc: FixtureDocument = emptyFixtureDocument()
  private bridge: DmxOutBridge | null = null
  private universeHost: string | undefined

  targets(): PatchTargetDecl[] {
    return fixtureTargetCatalog(this.doc)
  }

  setDocument(doc: FixtureDocument): void {
    this.doc = doc
  }

  connect(config: FixtureOutConfig, onStatus: (status: DmxOutStatus) => void): void {
    this.bridge?.disconnect()
    this.universeHost = config.universeHost
    this.bridge = new DmxOutBridge({ protocol: config.protocol, sacnSourceName: 'Hysteresis' }, onStatus)
    this.bridge.connect(config.wsUrl)
  }

  disconnect(): void {
    this.bridge?.disconnect()
    this.bridge = null
  }

  // `resolved` is PatchGraphEvaluator.evaluate()'s raw output — only ever
  // contains a target an actual route reaches, same partial-map contract
  // ScreenOutput's resolveScreenTargets exists to fill in defaults for.
  // renderDmxUniverses already falls back to each channel's own
  // defaultValue for a missing key (see its own doc comment), so no
  // equivalent fill-in step is needed here.
  send(resolved: Record<string, number>): void {
    if (!this.bridge) return
    const universes = renderDmxUniverses(this.doc, resolved)
    if (universes.size > 0) this.bridge.send(universes, this.universeHost)
  }

  dispose(): void {
    this.disconnect()
  }
}
