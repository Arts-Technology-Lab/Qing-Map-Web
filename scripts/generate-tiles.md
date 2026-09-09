# Generate Deep Zoom (DZI) tiles

The 234MB source JPG is too large to load directly in a browser. OpenSeadragon
needs a **Deep Zoom Image** pyramid: `assets/tiles/map.dzi` plus a
`assets/tiles/map_files/` folder of JPEG tiles.

## Prerequisites

1. Copy the source image:

```bash
npm run copy-source
```

2. Install [libvips](https://www.libvips.org/) (includes the `vips` CLI):

```bash
brew install vips
```

## Generate tiles

From the repo root:

```bash
mkdir -p assets/tiles
vips dzsave assets/source/map-super-res.jpg assets/tiles/map --layout dz
```

This writes:

- `assets/tiles/map.dzi`
- `assets/tiles/map_files/` (many small tile images)

Generation may take several minutes and use substantial disk space.

## Verify

```bash
ls -la assets/tiles/map.dzi
npm run dev
```

Open the local URL — the map should pan and zoom.

Tiles are served from `public/tiles` (symlink to `assets/tiles`), so Vite
exposes them at `/tiles/...` as normal static files.

## Alternative (ImageMagick)

If you cannot use libvips:

```bash
# Requires ImageMagick with deepzoom support; quality/options vary by version
magick assets/source/map-super-res.jpg -define dz:layout=dz assets/tiles/map.dzi
```

Prefer **vips** when possible — it is faster and memory-efficient for large scans.

## Notes

- `assets/source/` and `assets/tiles/` are gitignored (too large for git).
- Do not edit files under `20260730_object_painting/` — that folder is the raw archive.
