import OpenSeadragon from 'openseadragon'
import {
  flipXForDrift,
  pickCloudAsset,
  rand,
  randomFocusCloudPx,
  type CloudDriftDir,
  type CloudHeadSide,
} from '../lib/clouds'

type Viewer = OpenSeadragon.Viewer
type TiledImage = OpenSeadragon.TiledImage

const FOCUS_CLOUD_COUNT = 24
const VIEWPORT_AVOID_ZOOM = 2
/** Cursor evade radius as fraction of the *visible* viewport min-dimension. */
const CURSOR_AVOID_FRAC = 0.16
/** Peak vertical flee speed relative to cruise speed (at cursor center). */
const CURSOR_NUDGE = 1.15
/** How quickly vy eases toward the evade target (1/s). */
const CURSOR_VY_LERP = 6
/** Native puff art aspect (width / height) — keeps OSD box from letterboxing. */
const CLOUD_ASPECT = 1354 / 665

type Cloud = {
  el: HTMLElement
  inner: HTMLElement
  widthImg: number
  heightImg: number
  vpW: number
  vpH: number
  x: number
  y: number
  speed: number
  dir: CloudDriftDir
  headSide: CloudHeadSide
  src: string
  /** Smoothed vertical velocity (image px / s) for curved evade paths. */
  vy: number
  /** Sticky evade sign: -1 up, +1 down, 0 unset. */
  evadeSign: -1 | 0 | 1
}

export type FocusCloudsHandle = {
  stop: () => void
}

export type StartFocusCloudsOptions = {
  /** Element used for pointer → image mapping (usually the OSD root). */
  canvas: HTMLElement
  count?: number
  /**
   * Floor / locked-home displays: skip deep-zoom flee (viewport stays at home).
   * Cursor nudge still works if the canvas receives pointers.
   */
  lockedHome?: boolean
}

/**
 * Spawn drifting focus mist on a viewer. Caller owns enter/exit lifecycle.
 */
