#!/usr/bin/env node
/**
 * Materialize public/ map assets from assets/ (real copies, not symlinks)
 * so Vite → dist and Vercel deploys work without local symlink hacks.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const publicDir = path.join(root, 'public')

function rmIfExists(p) {
  fs.rmSync(p, { recursive: true, force: true })
}

function copyFile(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true })
  fs.copyFileSync(src, dest)
}

/** Recursive copy (Node 16.7+ has fs.cpSync). */
function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true })
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name)
    const to = path.join(dest, entry.name)
    if (entry.isDirectory()) copyDir(from, to)
    else if (entry.isFile()) fs.copyFileSync(from, to)
  }
}

const previewSrc = path.join(root, 'assets', 'preview', 'map-preview.jpg')
const previewLowSrc = path.join(root, 'assets', 'preview', 'map-preview-low.jpg')
const tilesSrc = path.join(root, 'assets', 'tiles')
const dzi = path.join(tilesSrc, 'map.dzi')

let ok = true

if (!fs.existsSync(previewSrc)) {
  console.error(
    '[prepare-public] Missing assets/preview/map-preview.jpg — run npm run copy-previews',
  )
  ok = false
} else {
  rmIfExists(path.join(publicDir, 'map-preview.jpg'))
  copyFile(previewSrc, path.join(publicDir, 'map-preview.jpg'))
  console.log('[prepare-public] public/map-preview.jpg')
}

if (fs.existsSync(previewLowSrc)) {
  rmIfExists(path.join(publicDir, 'map-preview-low.jpg'))
  copyFile(previewLowSrc, path.join(publicDir, 'map-preview-low.jpg'))
  console.log('[prepare-public] public/map-preview-low.jpg')
}

if (!fs.existsSync(dzi)) {
  console.warn(
    '[prepare-public] No assets/tiles/map.dzi — deploy will be preview-only. Generate tiles locally and commit assets/tiles/.',
  )
  rmIfExists(path.join(publicDir, 'tiles'))
  fs.mkdirSync(path.join(publicDir, 'tiles'), { recursive: true })
} else {
  const tilesDest = path.join(publicDir, 'tiles')
  rmIfExists(tilesDest)
  copyDir(tilesSrc, tilesDest)
  console.log('[prepare-public] public/tiles/ (from assets/tiles)')
}

if (!ok) process.exit(1)
