---
name: scroll-story
description: Turn a plain-text script into a scrolling story (scrollytelling) - a map that flies between places, pictures that change, a before/after divider that moves with the reader's scroll, and text cards passing over them - as one HTML page (local images embedded; map steps need a connection), or as a Svelte 5 project for a newsroom's own build. Use when the user wants a scrollytelling piece, a map story, an explainer that walks readers through places or images, or a Svelte scrolly component for an investigation.
---

# Scroll story

Writes one HTML page (local images embedded) and, with `--svelte DIR`, a Svelte 5 + Vite project with the same
story: `Scrolly.svelte` (which step is on screen and how far through it the reader is), `StoryMap.svelte` (MapLibre,
OpenFreeMap tiles, no key) and `Compare.svelte` (a scroll-driven before/after). Light or dark theme; respects
"reduce motion" (the map jumps instead of flying); works on phones.

## The script

Help the user write a plain-text file like `examples/scroll-story/demo.md`:

```
---
title: The headline
dek: One line under it
byline: Who wrote it
theme: dark
sources: Where the facts and pictures came from
---

[map 20.88,-156.6 zoom=9.5 bearing=-15]
Text for this step. **Bold**, *italic* and [links](https://example.org) work. A blank line starts a new paragraph.

[map 20.8783,-156.6825 zoom=13.5 pitch=45 marker="Lahaina"]
...
[compare before.jpg after.jpg labels="29 Jul 2023|18 Aug 2023" credit="..."]
...
[image photo.jpg alt="What it shows" credit="Photo: ..." fit=cover]
...
[text]
A step with no picture: the graphic behind dims.
```

- Map steps take `zoom`, `pitch`, `bearing`, `marker="label"` or `markers="lat,lon,label;lat,lon,label"`.
- Every image needs `credit=` and `alt=` (the script reminds you).
- The before-after skill's images, the track-map PNGs and the other skills' exports work as image steps.

## Run

```
python3 scripts/story.py story.md                 # story.html next to it
python3 scripts/story.py story.md --svelte story-app/ && cd story-app && npm install && npm run build
```

The Svelte project needs Node 20.19+, 22.12+ or 24+ (Vite 8's requirement); its `dist/` is a static site with relative paths, ready for a CMS embed
or any static host.

## How to report

- Keep the sources footer: OpenStreetMap data must be credited, and so must every image.
- Keep each step to a few sentences: one idea per step reads best on a phone.

## Limits

- Map steps need a connection (MapLibre and OpenFreeMap tiles); image, compare and text steps work offline.
- Very large photos make a heavy single page: resize them to about 2000 px wide first.

## Will not do

- Map a private person's home or movements, or publish images the user has no right to use.
