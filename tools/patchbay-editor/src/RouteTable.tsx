import { addRoute, removeRoute, updateRoute, type PatchDocument } from '../../../src/render/conductor/patchbay/editor/patch-document'
import { SIGNAL_CATALOG, CURVE_OPTIONS, curveKind, getTargetCatalog } from '../../../src/render/conductor/patchbay/editor/catalog'
import { Patchbay } from '../../../src/render/conductor/patchbay/Patchbay'
import { toConfig } from '../../../src/render/conductor/patchbay/editor/patch-document'
import type { Curve, Route } from '../../../src/render/conductor/patchbay/types'

// The actual route-table UI (task #4): every non-passthrough route in the
// document, editable in place. This is what turns "the patch document model
// exists" into "you can actually control the screen from here" — in
// particular, it's the concrete answer to "let me control/automate the
// palette": screen.hueShift and screen.paletteMix are routes like any
// other now (see screen-only.ts's paletteRoutes), so editing/adding rows
// here reaches them with no special-casing anywhere in this component.
const TARGET_CATALOG = getTargetCatalog()

interface RouteTableProps {
  doc: PatchDocument
  onChange: (next: PatchDocument) => void
}

export function RouteTable({ doc, onChange }: RouteTableProps) {
  // Recomputed on every render (cheap — a few dozen routes) rather than
  // memoized: this needs to reflect the doc as edited, not the last
  // successfully-applied config, so a bad edit shows its own error
  // immediately instead of waiting on the worker's async ack.
  const issues = Patchbay.collectIssues(toConfig(doc), TARGET_CATALOG)
  const issuesByRouteId = new Map<string, string[]>()
  doc.routes.forEach((route, index) => {
    const forThisRoute = issues.filter((i) => i.routeIndex === index)
    if (forThisRoute.length) issuesByRouteId.set(route.id, forThisRoute.map((i) => i.message))
  })

  const editableRoutes = doc.routes.filter((r) => !r.passThrough)

  function patch(routeId: string, fields: Partial<Route>) {
    onChange(updateRoute(doc, routeId, fields))
  }

  function handleAdd() {
    onChange(addRoute(doc, { from: SIGNAL_CATALOG[0].name, to: TARGET_CATALOG[0].id, curve: 'linear' }))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-1)' }}>
              <th style={thStyle}>From</th>
              <th style={thStyle}>To</th>
              <th style={thStyle}>Curve</th>
              <th style={thStyle}>Gain</th>
              <th style={thStyle}>Offset</th>
              <th style={thStyle}>Invert</th>
              <th style={thStyle}></th>
            </tr>
          </thead>
          <tbody>
            {editableRoutes.map((route) => {
              const routeIssues = issuesByRouteId.get(route.id)
              return (
                <tr key={route.id} style={{ borderTop: '1px solid var(--border-soft)' }}>
                  <td style={tdStyle}>
                    <select value={route.from} onChange={(e) => patch(route.id, { from: e.target.value })} style={selectStyle}>
                      {SIGNAL_CATALOG.map((s) => (
                        <option key={s.name} value={s.name}>
                          {s.name} ({s.tag})
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={tdStyle}>
                    <select value={route.to} onChange={(e) => patch(route.id, { to: e.target.value })} style={selectStyle}>
                      {TARGET_CATALOG.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.id}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={tdStyle}>
                    <select
                      value={curveKind(route.curve)}
                      onChange={(e) => {
                        const found = CURVE_OPTIONS.find((c) => curveKind(c.value) === e.target.value)
                        patch(route.id, { curve: (found?.value ?? 'linear') as Curve })
                      }}
                      style={selectStyle}
                    >
                      {CURVE_OPTIONS.map((c) => (
                        <option key={curveKind(c.value)} value={curveKind(c.value)}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={tdStyle}>
                    <input
                      type="number"
                      step={0.05}
                      value={route.gain ?? 1}
                      onChange={(e) => patch(route.id, { gain: Number(e.target.value) })}
                      style={numInputStyle}
                    />
                  </td>
                  <td style={tdStyle}>
                    <input
                      type="number"
                      step={0.05}
                      value={route.offset ?? 0}
                      onChange={(e) => patch(route.id, { offset: Number(e.target.value) })}
                      style={numInputStyle}
                    />
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <input type="checkbox" checked={route.invert ?? false} onChange={(e) => patch(route.id, { invert: e.target.checked })} />
                  </td>
                  <td style={tdStyle}>
                    <button onClick={() => onChange(removeRoute(doc, route.id))} title="Remove route" style={{ padding: '2px 8px' }}>
                      ✕
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {[...issuesByRouteId.entries()].map(([routeId, messages]) => (
        <div key={routeId} style={{ fontSize: 11, color: 'var(--error)' }}>
          {messages.join('; ')}
        </div>
      ))}
      <button className="primary" onClick={handleAdd} style={{ alignSelf: 'flex-start', marginTop: 4 }}>
        + Add route
      </button>
    </div>
  )
}

const thStyle: React.CSSProperties = { padding: '4px 6px', fontWeight: 500 }
const tdStyle: React.CSSProperties = { padding: '4px 6px' }
const selectStyle: React.CSSProperties = { width: '100%', fontSize: 12 }
const numInputStyle: React.CSSProperties = { width: 64, fontSize: 12 }
