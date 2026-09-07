#!/usr/bin/env node
/**
 * Copy the 234MB super-resolution JPG from the raw archive folder into
 * assets/source/map-super-res.jpg. Does not modify the original.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, '..')
const mapRoot = path.resolve(projectRoot, '..')

const SOURCE_NAME =
  '234MB JPG File_Super Resolution_18438x10516px_DSC3891-Edit.jpg'
const sourcePath = path.join(
  mapRoot,
  '20260730_object_painting',
  'High Res',
  SOURCE_NAME,
)
const destDir = path.join(projectRoot, 'assets', 'source')
const destPath = path.join(destDir, 'map-super-res.jpg')

if (!fs.existsSync(sourcePath)) {
  console.error('Source image not found:', sourcePath)
  process.exit(1)
}

fs.mkdirSync(destDir, { recursive: true })

if (fs.existsSync(destPath)) {
  const srcStat = fs.statSync(sourcePath)
  const destStat = fs.statSync(destPath)
  if (srcStat.size === destStat.size) {
    console.log('Already present (same size):', destPath)
    process.exit(0)
  }
}

console.log('Copying (~234MB)…')
console.log('  from:', sourcePath)
console.log('  to:  ', destPath)
fs.copyFileSync(sourcePath, destPath)
console.log('Done.')
console.log('Next: generate DZI tiles — see scripts/generate-tiles.md')
