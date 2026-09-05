export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'ghost'
  icon?: React.ReactNode
}

// Thin wrapper over the plain <button> styling styles.css already defines
// (.primary etc) — exists so every screen reaches for one shared component
// instead of re-deciding button markup/spacing per panel, which is exactly
// the inconsistency the redesign's own inventory flagged (fixture/DMX/OSC/
// MIDI panels on ad hoc inline styles vs. the graph canvas's shared classes).
export function Button({ variant = 'default', icon, className, children, ...rest }: ButtonProps) {
  const classes = ['ui-button', variant === 'primary' ? 'primary' : '', variant === 'ghost' ? 'ui-button-ghost' : '', className].filter(Boolean).join(' ')
  return (
    <button className={classes} {...rest}>
      {icon && <span className="ui-button-icon">{icon}</span>}
      {children}
    </button>
  )
}
