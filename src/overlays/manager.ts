import type { Viewer } from 'openseadragon'
import type { OverlayCollection, OverlayFeature } from '../lib/types'
import handiCollection from '../../data/overlays/handi-shibasheng.json'
import zhongguoCollection from '../../data/overlays/zhongguo.json'
import { overlayStore } from './store'
import { attachSvgOverlayLayer, type SvgOverlayLayer } from './svgLayer'

export const HANDI_GROUP_ID = 'handi-shibasheng'
export const ZHONGGUO_GROUP_ID = 'zhongguo'

export type OverlayManager = {
  collection: OverlayCollection
  /** All feature ids across loaded overlay JSON files */
  featureIds: string[]
  idsForGroup: (groupId: string) => string[]
  attach: (viewer: Viewer) => () => void
  destroyAll: () => void
}

let singleton: OverlayManager | null = null

function asCollection(raw: unknown): OverlayCollection {
  return raw as OverlayCollection
}

function mergeCollections(parts: OverlayCollection[]): OverlayCollection {
  const overlays: OverlayFeature[] = []
  for (const part of parts) {
    overlays.push(...part.overlays)
  }
  return {
    version: 1,
    mapId: parts[0]?.mapId ?? 'qing-object-painting',
    overlays,
  }
}

/**
 * Loads overlay JSON once and can attach SVG layers to multiple OSD viewers
 * (wall + ATLab floor) that share overlayStore visibility.
 */
export function getOverlayManager(): OverlayManager {
  if (singleton) return singleton

  const parts = [asCollection(handiCollection), asCollection(zhongguoCollection)]
  const collection = mergeCollections(parts)
  const featureIds = collection.overlays.map((o) => o.id)

  const groupMap = new Map<string, string[]>()
  for (const part of parts) {
    const gid = part.groupId ?? part.overlays[0]?.id
    if (!gid) continue
    groupMap.set(
      gid,
      part.overlays.map((o) => o.id),
    )
  }

  const layers: SvgOverlayLayer[] = []
  const unsubs: Array<() => void> = []

  const sync = (visible: ReadonlySet<string>) => {
    for (const layer of layers) layer.setActiveIds(visible)
  }

  unsubs.push(overlayStore.subscribe(sync))

  singleton = {
    collection,
    featureIds,
    idsForGroup(groupId: string) {
      return groupMap.get(groupId) ?? [groupId]
    },
    attach(viewer: Viewer) {
      const layer = attachSvgOverlayLayer(viewer, collection)
      layers.push(layer)
      layer.setActiveIds(overlayStore.getVisible())
      return () => {
        const i = layers.indexOf(layer)
        if (i >= 0) layers.splice(i, 1)
        layer.destroy()
      }
    },
    destroyAll() {
      for (const u of unsubs) u()
      unsubs.length = 0
      for (const layer of layers) layer.destroy()
      layers.length = 0
      singleton = null
    },
  }

  return singleton
}

export function mountOverlaysOnViewer(viewer: Viewer): () => void {
  return getOverlayManager().attach(viewer)
}
