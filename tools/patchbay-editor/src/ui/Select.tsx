import { IconChevronDown } from './icons'

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  uiSize?: 'sm' | 'md'
}

// Wraps the plain <select> styles.css already themes, adding a real chevron
// (the native select arrow is whatever the OS draws, which doesn't match
// this theme) via a non-interactive icon layered on top — the <select>
// itself stays a real native element throughout (full keyboard/screen-reader
// behavior for free), this is presentation only.
export function Select({ uiSize = 'md', className, children, ...rest }: SelectProps) {
  return (
    <span className={`ui-select-wrap ui-select-${uiSize}`}>
      <select className={['ui-select', className].filter(Boolean).join(' ')} {...rest}>
        {children}
      </select>
      <IconChevronDown size={12} className="ui-select-chevron" />
    </span>
  )
}
