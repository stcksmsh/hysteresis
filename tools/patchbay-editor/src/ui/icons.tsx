// A small, hand-authored inline-SVG icon set — replaces the raw emoji/Unicode
// characters (🐞⤢✕⊡▶⏸📁) scattered through the editor before this pass, which
// render however the OS's emoji font happens to draw them rather than
// matching this tool's own dark/accent-teal theme. No icon library dependency
// — consistent with this project's own precedent of reaching for a browser-
// native or hand-rolled solution over a new package when one is easy to
// author (native `resize`, native drag-and-drop). Every icon is a 20x20
// viewBox, stroke-based, `currentColor` throughout so it inherits whatever
// text color the surrounding button/label already has.
export interface IconProps {
  size?: number
  className?: string
}

const base = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

function Svg({ size = 16, className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" className={className} aria-hidden="true">
      {children}
    </svg>
  )
}

export function IconBug(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="6" y="6.5" width="8" height="9" rx="4" {...base} />
      <path d="M10 6.5V4M6.5 8.5 3.5 6M13.5 8.5 16.5 6M6.5 12.5H3M13.5 12.5H17M6.5 15.5 4 17.5M13.5 15.5 16 17.5M7.5 6.5c0-1.4 1.1-2.5 2.5-2.5s2.5 1.1 2.5 2.5" {...base} />
    </Svg>
  )
}

export function IconExpand(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 3H3v4M13 3h4v4M7 17H3v-4M13 17h4v-4" {...base} />
    </Svg>
  )
}

export function IconClose(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 5l10 10M15 5 5 15" {...base} />
    </Svg>
  )
}

export function IconFit(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="4" y="4" width="12" height="12" rx="2" {...base} />
      <path d="M7.5 7.5h5v5h-5z" {...base} />
    </Svg>
  )
}

export function IconPlay(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 4.2v11.6l9-5.8z" fill="currentColor" stroke="none" />
    </Svg>
  )
}

export function IconPause(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="5.5" y="4" width="3.2" height="12" rx="0.8" fill="currentColor" stroke="none" />
      <rect x="11.3" y="4" width="3.2" height="12" rx="0.8" fill="currentColor" stroke="none" />
    </Svg>
  )
}

export function IconFolder(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 6.5c0-.83.67-1.5 1.5-1.5H8l1.5 2H15.5c.83 0 1.5.67 1.5 1.5V14c0 .83-.67 1.5-1.5 1.5h-11C3.67 15.5 3 14.83 3 14z" {...base} />
    </Svg>
  )
}

export function IconGraph(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="4.5" cy="5" r="1.8" {...base} />
      <circle cx="4.5" cy="15" r="1.8" {...base} />
      <circle cx="15.5" cy="10" r="1.8" {...base} />
      <path d="M6.2 5.6 13.9 9.3M6.2 14.4 13.9 10.7" {...base} />
    </Svg>
  )
}

export function IconCode(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 6 3 10l4 4M13 6l4 4-4 4M11 4.5 9 15.5" {...base} />
    </Svg>
  )
}

export function IconOutput(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 12V6.5c0-.83.67-1.5 1.5-1.5h9c.83 0 1.5.67 1.5 1.5V12" {...base} />
      <path d="M2.5 12h15l-1.4 4.2a1 1 0 0 1-.95.68H4.85a1 1 0 0 1-.95-.68z" {...base} />
      <circle cx="10" cy="8.5" r="1.4" {...base} />
    </Svg>
  )
}

export function IconSave(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4.5 3.5h9L17 6v10.5a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1z" {...base} />
      <path d="M6.5 3.5v4h6v-4M6.5 17v-5h7v5" {...base} />
    </Svg>
  )
}

export function IconPlus(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M10 4.5v11M4.5 10h11" {...base} />
    </Svg>
  )
}

export function IconTrash(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4.5 6h11M8 6V4.5h4V6M6 6l.7 9.3a1 1 0 0 0 1 .95h4.6a1 1 0 0 0 1-.95L14 6" {...base} />
    </Svg>
  )
}

export function IconChevronDown(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 8l5 5 5-5" {...base} />
    </Svg>
  )
}

export function IconFile(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 3h5.5L15.5 7v9.5a1 1 0 0 1-1 1h-8.5a1 1 0 0 1-1-1v-12.5a1 1 0 0 1 1-1z" {...base} />
      <path d="M11.5 3v4h4" {...base} />
    </Svg>
  )
}
