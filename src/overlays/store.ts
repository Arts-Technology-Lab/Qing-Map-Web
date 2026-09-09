/** Shared visibility state for map overlays (wall + floor subscribe to the same store). */

type Listener = (visible: ReadonlySet<string>) => void

const visible = new Set<string>()
const listeners = new Set<Listener>()

function emit(): void {
  const snapshot = new Set(visible)
  for (const fn of listeners) fn(snapshot)
}

export const overlayStore = {
  isVisible(id: string): boolean {
    return visible.has(id)
  },

  setVisible(id: string, on: boolean): void {
    const had = visible.has(id)
    if (on && !had) {
      visible.add(id)
      emit()
    } else if (!on && had) {
      visible.delete(id)
      emit()
    }
  },

  toggle(id: string): boolean {
    const next = !visible.has(id)
    overlayStore.setVisible(id, next)
    return next
  },

  /** Show/hide every id in the list as one atomic update. */
  setGroupVisible(ids: readonly string[], on: boolean): void {
    let changed = false
    for (const id of ids) {
      if (on && !visible.has(id)) {
        visible.add(id)
        changed = true
      } else if (!on && visible.has(id)) {
        visible.delete(id)
        changed = true
      }
    }
    if (changed) emit()
  },

  toggleGroup(ids: readonly string[]): boolean {
    const on = !ids.every((id) => visible.has(id))
    overlayStore.setGroupVisible(ids, on)
    return on
  },

  subscribe(fn: Listener): () => void {
    listeners.add(fn)
    fn(new Set(visible))
    return () => {
      listeners.delete(fn)
    }
  },

  getVisible(): ReadonlySet<string> {
    return new Set(visible)
  },
}
