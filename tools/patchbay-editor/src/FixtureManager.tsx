import { useState } from 'react'
import { addFixture, removeFixture, renameFixture, setFixtureDmxPatch, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
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
        const patch = fixture.dmxPatch
        return (
          <div key={fixture.id} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
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
            {/* Real DMX address (docs/dmx-out.md) — optional, only needed to
                send this fixture out over Art-Net/sACN. Unset by default,
                same as before this field existed (fixture-document.ts's
                DmxPatch doc comment). */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-2)' }}>
              <span>DMX:</span>
              <input
                type="number"
                min={1}
                placeholder="universe"
                value={patch?.universe ?? ''}
                onChange={(e) => {
                  const universe = Number(e.target.value)
                  onChange(
                    setFixtureDmxPatch(doc, fixture.id, Number.isFinite(universe) && universe > 0 ? { universe, startAddress: patch?.startAddress ?? 1 } : null),
                  )
                }}
                style={{ width: 64, fontSize: 11 }}
              />
              <span>@</span>
              <input
                type="number"
                min={1}
                max={512}
                placeholder="address"
                value={patch?.startAddress ?? ''}
                disabled={!patch}
                onChange={(e) => {
                  const startAddress = Number(e.target.value)
                  if (patch && Number.isFinite(startAddress)) onChange(setFixtureDmxPatch(doc, fixture.id, { ...patch, startAddress }))
                }}
                style={{ width: 64, fontSize: 11 }}
              />
            </div>
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
