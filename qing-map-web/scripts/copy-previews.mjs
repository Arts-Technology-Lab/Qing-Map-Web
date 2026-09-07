#!/usr/bin/env node
/**
 * Copy mid/low-res JPGs from the raw archive into assets/preview/.
 * Does not modify the originals. Then run prepare-public for public/.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, '..')
const mapRoot = path.resolve(projectRoot, '..')
const painting = path.join(mapRoot, '20260730_object_painting')

const copies = [
  {
    from: path.join(painting, 'High Res', '9MB JPG File_DSC3891-Edit.jpg'),
    to: path.join(projectRoot, 'assets', 'preview', 'map-preview.jpg'),
  },
  {
    from: path.join(painting, 'Low Res', '3MB JPG File_DSC3891-Edit.jpg'),
    to: path.join(projectRoot, 'assets', 'preview', 'map-preview-low.jpg'),
  },
]

const previewDir = path.join(projectRoot, 'assets', 'preview')
fs.mkdirSync(previewDir, { recursive: true })

for (const { from, to } of copies) {
  if (!fs.existsSync(from)) {
    console.error('Missing source:', from)
    process.exit(1)
  }
  fs.copyFileSync(from, to)
  console.log('OK assets/preview/', path.basename(to))
}

console.log('Run npm run prepare-public (or npm run dev/build) to refresh public/.')
