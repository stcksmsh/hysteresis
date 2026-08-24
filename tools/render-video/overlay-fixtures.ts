import type { FixtureDocument } from '../../src/render/conductor/patchgraph/fixture-document'
import { fixtureTargetId } from '../../src/render/conductor/patchgraph/fixture-types'

// The right-side fixture overlay: canvas reimplementations of
// tools/patchbay-editor/src/FixtureVisuals.tsx's four widget types (that
// component is DOM/CSS/SVG, not canvas-drawable — see AGENTS.md's own note
// on why this needed reimplementing rather than reusing). Same
// value-resolution pattern (`fixtureValues[fixtureTargetId(id, channel)]`),
// just drawn with 2D canvas primitives instead of React elements so it can
// be composited directly onto the same output canvas as the rendered scene.
function get(fixtureValues: Record<string, number>, fixtureId: string, channel: string, fallback: number): number {
  const v = fixtureValues[fixtureTargetId(fixtureId, channel)]
  return typeof v === 'number' && Number.isFinite(v) ? v : fallback
}

export function drawFixtureOverlay(
  ctx: OffscreenCanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  doc: FixtureDocument,
  fixtureValues: Record<string, number>,
  alpha: number,
): void {
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.fillStyle = 'rgba(8,8,14,0.55)'
  ctx.fillRect(x, y, width, height)

  const rowHeight = height / Math.max(1, doc.fixtures.length)
  ctx.font = '12px monospace'
  ctx.textBaseline = 'top'

  doc.fixtures.forEach((fixture, i) => {
    const rowY = y + i * rowHeight
    const cx = x + width / 2
    const cy = rowY + rowHeight / 2

    ctx.fillStyle = 'rgba(200,200,215,0.9)'
    ctx.fillText(fixture.name, x + 10, rowY + 8)

    switch (fixture.typeId) {
      case 'dimmer': {
        const brightness = get(fixtureValues, fixture.id, 'brightness', 0)
        const radius = 18 + brightness * 22
        ctx.fillStyle = `rgba(255,220,150,${0.15 + brightness * 0.7})`
        ctx.beginPath()
        ctx.arc(cx, cy + 8, radius, 0, Math.PI * 2)
        ctx.fill()
        break
      }
      case 'rgb': {
        const r = get(fixtureValues, fixture.id, 'r', 0)
        const g = get(fixtureValues, fixture.id, 'g', 0)
        const b = get(fixtureValues, fixture.id, 'b', 0)
        ctx.fillStyle = `rgb(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)})`
        const size = 30
        ctx.fillRect(cx - size / 2, cy - size / 2 + 8, size, size)
        break
      }
      case 'servo': {
        const angle = get(fixtureValues, fixture.id, 'angle', 90)
        const radius = 22
        ctx.strokeStyle = 'rgba(180,180,200,0.6)'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(cx, cy + 8, radius, Math.PI, Math.PI * 2)
        ctx.stroke()
        const rad = (angle / 180) * Math.PI + Math.PI
        ctx.strokeStyle = 'rgba(255,180,120,0.95)'
        ctx.lineWidth = 3
        ctx.beginPath()
        ctx.moveTo(cx, cy + 8)
        ctx.lineTo(cx + Math.cos(rad) * radius, cy + 8 + Math.sin(rad) * radius)
        ctx.stroke()
        break
      }
      case 'mover': {
        const pan = get(fixtureValues, fixture.id, 'pan', 0.5)
        const tilt = get(fixtureValues, fixture.id, 'tilt', 0.5)
        const intensity = get(fixtureValues, fixture.id, 'intensity', 0)
        const boxSize = Math.min(width - 20, rowHeight - 16)
        const boxX = cx - boxSize / 2
        const boxY = rowY + 16
        ctx.strokeStyle = 'rgba(120,120,140,0.5)'
        ctx.strokeRect(boxX, boxY, boxSize, boxSize)
        const dotX = boxX + pan * boxSize
        const dotY = boxY + tilt * boxSize
        ctx.fillStyle = `rgba(120,220,255,${0.3 + intensity * 0.7})`
        ctx.beginPath()
        ctx.arc(dotX, dotY, 5 + intensity * 5, 0, Math.PI * 2)
        ctx.fill()
        break
      }
    }
  })
  ctx.restore()
}
