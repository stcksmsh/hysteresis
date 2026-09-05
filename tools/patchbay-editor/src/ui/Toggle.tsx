export interface ToggleProps {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
  disabled?: boolean
}

// A real switch instead of a bare checkbox (used today only for `map`'s
// clamp option) — same semantics, clearer at a glance against a dark theme
// than a native checkbox's OS-drawn box.
export function Toggle({ checked, onChange, label, disabled }: ToggleProps) {
  return (
    <label className={`ui-toggle${disabled ? ' ui-toggle-disabled' : ''}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="ui-toggle-track">
        <span className="ui-toggle-thumb" />
      </span>
      {label && <span className="ui-toggle-label">{label}</span>}
    </label>
  )
}
