/** Visibility of map location-label hotspots (誌 toggle). */

type Listener = () => void

let visible = true
const listeners = new Set<Listener>()

export const labelStore = {
  isVisible(): boolean {
    return visible
  },
  setVisible(next: boolean): void {
    if (next === visible) return
    visible = next
    for (const fn of listeners) fn()
  },
  toggle(): boolean {
    labelStore.setVisible(!visible)
    return visible
  },
  subscribe(fn: Listener): () => void {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },
}
