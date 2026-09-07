# Qing Map Web

Vite + TypeScript + OpenSeadragon viewer for a Qing dynasty map scan.

**Load sequence:** HTML shows the mid-res preview instantly → OpenSeadragon opens with that same preview as the **base world layer** → high-res DZI tiles stack **directly on top** (same position/size). Unloaded tiles are transparent so the preview shows through.

Raw archive (`../20260730_object_painting/`) is never modified.

## Asset locations

| Path | What |
|---|---|
| [`assets/preview/`](assets/preview/) | Mid/low-res map previews (**commit for Vercel**) |
| [`assets/ui/`](assets/ui/) | Bronze badges + golden paper chrome (also in `public/ui/`) |
| `assets/tiles/` | DZI pyramid (`map.dzi` + `map_files/`) (**commit for Vercel**) |
| `assets/source/` | optional 234MB super-res copy (gitignored) |
| `assets/patterns/` | Letterbox wave fill |

Browser URLs: `/map-preview.jpg`, `/tiles/...` (copied into `public/` by `npm run prepare-public`).

## Quick start

```bash
cd qing-map-web
npm install
npm run copy-previews   # if preview JPGs are missing
npm run dev
```

## Deploy on Vercel

1. Push this repo to GitHub (include `qing-map-web/assets/preview/` and `qing-map-web/assets/tiles/`).
2. Import the repo in Vercel → set **Root Directory** to `qing-map-web`.
3. Framework preset: Vite (or leave defaults — `vercel.json` sets build/output).
4. Deploy. URLs:
   - `/` — interactive wall viewer
   - `/atlab` — wall + floor dual canvas

Do **not** commit `assets/source/` (super-res). Preview + tiles are enough for production.