import { useState } from 'react'
import { addFixture, removeFixture, renameFixture, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import { FIXTURE_TYPES } from '../../../src/render/conductor/patchgraph/fixture-types'

interface FixtureManagerProps {
  doc: FixtureDocument
  onChange: (next: FixtureDocument) => void
}

// Fixture instances are the actual degree of freedom this tool is supposed
// to hand the user (see fixture-document.ts's header comment) — adding one
// here immediately makes its channels real, routable targets in
// GraphEditor's target dropdown, no code change anywhere.
export function FixtureManager({ doc, onChange }: FixtureManagerProps) {
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState(FIXTURE_TYPES[0].id)

  function handleAdd() {
    const name = newName.trim() || `${FIXTURE_TYPES.find((t) => t.id === newType)?.label ?? newType} ${doc.fixtures.length + 1}`
    onChange(addFixture(doc, name, newType))
    setNewName('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {doc.fixtures.map((fixture) => {
        const type = FIXTURE_TYPES.find((t) => t.id === fixture.typeId)
        return (
          <div key={fixture.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <input
              type="text"
              value={fixture.name}
              onChange={(e) => onChange(renameFixture(doc, fixture.id, e.target.value))}
              style={{ flex: 1, fontSize: 12 }}
            />
            <span style={{ color: 'var(--text-2)', minWidth: 90 }}>{type?.label ?? fixture.typeId}</span>
            <button onClick={() => onChange(removeFixture(doc, fixture.id))} style={{ padding: '2px 8px', fontSize: 11 }} title="Remove fixture">
              ✕
            </button>
          </div>
        )
      })}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 4 }}>
        <input type="text" placeholder="name" value={newName} onChange={(e) => setNewName(e.target.value)} style={{ flex: 1, fontSize: 12 }} />
        <select value={newType} onChange={(e) => setNewType(e.target.value)} style={{ fontSize: 12 }}>
          {FIXTURE_TYPES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
        <button className="primary" onClick={handleAdd} style={{ fontSize: 12 }}>
          + Add
        </button>
      </div>
    </div>
  )
}
