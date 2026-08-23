import type { ReactNode } from 'react'

// Static chrome for a secondary panel (the rail, the debug drawer) — no
// drag-reorder, no per-panel resize. Those existed when every panel was an
// equal-weight member of one flat flow (see the earlier panel-flow layout);
// now the workspace has a real hierarchy (the graph is the hero, everything
// else is fixed-position supporting UI), so a loose, rearrangeable window
// manager for two or three small cards was solving a problem the new
// layout doesn't have anymore.
export interface SectionCardProps {
  title: string
  hint?: string
  children: ReactNode
  className?: string
}

export function SectionCard({ title, hint, children, className }: SectionCardProps) {
  return (
    <section className={['section-card', className].filter(Boolean).join(' ')}>
      <h3 className="section-card-title">{title}</h3>
      {hint && <p className="section-hint">{hint}</p>}
      {children}
    </section>
  )
}