export function startFocusClouds(
  viewer: Viewer,
  opts: StartFocusCloudsOptions,
): FocusCloudsHandle {
  const canvas = opts.canvas
  const count = opts.count ?? FOCUS_CLOUD_COUNT
  const lockedHome = opts.lockedHome === true

  let clouds: Cloud[] = []
  let raf = 0
  let lastTs = 0
  let cursorImg: { x: number; y: number } | null = null
  let running = true
  let preferReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const onMotionPref = (e: MediaQueryListEvent) => {
    preferReducedMotion = e.matches
  }
  const motionMq = window.matchMedia('(prefers-reduced-motion: reduce)')
  motionMq.addEventListener('change', onMotionPref)

  const applyFacing = (
    inner: HTMLElement,
    headSide: CloudHeadSide,
    dir: CloudDriftDir,
  ) => {
    const flipX = flipXForDrift(headSide, dir)
    inner.style.setProperty('--fc-flip-x', String(flipX))
    inner.style.setProperty('--fc-flip-y', '1')
  }

  const onDrawCloud = (
    position: OpenSeadragon.Point,
    size: OpenSeadragon.Point,
    element: Element,
  ) => {
    const el = element as HTMLElement
    const wrapper = el.parentElement
    const w = Math.max(1, Math.round(size.x))
    const h = Math.max(1, Math.round(size.y))
    if (wrapper) {
      wrapper.style.left = '0'
      wrapper.style.top = '0'
      wrapper.style.transform = `translate3d(${position.x}px, ${position.y}px, 0)`
      wrapper.style.transformOrigin = '0 0'
      wrapper.style.display = 'block'
    }
    el.style.display = 'block'
    el.style.width = `${w}px`
    el.style.height = `${h}px`
    el.style.transform = ''
  }

  const syncOverlay = (cloud: Cloud, item: TiledImage) => {
    const topLeft = item.imageToViewportCoordinates(
      cloud.x - cloud.widthImg / 2,
      cloud.y - cloud.heightImg / 2,
    )
    viewer.updateOverlay(
      cloud.el,
      new OpenSeadragon.Rect(topLeft.x, topLeft.y, cloud.vpW, cloud.vpH),
    )
  }

  const wrapAlongFacing = (cloud: Cloud, size: OpenSeadragon.Point) => {
    if (cloud.dir === 1 && cloud.x > size.x + cloud.widthImg * 0.45) {
      cloud.x = -cloud.widthImg * 0.35
      cloud.y = rand(size.y * 0.08, size.y * 0.9)
    } else if (cloud.dir === -1 && cloud.x < -cloud.widthImg * 0.45) {
      cloud.x = size.x + cloud.widthImg * 0.35
      cloud.y = rand(size.y * 0.08, size.y * 0.9)
    }
  }

  const tick = (ts: number) => {
    if (!running) return
    const item = viewer.world.getItemAt(0)
    if (!item) {
      raf = requestAnimationFrame(tick)
      return
    }

    const dt = lastTs ? Math.min(0.05, (ts - lastTs) / 1000) : 0.016
    lastTs = ts

    const size = item.getContentSize()
    const homeZoom = viewer.viewport.getHomeZoom()
    const zoom = viewer.viewport.getZoom(true)
    const deepZoom = !lockedHome && zoom >= homeZoom * VIEWPORT_AVOID_ZOOM
    const speedScale = preferReducedMotion ? 0.2 : 1

    const bounds = viewer.viewport.getBounds(true)
    const vtl = item.viewportToImageCoordinates(bounds.getTopLeft())
    const vbr = item.viewportToImageCoordinates(bounds.getBottomRight())
    // Evade radius in image px must track the *visible* viewport, not the
    // full map — otherwise the on-screen avoid zone balloons when zoomed in.
    const viewW = Math.abs(vbr.x - vtl.x)
    const viewH = Math.abs(vbr.y - vtl.y)
    const cursorR = Math.min(viewW, viewH) * CURSOR_AVOID_FRAC

    for (const cloud of clouds) {
      let spd = cloud.speed * speedScale
      if (deepZoom) {
        const inside =
          cloud.x > vtl.x - cloud.widthImg * 0.1 &&
          cloud.x < vbr.x + cloud.widthImg * 0.1 &&
          cloud.y > vtl.y - cloud.heightImg * 0.1 &&
          cloud.y < vbr.y + cloud.heightImg * 0.1
        if (inside) spd *= 2.2
      }

      let vx = cloud.dir * spd
      let vyTarget = 0

      if (cursorImg) {
        const dx = cloud.x - cursorImg.x
        const dy = cloud.y - cursorImg.y
        const dCursor = Math.hypot(dx, dy)
        if (dCursor < cursorR && dCursor > 1) {
          const falloff = 1 - dCursor / cursorR
          const strength = falloff * falloff
          if (cloud.evadeSign === 0) {
            cloud.evadeSign = dy >= 0 ? 1 : -1
          }
          vyTarget = cloud.evadeSign * spd * CURSOR_NUDGE * (0.55 + 0.45 * strength)
          vx *= 1 - 0.35 * strength
        } else {
          cloud.evadeSign = 0
        }
      } else {
        cloud.evadeSign = 0
      }

      const blend = 1 - Math.exp(-CURSOR_VY_LERP * dt)
      cloud.vy += (vyTarget - cloud.vy) * blend

      cloud.x += vx * dt
      cloud.y = clamp(cloud.y + cloud.vy * dt, size.y * 0.04, size.y * 0.96)
      wrapAlongFacing(cloud, size)
      syncOverlay(cloud, item)
    }

    raf = requestAnimationFrame(tick)
  }

  /**
   * Pointer → image coords via the OSD container (what pointFromPixel expects).
   * Divide by CSS scale (ATLab fit) so layout px match _containerInnerSize at any zoom.
   */
  const pointerToImage = (e: PointerEvent): { x: number; y: number } | null => {
    const item = viewer.world.getItemAt(0)
    if (!item) return null
    const el = viewer.container as HTMLElement
    const rect = el.getBoundingClientRect()
    const sx = rect.width / Math.max(1, el.clientWidth)
    const sy = rect.height / Math.max(1, el.clientHeight)
    const pixel = new OpenSeadragon.Point(
      (e.clientX - rect.left) / sx,
      (e.clientY - rect.top) / sy,
    )
    const img = item.viewerElementToImageCoordinates(pixel)
    return { x: img.x, y: img.y }
  }

  const onPointerMove = (e: PointerEvent) => {
    if (!running) return
    cursorImg = pointerToImage(e)
  }

  const onPointerLeave = () => {
    cursorImg = null
  }

  const item = viewer.world.getItemAt(0)
  if (!item) {
    motionMq.removeEventListener('change', onMotionPref)
    return {
      stop: () => {
        /* nothing spawned */
      },
    }
  }

  const size = item.getContentSize()
  clouds = []

  for (let i = 0; i < count; i++) {
    const el = document.createElement('div')
    el.className = 'focus-cloud'
    const inner = document.createElement('div')
    inner.className = 'focus-cloud-inner'
    el.append(inner)

    const asset = pickCloudAsset()
    const dir: CloudDriftDir = Math.random() < 0.5 ? 1 : -1
    applyFacing(inner, asset.headSide, dir)
    inner.style.backgroundImage = `url('${asset.src}')`

    const widthImg = randomFocusCloudPx()
    const heightImg = widthImg / CLOUD_ASPECT
    const vpW = widthImg / size.x
    const vpH = heightImg / size.x
    const x =
      Math.random() < 0.78
        ? rand(size.x * 0.2, size.x * 0.58)
        : rand(size.x * 0.1, size.x * 0.88)
    const y =
      Math.random() < 0.7
        ? rand(size.y * 0.14, size.y * 0.52)
        : rand(size.y * 0.08, size.y * 0.9)
    const speed = (size.x * rand(0.14, 0.24)) / rand(75, 110)

    const cloud: Cloud = {
      el,
      inner,
      widthImg,
      heightImg,
      vpW,
      vpH,
      x,
      y,
      speed,
      dir,
      headSide: asset.headSide,
      src: asset.src,
      vy: 0,
      evadeSign: 0,
    }

    const topLeft = item.imageToViewportCoordinates(
      x - widthImg / 2,
      y - heightImg / 2,
    )
    viewer.addOverlay({
      element: el,
      location: new OpenSeadragon.Rect(topLeft.x, topLeft.y, vpW, vpH),
      checkResize: false,
      onDraw: onDrawCloud,
    })

    clouds.push(cloud)
  }

  requestAnimationFrame(() => {
    for (const c of clouds) c.el.classList.add('is-visible')
  })

  lastTs = 0
  raf = requestAnimationFrame(tick)
  canvas.addEventListener('pointermove', onPointerMove)
  canvas.addEventListener('pointerleave', onPointerLeave)

  return {
    stop: () => {
      if (!running) return
      running = false
      cancelAnimationFrame(raf)
      raf = 0
      cursorImg = null
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerleave', onPointerLeave)
      motionMq.removeEventListener('change', onMotionPref)

      for (const c of clouds) c.el.classList.remove('is-visible')

      window.setTimeout(() => {
        for (const c of clouds) {
          try {
            viewer.removeOverlay(c.el)
          } catch {
            /* already removed */
          }
        }
        clouds = []
      }, 650)
    },
  }
}

/** Wall chrome: toggle 淨 focus mist on/off. */
export function mountFocusMode(viewer: Viewer): void {
  const app = document.querySelector<HTMLElement>('#app')
  const btn = document.querySelector<HTMLButtonElement>('#btn-focus')
  const canvas = document.querySelector<HTMLElement>('#viewer')
  if (!app || !btn || !canvas) {
    throw new Error('Missing focus-mode controls')
  }

  let handle: FocusCloudsHandle | null = null

  const enter = () => {
    if (handle) return
    app.classList.add('focus-mode')
    btn.setAttribute('aria-pressed', 'true')
    handle = startFocusClouds(viewer, { canvas })
    if (!viewer.world.getItemAt(0)) {
      handle.stop()
      handle = null
      app.classList.remove('focus-mode')
      btn.setAttribute('aria-pressed', 'false')
    }
  }

  const exit = () => {
    if (!handle) return
    btn.setAttribute('aria-pressed', 'false')
    handle.stop()
    handle = null
    window.setTimeout(() => {
      app.classList.remove('focus-mode')
    }, 650)
  }

  btn.addEventListener('click', () => {
    if (handle) exit()
    else enter()
  })

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && handle) {
      e.preventDefault()
      exit()
    }
  })
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}
