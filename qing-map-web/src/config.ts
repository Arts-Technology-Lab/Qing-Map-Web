/**
 * Site / exhibition config — change here (or later from an API) rather than in the UI.
 */
export type UiTheme = 'bronze' | 'silver'

/** Chrome theme: silver (default) or bronze. Not exposed as an end-user control. */
export const UI_THEME: UiTheme = 'silver'

/**
 * Intro zoom target — normalized image coordinates (0–1), approx. Xi’an / Luoyang.
 * Tweak if the geographic framing of the scan differs.
 */
export const INTRO_FOCUS = {
  x: 0.44,
  /** Higher on the scan (smaller y) — Central Plains / Guanzhong–Luoyang belt */
  y: 0.34,
  /** Multiplier of home zoom while focused (higher = closer). */
  zoomFactor: 3.6,
} as const

/**
 * ATLab dual-canvas layout (wall + floor stacked).
 * Browse at `/atlab` — fixed pixel frame for the exhibition screens.
 */
export const ATLAB = {
  width: 3536,
  wallHeight: 808,
  floorHeight: 2400,
} as const
