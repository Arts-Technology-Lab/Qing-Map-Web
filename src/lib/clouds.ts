/** Dunhuang xiangyun puff sprites with native head-side annotations. */
export type CloudHeadSide = 'left' | 'right'

export type CloudPuffAsset = {
  src: string
  /** Side of the PNG where the rounded head sits (before any CSS flip). */
  headSide: CloudHeadSide
}

/**
 * Backend facing table — keep in sync with art.
 * head left  → faces left  → float RTL unless flipped
 * head right → faces right → float LTR unless flipped
 */
export const CLOUD_PUFF_ASSETS: readonly CloudPuffAsset[] = [
  { src: '/intro/cloud-puff-a.png', headSide: 'left' },
  { src: '/intro/cloud-puff-b.png', headSide: 'left' },
  { src: '/intro/cloud-puff-c.png', headSide: 'right' }, // mirrored of a
  { src: '/intro/cloud-puff-d.png', headSide: 'left' },
] as const

export const CLOUD_PUFF_SRCS = CLOUD_PUFF_ASSETS.map((a) => a.src)

export const CLOUD_PUFF_SRC = CLOUD_PUFF_ASSETS[0]!.src

/** Drift dir: +1 = LTR (head must face right), -1 = RTL (head must face left). */
export type CloudDriftDir = 1 | -1

export function rand(min: number, max: number): number {
  return min + Math.random() * (max - min)
}

export function pickCloudAsset(): CloudPuffAsset {
  return CLOUD_PUFF_ASSETS[Math.floor(Math.random() * CLOUD_PUFF_ASSETS.length)]!
}

export function pickCloudSrc(): string {
  return pickCloudAsset().src
}

/**
 * CSS scaleX so the rounded head faces the drift direction.
 * wantHeadRight ≡ driftDir === +1
 */
export function flipXForDrift(headSide: CloudHeadSide, driftDir: CloudDriftDir): 1 | -1 {
  const wantHeadRight = driftDir === 1
  const nativeHeadRight = headSide === 'right'
  return wantHeadRight === nativeHeadRight ? 1 : -1
}

/** Random flip / stretch / rotate for intro veil variety (not focus drift). */
export function randomCloudShape(): {
  flipX: number
  flipY: number
  stretchX: number
  stretchY: number
  rot: number
} {
  return {
    flipX: Math.random() < 0.5 ? -1 : 1,
    flipY: Math.random() < 0.12 ? -1 : 1,
    stretchX: rand(0.85, 1.2),
    stretchY: rand(0.8, 1.15),
    rot: rand(-18, 18),
  }
}

export function applyCloudShape(el: HTMLElement, prefix = ''): void {
  const s = randomCloudShape()
  const p = prefix ? `${prefix}-` : ''
  el.style.setProperty(`--${p}flip-x`, String(s.flipX))
  el.style.setProperty(`--${p}flip-y`, String(s.flipY))
  el.style.setProperty(`--${p}stretch-x`, String(s.stretchX))
  el.style.setProperty(`--${p}stretch-y`, String(s.stretchY))
  el.style.setProperty(`--${p}rot`, `${s.rot}deg`)
}

export function evenScatterPoints(
  count: number,
  opts?: { margin?: number; jitter?: number },
): { x: number; y: number }[] {
  const margin = opts?.margin ?? 4
  const jitter = opts?.jitter ?? 0.42
  const cols = Math.ceil(Math.sqrt(count * 1.35))
  const rows = Math.ceil(count / cols)
  const usableW = 100 - margin * 2
  const usableH = 100 - margin * 2
  const cellW = usableW / cols
  const cellH = usableH / rows
  const pts: { x: number; y: number }[] = []
  const order = Array.from({ length: cols * rows }, (_, i) => i)
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[order[i], order[j]] = [order[j]!, order[i]!]
  }
  for (let n = 0; n < count; n++) {
    const idx = order[n]!
    const c = idx % cols
    const r = Math.floor(idx / cols)
    const jx = (Math.random() - 0.5) * cellW * jitter
    const jy = (Math.random() - 0.5) * cellH * jitter
    pts.push({
      x: clampPct(margin + (c + 0.5) * cellW + jx, margin, 100 - margin),
      y: clampPct(margin + (r + 0.5) * cellH + jy, margin, 100 - margin),
    })
  }
  return pts
}

function clampPct(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

export function randomFocusCloudPx(): number {
  const roll = Math.random()
  if (roll < 0.4) return rand(180, 340)
  if (roll < 0.75) return rand(340, 520)
  if (roll < 0.92) return rand(520, 780)
  return rand(780, 1050)
}
