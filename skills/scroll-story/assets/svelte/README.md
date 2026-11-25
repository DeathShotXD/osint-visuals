# Story (Svelte 5 + Vite)

Written by osint-visuals `scroll-story`. The story is in `src/story.json` and its images in `public/media/`.

Needs Node 20.19+, 22.12+ or 24+ (Vite 8's requirement).

```
npm install
npm run dev      # local preview with hot reload
npm run build    # a static site in dist/ (relative paths: it works from any folder)
```

- `src/lib/Scrolly.svelte`: which step is on screen and how far through it the reader is.
- `src/lib/StoryMap.svelte`: the MapLibre map (OpenFreeMap tiles, no key) that flies between map steps.
- `src/lib/Compare.svelte`: the before/after divider, driven by scroll progress.

Keep the "Sources and credits" footer: OpenStreetMap data is under the ODbL and must be credited, and every image
needs its credit.
