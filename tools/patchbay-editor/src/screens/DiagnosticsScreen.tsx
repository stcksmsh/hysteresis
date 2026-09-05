import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import type { SignalBus } from '../../../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../../../src/audio/worklet/brain/drop-detector'

export interface DropLogEntry {
  atMs: number
  strength: number
}

const DROP_EDGE_EPS = 0.05

export interface DiagnosticsScreenProps {
  bus: SignalBus | null
  graphErrorCount: number
  routedFixtureChannelCount: number
  dropDebug: DropDetectorDebug | null
  dropLog: DropLogEntry[]
}

// Promoted from a slide-in overlay to a real screen — same real data as
// before (bus readout, Layer 2 musical-state readout, drop-detector
// internals, drop-detector log), just no longer competing with whatever
// else was on screen for space. MIDI moved OUT of this group to Output —
// it's I/O configuration, not a read-only diagnostic.
export function DiagnosticsScreen({ bus, graphErrorCount, routedFixtureChannelCount, dropDebug, dropLog }: DiagnosticsScreenProps) {
  return (
    <div className="screen screen-diagnostics">
      <div className="diagnostics-grid">
        <Card title="Debug readout">
          <div className="mono readout">
            <div>bus.energy: {bus ? bus.energy.toFixed(4) : '—'}</div>
            <div>bus.idle: {bus ? String(bus.idle) : '—'}</div>
            <div>graph: {graphErrorCount === 0 ? <Badge tone="ok">valid</Badge> : <Badge tone="error">{graphErrorCount} error(s) — see Patch Graph</Badge>}</div>
            <div>fixture values from worker: {routedFixtureChannelCount} routed channel(s)</div>
          </div>
        </Card>

        <Card title="Musical state (Layer 2 → bus)">
          <div className="mono readout">
            <div>tension: {bus ? bus.tension.toFixed(4) : '—'}</div>
            <div>buildProgress: {bus ? bus.buildProgress.toFixed(4) : '—'}</div>
            <div>suspension: {bus ? bus.suspension.toFixed(4) : '—'}</div>
            <div>dropImpulse: {bus ? bus.dropImpulse.toFixed(4) : '—'}</div>
            <div>familiarity: {bus ? bus.familiarity.toFixed(4) : '—'}</div>
            <div>flatness: {bus ? bus.flatness.toFixed(4) : '—'}</div>
            <div>tempoBpm / confidence: {bus ? `${bus.tempoBpm.toFixed(1)} / ${bus.tempoConfidence.toFixed(2)}` : '—'}</div>
            <div>noveltyLocal / noveltySection: {bus ? `${bus.noveltyLocal.toFixed(3)} / ${bus.noveltySection.toFixed(3)}` : '—'}</div>
            <div>fullness / onsetDensity: {bus ? `${bus.fullness.toFixed(3)} / ${bus.onsetDensity.toFixed(3)}` : '—'}</div>
            <div>harmonicNovelty / chromaRootHue: {bus ? `${bus.harmonicNovelty.toFixed(3)} / ${bus.chromaRootHue.toFixed(3)}` : '—'}</div>
          </div>
        </Card>

        <Card
          title="Drop detector internals"
          hint="The detector's own live qualifying values, straight from inside it — not the bus. If dropImpulse never fires, this is what tells you WHICH condition is failing against real audio."
        >
          <div className="mono readout">
            <div>fullness: {dropDebug ? dropDebug.fullness.toFixed(4) : '—'} (needs &gt; 0.5)</div>
            <div>onsetJump: {dropDebug ? dropDebug.onsetJump.toFixed(4) : '—'} (needs &gt; 0.06 for the rhythmic path)</div>
            <div>noveltyPeak: {dropDebug ? dropDebug.noveltyPeak.toFixed(4) : '—'} (needs &gt; 0.3)</div>
            <div>armed: {dropDebug ? String(dropDebug.armed) : '—'}</div>
            {dropDebug === null && bus !== null && (
              <div style={{ color: 'var(--warn)' }}>
                null — either no track is loaded, or detectors are disabled (sidecar/position-only mode has no live detector to read from at all).
              </div>
            )}
          </div>
        </Card>

        <Card title="Drop detector log" hint={`Rising edges of bus.dropImpulse (>${DROP_EDGE_EPS} in one tick), most recent first. Time is seconds since this page loaded, not track position.`}>
          {dropLog.length === 0 ? (
            <div className="empty-hint">No drops observed yet.</div>
          ) : (
            <div className="mono readout">
              {dropLog.map((entry, i) => (
                <div key={i}>
                  +{(entry.atMs / 1000).toFixed(1)}s — strength {entry.strength.toFixed(2)}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
