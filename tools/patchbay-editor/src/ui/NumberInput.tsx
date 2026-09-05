import { useRef, useState } from 'react'

export interface NumberInputProps {
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
  max?: number
  width?: number
  disabled?: boolean
  title?: string
}

const DRAG_THRESHOLD_PX = 3 // how far the pointer has to move before a click becomes a drag-scrub, so a plain click-to-focus-and-type still works
const DRAG_PIXELS_PER_STEP = 4 // how many px of horizontal drag equals one `step` increment

// The concrete "usable, easily navigable" win this redesign's plan called
// out: today every gain/offset/threshold/cut value in the graph inspector is
// a bare <input type=number> that only accepts typed values. This adds
// click-and-drag-to-scrub (the same interaction Figma/After Effects/Blender
// number fields use) on top of the native input — a plain click still
// focuses it for typing (nothing intercepts the gesture until real
// horizontal movement is detected), a click-drag adjusts the value directly
// without ever needing the keyboard.
export function NumberInput({ value, onChange, step = 0.05, min, max, width = 64, disabled, title }: NumberInputProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const dragState = useRef<{ startX: number; startValue: number; dragged: boolean } | null>(null)
  const [dragging, setDragging] = useState(false)

  function clampVal(v: number): number {
    let out = v
    if (min !== undefined) out = Math.max(min, out)
    if (max !== undefined) out = Math.min(max, out)
    return out
  }

  function onPointerDown(e: React.PointerEvent<HTMLInputElement>) {
    if (disabled) return
    dragState.current = { startX: e.clientX, startValue: value, dragged: false }
    const onMove = (ev: PointerEvent) => {
      const state = dragState.current
      if (!state) return
      const dx = ev.clientX - state.startX
      if (!state.dragged && Math.abs(dx) < DRAG_THRESHOLD_PX) return
      if (!state.dragged) {
        state.dragged = true
        setDragging(true)
        inputRef.current?.blur() // stop it looking/behaving like a text cursor is active mid-drag
      }
      const delta = (dx / DRAG_PIXELS_PER_STEP) * step
      onChange(clampVal(Number((state.startValue + delta).toFixed(6))))
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      setDragging(false)
      dragState.current = null
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  return (
    <input
      ref={inputRef}
      type="number"
      className={`ui-number-input${dragging ? ' ui-number-input-dragging' : ''}`}
      style={{ width }}
      step={step}
      min={min}
      max={max}
      value={value}
      disabled={disabled}
      title={title ?? 'Click and drag horizontally to adjust, or click to type a value'}
      onChange={(e) => onChange(Number(e.target.value))}
      onPointerDown={onPointerDown}
    />
  )
}
