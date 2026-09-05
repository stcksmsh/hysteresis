import { Button } from '../ui/Button'
import { IconSave } from '../ui/icons'
import { PatchGraphCanvas } from '../PatchGraphCanvas'
import type { DraftNode } from '../graph-draft'
import type { PatchTargetDecl } from '../../../../src/render/conductor/patchgraph/types'

export interface GraphScreenProps {
  nodes: DraftNode[]
  onChange: (next: DraftNode[]) => void
  targets: PatchTargetDecl[]
  onSave: () => void
}

// Today's former "workspace-main" — the graph is the hero, and now that
// it's a real full-width screen instead of sharing a flex row with a
// permanent 320px rail, it gets the whole screen instead of competing for
// horizontal space with fixture/DMX/OSC panels it has nothing to do with.
export function GraphScreen({ nodes, onChange, targets, onSave }: GraphScreenProps) {
  return (
    <div className="screen screen-graph">
      <div className="screen-header">
        <h2 className="screen-title">Patch graph — screen + fixtures</h2>
        <span className="section-hint" style={{ margin: 0 }}>
          One unified graph: signal → operator → target chains, driving both the live screen and every fixture from
          the same wiring.
        </span>
        <Button icon={<IconSave size={14} />} onClick={onSave} style={{ marginLeft: 'auto' }}>
          Save to file
        </Button>
      </div>
      <PatchGraphCanvas nodes={nodes} onChange={onChange} targets={targets} />
    </div>
  )
}
