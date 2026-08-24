import type { SignalBus } from '../../src/render/conductor/types'
import type { DropDetectorDebug } from '../../src/audio/worklet/brain/drop-detector'

// The left-side debug overlay: a semi-transparent readout of the full live
// signal set, drawn straight onto the output 2D canvas each frame. This is
// deliberately more complete than the patchbay editor's own debug drawer —
// AGENTS.md confirms the newest bus signals (noveltyLocal/noveltySection,
// harmonicNovelty, chromaRootHue, fullness, onsetDensity, the 5 stem-
// presence signals) were never wired into that UI — the render tool's
// overlay is the first place any of them are actually drawn.
function fmt(v: number | undefined): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(3) : '—'
}

interface Row {
  label: string
  value: string
}

function rows(bus: SignalBus, dropDebug: DropDetectorDebug | null): Row[] {
  return [
    { label: 'tempoBpm', value: fmt(bus.tempoBpm) },
    { label: 'beatPhase', value: fmt(bus.beatPhase) },
    { label: 'barPhase', value: fmt(bus.barPhase) },
    { label: '', value: '' },
    { label: 'energy', value: fmt(bus.energy) },
    { label: 'sub / low / mid', value: `${fmt(bus.sub)} / ${fmt(bus.low)} / ${fmt(bus.mid)}` },
    { label: 'presence / air', value: `${fmt(bus.presence)} / ${fmt(bus.air)}` },
    { label: 'bandTilt', value: fmt(bus.bandTilt) },
    { label: 'centroid / flatness', value: `${fmt(bus.centroid)} / ${fmt(bus.flatness)}` },
    { label: '', value: '' },
    { label: 'buildProgress', value: fmt(bus.buildProgress) },
    { label: 'tension / suspension', value: `${fmt(bus.tension)} / ${fmt(bus.suspension)}` },
    { label: 'dropImpulse', value: fmt(bus.dropImpulse) },
    { label: 'onsetImpulse', value: fmt(bus.onsetImpulse) },
    { label: '', value: '' },
    { label: 'familiarity', value: fmt(bus.familiarity) },
    { label: 'noveltyLocal', value: fmt(bus.noveltyLocal) },
    { label: 'noveltySection', value: fmt(bus.noveltySection) },
    { label: 'fullness', value: fmt(bus.fullness) },
    { label: 'onsetDensity', value: fmt(bus.onsetDensity) },
    { label: '', value: '' },
    { label: 'harmonicNovelty', value: fmt(bus.harmonicNovelty) },
    { label: 'chromaRootHue', value: fmt(bus.chromaRootHue) },
    { label: '', value: '' },
    { label: 'vocalPresence', value: fmt(bus.vocalPresence) },
    { label: 'drumsPresence', value: fmt(bus.drumsPresence) },
    { label: 'bassPresence', value: fmt(bus.bassPresence) },
    { label: 'otherPresence', value: fmt(bus.otherPresence) },
    { label: 'leadPresence', value: fmt(bus.leadPresence) },
    { label: '', value: '' },
    { label: 'drop.fullness', value: fmt(dropDebug?.fullness) },
    { label: 'drop.onsetJump', value: fmt(dropDebug?.onsetJump) },
    { label: 'drop.noveltyPeak', value: fmt(dropDebug?.noveltyPeak) },
    { label: 'drop.armed', value: dropDebug ? String(dropDebug.armed) : '—' },
  ]
}

export function drawDebugOverlay(
  ctx: OffscreenCanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  bus: SignalBus,
  dropDebug: DropDetectorDebug | null,
  alpha: number,
): void {
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.fillStyle = 'rgba(8,8,14,0.55)'
  ctx.fillRect(x, y, width, height)

  ctx.globalAlpha = alpha
  ctx.font = '13px monospace'
  ctx.textBaseline = 'top'
  const lineHeight = 16
  const padding = 12
  let cy = y + padding
  for (const row of rows(bus, dropDebug)) {
    if (row.label === '') {
      cy += lineHeight * 0.4
      continue
    }
    ctx.fillStyle = 'rgba(200,200,215,0.9)'
    ctx.fillText(row.label, x + padding, cy)
    ctx.fillStyle = 'rgba(255,180,120,0.95)'
    ctx.fillText(row.value, x + padding + 150, cy)
    cy += lineHeight
    if (cy > y + height - lineHeight) break // overflow guard for small panels
  }
  ctx.restore()
}
