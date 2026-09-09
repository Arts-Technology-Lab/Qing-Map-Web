# TouchDesigner compatibility

This app is a static web viewer. TouchDesigner can use it without a Node/Mongo backend.

## Load the viewer in TD

1. `npm run build` → output in `dist/`.
2. Host `dist/` with any static server (or Vite `npm run preview`), **or** point a **Web Render TOP** at the local/dev URL during development.
3. The map tiles must be available at `/tiles/` (the Vite plugin copies `assets/tiles` into `dist/tiles` on build).

## Shared data contract

Annotations live as plain JSON under `data/` (see `src/lib/types.ts`):

```json
{
  "version": 1,
  "mapId": "qing-object-painting",
  "annotations": [
    {
      "id": "gate-01",
      "title": "Example gate",
      "body": "Optional description",
      "point": { "x": 0.42, "y": 0.55 },
      "tags": ["architecture"]
    }
  ]
}
```

Coordinates are **normalized image space** (0–1). TD and the web app should read/write the same files or copies of them.

## Later: live sync

When needed, export viewer state (zoom, center, active annotation id) over WebSocket or OSC. Keep that transport thin so TD and the browser stay interchangeable consumers of the same JSON model.

## Do not

- Point TD at files inside `20260730_object_painting/` for editing — treat that folder as read-only archive.
- Commit `assets/source/` or `assets/tiles/` into git.
