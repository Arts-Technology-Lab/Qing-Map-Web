import OpenSeadragon, { type Viewer, type TiledImage } from 'openseadragon'
import type { OverlayCollection, OverlayFeature, MapRing } from '../lib/types'
import { overlayStore } from './store'

function ringToPathD(ring: MapRing): string {
  if (ring.length === 0) return ''
  const [first, ...rest] = ring
  let d = `M ${first.x} ${first.y}`
  for (const p of rest) {
    d += ` L ${p.x} ${p.y}`
  }
  const last = rest.length ? rest[rest.length - 1] : first
  if (last.x !== first.x || last.y !== first.y) {
    d += ' Z'
  } else {
    d += ' Z'
  }
  return d
}

function buildFeatureGroup(feature: OverlayFeature): SVGGElement {
  const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  g.setAttribute('data-overlay-id', feature.id)
  g.classList.add('map-overlay-feature')
  if (feature.style === 'yellow-glow') {
    g.classList.add('style-yellow-glow')
  } else {
    g.classList.add('style-crimson-glow')
  }

  for (const ring of feature.rings) {
    const d = ringToPathD(ring)
    if (!d) continue

    // Soft outer bloom
    const glow = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    glow.setAttribute('d', d)
    glow.classList.add('overlay-stroke', 'overlay-stroke-glow')
    g.appendChild(glow)

    // Mid halo
    const mid = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    mid.setAttribute('d', d)
    mid.classList.add('overlay-stroke', 'overlay-stroke-mid')
    g.appendChild(mid)

    // Sharp rim
    const core = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    core.setAttribute('d', d)
    core.classList.add('overlay-stroke', 'overlay-stroke-core')
    g.appendChild(core)
  }

  return g
}

export type SvgOverlayLayer = {
  root: HTMLDivElement
  svg: SVGSVGElement
  setActiveIds: (ids: ReadonlySet<string>) => void
  destroy: () => void
}

/**
 * Full-image SVG overlay locked to the map via OpenSeadragon addOverlay.
 * Paths use normalized image coordinates (viewBox 0 0 1 1).
 */
export function attachSvgOverlayLayer(
  viewer: Viewer,
  collection: OverlayCollection,
): SvgOverlayLayer {
  const root = document.createElement('div')
  root.className = 'map-overlay-layer'
  root.setAttribute('aria-hidden', 'true')

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('viewBox', '0 0 1 1')
  svg.setAttribute('preserveAspectRatio', 'none')
  svg.classList.add('map-overlay-svg')

  const groups = new Map<string, SVGGElement>()
  for (const feature of collection.overlays) {
    const g = buildFeatureGroup(feature)
    groups.set(feature.id, g)
    svg.appendChild(g)
  }

  root.appendChild(svg)

  let attached = false
  const place = () => {
    const item = viewer.world.getItemAt(0) as TiledImage | null
    if (!item) return
    const bounds = item.getBounds()
    const loc = new OpenSeadragon.Rect(bounds.x, bounds.y, bounds.width, bounds.height)
    if (!attached) {
      viewer.addOverlay({
        element: root,
        location: loc,
        checkResize: false,
      })
      attached = true
    } else {
      viewer.updateOverlay(root, loc)
    }
  }

  const onOpen = () => place()
  if (viewer.world.getItemAt(0)) {
    place()
  } else {
    viewer.addHandler('open', onOpen)
  }

  const setActiveIds = (ids: ReadonlySet<string>) => {
    let any = false
    for (const [id, g] of groups) {
      const on = ids.has(id)
      g.classList.toggle('is-active', on)
      if (on) any = true
    }
    root.classList.toggle('is-active', any)
  }

  setActiveIds(overlayStore.getVisible())

  const destroy = () => {
    viewer.removeHandler('open', onOpen)
    if (attached) {
      try {
        viewer.removeOverlay(root)
      } catch {
        /* already gone */
      }
      attached = false
    }
    root.remove()
  }

  return { root, svg, setActiveIds, destroy }
}
