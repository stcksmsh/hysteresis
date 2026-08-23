import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'patchbay-panel-order'

// Reordering is stored as a plain id array in localStorage — the panels
// themselves are still defined fresh every render in App.tsx (they close
// over live state), this hook only tracks *what order* to render them in.
// Merges in any ids the saved order doesn't know about (new panel added
// after the user already customized their layout) rather than resetting.
export function usePanelOrder(defaultOrder: string[]) {
  const [order, setOrder] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return defaultOrder
      const saved: unknown = JSON.parse(raw)
      if (!Array.isArray(saved)) return defaultOrder
      const known = saved.filter((id): id is string => typeof id === 'string' && defaultOrder.includes(id))
      const missing = defaultOrder.filter((id) => !known.includes(id))
      return [...known, ...missing]
    } catch {
      return defaultOrder
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(order))
    } catch {
      // best-effort persistence only
    }
  }, [order])

  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [dragOverId, setDragOverId] = useState<string | null>(null)

  const onDragStart = useCallback((id: string) => setDraggingId(id), [])
  const onDragEnd = useCallback(() => {
    setDraggingId(null)
    setDragOverId(null)
  }, [])
  const onDragOver = useCallback((id: string) => setDragOverId(id), [])
  const onDrop = useCallback((targetId: string) => {
    setDraggingId((dragged) => {
      if (dragged && dragged !== targetId) {
        setOrder((prev) => {
          const next = prev.filter((id) => id !== dragged)
          const idx = next.indexOf(targetId)
          next.splice(idx, 0, dragged)
          return next
        })
      }
      return null
    })
    setDragOverId(null)
  }, [])

  return { order, draggingId, dragOverId, onDragStart, onDragEnd, onDragOver, onDrop }
}
