import type { FixtureDocument } from '../../../src/render/conductor/patchgraph/fixture-document'
import { getFixtureType, fixtureTargetId } from '../../../src/render/conductor/patchgraph/fixture-types'

interface FixtureVisualsProps {
  doc: FixtureDocument
  resolved: Record<string, number>
}

// Task #9: a live-rendered widget per fixture instance, driven by the real
// PatchGraphEvaluator result — lets patches be validated with zero real
// hardware, per the earlier scoping decision (simulated fixtures over
// numeric-readouts-only).
export function FixtureVisuals({ doc, resolved }: FixtureVisualsProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {doc.fixtures.map((fixture) => {
        const type = getFixtureType(fixture.typeId)
        if (!type) return null
        const get = (channelKey: string) => resolved[fixtureTargetId(fixture.id, channelKey)] ?? 0
        return (
          <div key={fixture.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, width: 110, color: 'var(--text-1)' }}>{fixture.name}</span>
            <FixtureWidget typeId={fixture.typeId} get={get} />
          </div>
        )
      })}
      {doc.fixtures.length === 0 && <div className="empty-hint">No fixtures yet.</div>}
    </div>
  )
}

function FixtureWidget({ typeId, get }: { typeId: string; get: (channelKey: string) => number }) {
  switch (typeId) {
    case 'dimmer': {
      const v = get('brightness')
      return (
        <div
          style={{
            width: 64,
            height: 32,
            borderRadius: 'var(--radius)',
            border: '1px solid var(--border)',
            background: `rgba(94, 230, 200, ${0.04 + v * 0.8})`,
            boxShadow: v > 0.05 ? `0 0 ${8 + v * 20}px rgba(94,230,200,${v * 0.6})` : 'none',
            transition: 'background 0.08s linear, box-shadow 0.08s linear',
          }}
        />
      )
    }
    case 'rgb': {
      const r = Math.round(get('r') * 255)
      const g = Math.round(get('g') * 255)
      const b = Math.round(get('b') * 255)
      return (
        <div
          style={{
            width: 64,
            height: 32,
            borderRadius: 'var(--radius)',
            border: '1px solid var(--border)',
            background: `rgb(${r},${g},${b})`,
          }}
        />
      )
    }
    case 'servo': {
      const angle = get('angle') // 0..180
      return (
        <div style={{ width: 64, height: 40, position: 'relative' }}>
          <svg width="64" height="40" viewBox="0 0 64 40">
            <path d="M 4 36 A 28 28 0 0 1 60 36" fill="none" stroke="var(--border)" strokeWidth="2" />
            <line
              x1="32"
              y1="36"
              x2={32 + 26 * Math.cos(Math.PI - (angle / 180) * Math.PI)}
              y2={36 - 26 * Math.sin(Math.PI - (angle / 180) * Math.PI)}
              stroke="var(--accent)"
              strokeWidth="2"
            />
            <circle cx="32" cy="36" r="3" fill="var(--accent)" />
          </svg>
          <span className="mono" style={{ position: 'absolute', top: 0, right: 0, fontSize: 10, color: 'var(--text-2)' }}>
            {angle.toFixed(0)}°
          </span>
        </div>
      )
    }
    case 'mover': {
      const pan = get('pan') // 0..1
      const tilt = get('tilt') // 0..1
      const intensity = get('intensity')
      return (
        <div
          style={{
            width: 64,
            height: 64,
            position: 'relative',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            background: 'var(--bg-2)',
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: `${pan * 100}%`,
              top: `${(1 - tilt) * 100}%`,
              width: 10,
              height: 10,
              marginLeft: -5,
              marginTop: -5,
              borderRadius: '50%',
              background: 'var(--accent)',
              opacity: 0.3 + intensity * 0.7,
              boxShadow: intensity > 0.05 ? `0 0 ${6 + intensity * 14}px var(--accent)` : 'none',
            }}
          />
        </div>
      )
    }
    default:
      return <span style={{ fontSize: 11, color: 'var(--text-2)' }}>(no visual for {typeId})</span>
  }
}
