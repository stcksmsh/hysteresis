import { Card } from '../ui/Card'
import { FixtureManager } from '../FixtureManager'
import { FixtureVisuals } from '../FixtureVisuals'
import { DmxOutPanel, type DmxOutPanelProps } from '../DmxOutPanel'
import { OscInPanel, type OscInPanelProps } from '../OscInPanel'
import { MidiPanel } from '../MidiPanel'
import type { FixtureDocument } from '../../../../src/render/conductor/patchgraph/fixture-document'

export interface OutputScreenProps {
  fixtureDoc: FixtureDocument
  onFixtureDocChange: (next: FixtureDocument) => void
  resolvedValues: Record<string, number>
  dmxProps: Pick<DmxOutPanelProps, 'status' | 'onConnect' | 'onDisconnect'>
  oscInProps: Pick<OscInPanelProps, 'status' | 'onConnect' | 'onDisconnect'>
  onMidiCcChange: (key: string, value: number) => void
}

// All physical-I/O configuration in one place — Fixtures and Fixture
// Visuals side by side (the visual feedback sits right next to the thing
// being configured, instead of a separate rail card scrolled somewhere
// else), DMX/OSC/MIDI output+input config below. MIDI moves here from its
// old home buried inside the debug drawer — connecting a controller is I/O
// setup, not a diagnostic readout.
export function OutputScreen({ fixtureDoc, onFixtureDocChange, resolvedValues, dmxProps, oscInProps, onMidiCcChange }: OutputScreenProps) {
  return (
    <div className="screen screen-output">
      <div className="output-grid-top">
        <Card title="Fixtures">
          <FixtureManager doc={fixtureDoc} onChange={onFixtureDocChange} />
        </Card>
        <Card title="Fixture visuals" hint="Live, simulated — driven by the real worker-resident fixture graph, no hardware needed to validate a patch.">
          <FixtureVisuals doc={fixtureDoc} resolved={resolvedValues} />
        </Card>
      </div>
      <div className="output-grid-bottom">
        <Card title="DMX out" hint="Send patched fixtures out over real Art-Net/sACN/WLED/USB — see docs/dmx-out.md.">
          <DmxOutPanel fixtureDoc={fixtureDoc} resolvedValues={resolvedValues} {...dmxProps} />
        </Card>
        <Card title="OSC in" hint="Route a live incoming OSC message into the graph — see docs/osc.md.">
          <OscInPanel {...oscInProps} />
        </Card>
        <Card title="MIDI in" hint="Real Web MIDI device input — control-change activity and clock/beat sync. See docs/midi.md.">
          <MidiPanel onCcChange={onMidiCcChange} />
        </Card>
      </div>
    </div>
  )
}
