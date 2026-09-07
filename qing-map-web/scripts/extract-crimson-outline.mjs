#!/usr/bin/env node
/** Thin wrapper — runs the Python crimson contour extractor. */
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const script = path.join(root, 'scripts', 'extract-crimson-outline.py')

const result = spawnSync('python3', [script], {
  cwd: root,
  stdio: 'inherit',
})

process.exit(result.status ?? 1)
