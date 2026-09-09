# Preview images (working copies)

| File | Role |
|---|---|
| `map-preview.jpg` | 9MB mid-res — instant placeholder + OSD base under tiles |
| `map-preview-low.jpg` | 3MB fallback |

Copied from `20260730_object_painting/` (raw archive is never modified).

Commit these files (and `assets/tiles/`) so Vercel can serve the map.
`npm run prepare-public` copies them into `public/` for local/dev and CI builds.
