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
| [`public/audio/`](public/audio/) | Soundtrack MP3s (Mist Sheng, Chao Tian Zi, Jing Diao) |

Browser URLs: `/map-preview.jpg`, `/tiles/...` (copied into `public/` by `npm run prepare-public`).

## Soundtrack

Playback (see `src/lib/playlist.ts` / `AUDIO` in `src/config.ts`):

1. **Mist Sheng** loops on the intro seal screen  
2. Seal click → **Chao Tian Zi** (entry; volume 0.7, starts at 1s so the drum lands during Mist’s fade-out)  
3. **Jing Diao** once (transition)  
4. Then **Mist Sheng ↔ Jing Diao** loop  

### Autoplay note

Browsers often block audio until a user gesture. Mist Sheng tries to start on load; if it stays silent, tap the cloud veil (not the seal) to unlock it. Clicking the seal always starts Chao Tian Zi.

### Credits (original YouTube)

| Track | Source |
|---|---|
| Mist Sheng（雾笙） | [youtube.com/watch?v=Me8y6EKQcYk](https://www.youtube.com/watch?v=Me8y6EKQcYk) |
| Chao Tian Zi（朝天子） | [youtube.com/watch?v=0JSjMvkaS8Q](https://www.youtube.com/watch?v=0JSjMvkaS8Q) |
| Jing Diao（京調） | [youtube.com/watch?v=EMYsu8PvkYk](https://www.youtube.com/watch?v=EMYsu8PvkYk) |

## Quick start

```bash
cd qing-map-web
npm install
npm run copy-previews   # if preview JPGs are missing
npm run dev
```

## Deploy on Vercel

Repo root is a thin wrapper; the app is in `qing-map-web/`.

**Use Root Directory = `./` (repo root), not the `qing-map-web` subfolder** — Vercel’s UI breaks if you set both Vite and a nested root.

1. Commit/push root `vercel.json` + root `package.json` (just added).
2. Import `Arts-Technology-Lab/Qing-Map-Web`.
3. Root Directory: **Qing-Map-Web (root)** / `./`.
4. Framework: **Vite**.
5. Overrides off, **or**:
   - Build: `npm run build`
   - Output: `qing-map-web/dist`
   - Install: `npm install --prefix qing-map-web`
6. Deploy, then **Settings → Git → Enable Git LFS**.

URLs: `/` and `/atlab`.