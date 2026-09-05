export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode
  label: string // required, not optional — an icon-only button with no accessible name is exactly the kind of "usable" gap this redesign is meant to close
  active?: boolean
}

// A square icon-only button (nav items, canvas toolbar actions, close/remove
// buttons) — title AND aria-label both set from `label` so it's identifiable
// by mouse-hover tooltip and by a screen reader alike, not just one or the
// other.
export function IconButton({ icon, label, active, className, ...rest }: IconButtonProps) {
  return (
    <button className={['ui-icon-button', active ? 'active' : '', className].filter(Boolean).join(' ')} title={label} aria-label={label} {...rest}>
      {icon}
    </button>
  )
}
