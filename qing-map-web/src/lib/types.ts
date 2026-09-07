/** Shared annotation / overlay shapes — plain JSON under data/, readable by web and TouchDesigner. */

export type MapPoint = {
  /** Normalized X in image space, 0–1 left→right */
  x: number
  /** Normalized Y in image space, 0–1 top→bottom */
  y: number
}

export type Annotation = {
  id: string
  title: string
  body?: string
  /** Anchor on the map (normalized image coordinates) */
  point: MapPoint
  tags?: string[]
}

export type AnnotationCollection = {
  version: 1
  mapId: string
  annotations: Annotation[]
}

/** Closed ring of normalized points (first ≈ last optional). */
export type MapRing = MapPoint[]

export type OverlayStyle = 'crimson-glow' | 'yellow-glow'

export type OverlayFeature = {
  id: string
  title: string
  /** Outer ring first; subsequent rings are holes if needed */
  rings: MapRing[]
  style?: OverlayStyle
}

export type OverlayCollection = {
  version: 1
  mapId: string
  /** Optional group id for toggling several features together (e.g. handi-shibasheng) */
  groupId?: string
  title?: string
  overlays: OverlayFeature[]
}
