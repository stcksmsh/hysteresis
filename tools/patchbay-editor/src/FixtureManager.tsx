import { useState } from 'react'
import { addFixture, removeFixture, renameFixture, setFixtureDmxPatch, type FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import { FIXTURE_TYPES } from '../../../src/render/conductor/patchgraph/fixture-types'
import { IconButton } from './ui/IconButton'
import { Button } from './ui/Button'
import { Select } from './ui/Select'
import { NumberInput } from './ui/NumberInput'
import { IconTrash, IconPlus } from './ui/icons'

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
              <IconButton icon={<IconTrash size={13} />} label="Remove fixture" onClick={() => onChange(removeFixture(doc, fixture.id))} />
            </div>
            {/* Real DMX address (docs/dmx-out.md) — optional, only needed to
                send this fixture out over Art-Net/sACN. Unset by default,
                same as before this field existed (fixture-document.ts's
                DmxPatch doc comment). */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-2)' }}>
              <span>DMX:</span>
              <NumberInput
                step={1}
                min={1}
                width={64}
                value={patch?.universe ?? 0}
                onChange={(universe) => onChange(setFixtureDmxPatch(doc, fixture.id, universe > 0 ? { universe, startAddress: patch?.startAddress ?? 1 } : null))}
              />
              <span>@</span>
              <NumberInput
                step={1}
                min={1}
                max={512}
                width={64}
                disabled={!patch}
                value={patch?.startAddress ?? 0}
                onChange={(startAddress) => {
                  if (patch) onChange(setFixtureDmxPatch(doc, fixture.id, { ...patch, startAddress }))
                }}
              />
            </div>
          </div>
        )
      })}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 4 }}>
        <input type="text" placeholder="name" value={newName} onChange={(e) => setNewName(e.target.value)} style={{ flex: 1, fontSize: 12 }} />
        <Select uiSize="sm" value={newType} onChange={(e) => setNewType(e.target.value)}>
          {FIXTURE_TYPES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </Select>
        <Button variant="primary" icon={<IconPlus size={13} />} onClick={handleAdd}>
          Add
        </Button>
      </div>
    </div>
  )
}
