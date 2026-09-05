export interface CardProps {
  title?: string
  hint?: string
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}

// The redesigned counterpart to SectionCard.tsx — same static-chrome role
// (title/hint/content, no drag/resize, per that file's own header comment
// on why those were removed once), plus an optional `actions` slot (a
// button/toggle in the card's own header) that SectionCard never had, so a
// card-level action doesn't have to live awkwardly inside `children`.
export function Card({ title, hint, actions, children, className }: CardProps) {
  return (
    <section className={['ui-card', className].filter(Boolean).join(' ')}>
      {(title || actions) && (
        <div className="ui-card-header">
          {title && <h3 className="ui-card-title">{title}</h3>}
          {actions && <div className="ui-card-actions">{actions}</div>}
        </div>
      )}
      {hint && <p className="section-hint">{hint}</p>}
      {children}
    </section>
  )
}
