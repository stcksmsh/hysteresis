import { IconGraph, IconCode, IconOutput, IconBug } from './ui/icons'
import type { Screen } from './screens'

const SCREENS: { id: Screen; label: string; icon: (props: { size?: number }) => React.ReactNode }[] = [
  { id: 'graph', label: 'Patch Graph', icon: (p) => <IconGraph {...p} /> },
  { id: 'shaders', label: 'Shaders', icon: (p) => <IconCode {...p} /> },
  { id: 'output', label: 'Output', icon: (p) => <IconOutput {...p} /> },
  { id: 'diagnostics', label: 'Diagnostics', icon: (p) => <IconBug {...p} /> },
]

// The redesign's navigation answer (plan's "IA rework"): 4 real, distinct
// screens instead of one dense workspace (graph hero + always-visible
// 320px rail + an overlay debug drawer). Each screen below now gets full
// width when active, instead of permanently competing for it.
export function NavBar({ active, onSelect }: { active: Screen; onSelect: (s: Screen) => void }) {
  return (
    <nav className="nav-bar">
      {SCREENS.map((s) => (
        <button key={s.id} className={active === s.id ? 'nav-tab active' : 'nav-tab'} onClick={() => onSelect(s.id)}>
          {s.icon({ size: 15 })}
          {s.label}
        </button>
      ))}
    </nav>
  )
}
