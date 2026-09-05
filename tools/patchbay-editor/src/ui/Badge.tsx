export interface BadgeProps {
  children: React.ReactNode
  tone?: 'default' | 'accent' | 'warn' | 'error' | 'ok'
}

// A small pill label — used for e.g. an envelope input's "live" override
// state in the inspector, a shader's parse status, a template tag. Distinct
// from .status-pill (styles.css, used for header/toolbar readouts) in
// intent: a Badge marks a property of ONE specific thing inline (this
// field is live-overridden), a status-pill reports ongoing app-level state.
export function Badge({ children, tone = 'default' }: BadgeProps) {
  return <span className={`ui-badge ui-badge-${tone}`}>{children}</span>
}
