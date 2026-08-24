import { useRef, useState } from 'react'
import type { PatchTargetDecl } from '../../../src/render/conductor/patchgraph/types'

export interface IsfPanelProps {
  onLoad: (source: string, fileName: string) => void
  onClear: () => void
  status: { state: 'empty' } | { state: 'loaded'; fileName: string; targets: PatchTargetDecl[] } | { state: 'error'; fileName: string; message: string }
}

// Real ISF import (master-prompt.md §6's "ISF import + auto-generated
// patchbay node UI" backlog item): drop in an actual .fs file from the ISF
// ecosystem, see it render live as the screen scene, and get its own
// declared inputs back as real targets in the graph canvas's target
// dropdown — this panel is the load/status half of that; PatchGraphCanvas
// (fed `mergedCatalog` in App.tsx) is what makes the resulting targets
// actually routable.
export function IsfPanel({ onLoad, onClear, status }: IsfPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  async function loadFile(file: File) {
    const text = await file.text()
    onLoad(text, file.name)
  }

  return (
    <div
      className={dragOver ? 'isf-drop-zone isf-drop-zone-active' : 'isf-drop-zone'}
      onDragOver={(e) => {
        e.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragOver(false)
        const file = e.dataTransfer.files?.[0]
        if (file) void loadFile(file)
      }}
    >
      <input
        ref={fileRef}
        type="file"
        accept=".fs,.glsl,.txt"
        style={{ display: 'none' }}
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void loadFile(file)
          e.target.value = ''
        }}
      />
      <div className="isf-panel-controls">
        <button onClick={() => fileRef.current?.click()}>Load .fs shader…</button>
        {status.state !== 'empty' && (
          <button className="isf-panel-clear" onClick={onClear}>
            Revert to Julia
          </button>
        )}
      </div>

      {status.state === 'empty' && <p className="empty-hint">Drop or load a real ISF (.fs) file — a single-pass generator/filter with only float/bool/long/color/point2D inputs.</p>}

      {status.state === 'loaded' && (
        <div className="mono readout">
          <div>{status.fileName} — loaded, {status.targets.length} input target(s)</div>
          {status.targets.map((t) => (
            <div key={t.id}>{t.label ?? t.id}</div>
          ))}
        </div>
      )}

      {status.state === 'error' && (
        <div className="banner banner-error" style={{ margin: 0 }}>
          {status.fileName}: {status.message}
        </div>
      )}
    </div>
  )
}
