/** Shared annotation shapes — plain JSON under data/, readable by web and TouchDesigner. */

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
