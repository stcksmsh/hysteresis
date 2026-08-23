import type { ReactNode } from 'react'

// Drag-to-reorder + native CSS resize, no extra dependency: the browser's
// own `resize: both` (see .panel-section in styles.css) gives a real
// per-panel resize handle for free, and HTML5 drag-and-drop (draggable +
// dragstart/dragover/drop) is enough for reordering a flat list — a full
// drag library would be overkill for a dev-only tool with ~8 panels.
export interface PanelProps {
  id: string
  title: string
  hint?: string
  wide?: boolean
  defaultWidth?: number
  defaultHeight?: number
  children: ReactNode
  dragging: boolean
  draggedOver: boolean
  onDragStart: (id: string) => void
  onDragEnd: () => void
  onDragOver: (id: string) => void
  onDrop: (id: string) => void
}

export function Panel({
  id,
  title,
  hint,
  wide,
  defaultWidth,
  defaultHeight,
  children,
  dragging,
  draggedOver,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: PanelProps) {
  return (
    <section
      className={[
        'panel-section',
        wide ? 'panel-section-wide' : '',
        dragging ? 'panel-section-dragging' : '',
        draggedOver ? 'panel-section-dragover' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{ width: defaultWidth, height: defaultHeight }}
      onDragOver={(e) => {
        e.preventDefault()
        onDragOver(id)
      }}
      onDrop={(e) => {
        e.preventDefault()
        onDrop(id)
      }}
    >
      <div className="panel-header" draggable onDragStart={() => onDragStart(id)} onDragEnd={onDragEnd} title="Drag to reorder">
        <span className="panel-drag-handle">⠿</span>
        <h3 className="section-title">{title}</h3>
      </div>
      {hint && <p className="section-hint">{hint}</p>}
      {children}
    </section>
  )
}
