---
name: before-after
description: Make a before-and-after satellite comparison readers can drag - with free NASA imagery for a place and two dates (the clearest pass near each date is picked automatically) or with the user's own licensed images - labelled with dates, annotations and credits, exportable as PNG or a sweep video for social media. Use when the user wants to show change on the ground (fire, flood, construction, destruction, a dried lake), asks for a before/after slider, or has two satellite images to compare.
---

# Before and after

Makes one self-contained HTML page (both images embedded, works offline): a slider, side-by-side or flicker view,
the dates on each picture, optional annotations, and the imagery credit drawn on the canvas, so every export
(PNG, or a WebM where the divider sweeps across and back) carries it. Frames: 1:1, 4:5, 16:9, 9:16.

## Two ways in

1. **The user's own images** (commercial imagery they licensed, or images they may publish):
   ```
   python3 scripts/before_after.py --before-image a.jpg --after-image b.jpg --before-label "3 Aug 2023" \
       --after-label "9 Aug 2023" --credit "Satellite images: <owner>" --title "..."
   ```
   Ask who owns the images; `--credit` goes on the graphic. Annotations use positions in the picture:
   `--mark "40%,55%,Bridge"`.
2. **Free NASA imagery** for a place and two dates:
   ```
   python3 scripts/before_after.py --lat 20.873 --lon -156.677 --km 1.8 --before 2023-08-05 --after 2023-08-10 \
       --mark "20.8783,-156.6825,Lahaina" --title "..."
   ```
   The script looks back from the "before" date and forward from the "after" date (`--window`, default 12 days)
   and picks the clearest pass, printing what it saw each day. Layers: `hls` (30 m, default), `hls-landsat`
   (30 m), `viirs` and `modis` (about 250 m, for very large areas: floods, smoke, sea ice).

## How to report

- Say the dates of both pictures (the picked dates can differ from the ones asked for: the script prints them).
- Say what the resolution can and cannot show. At 30 m a pixel, single buildings are not visible; burn scars,
  flooded fields, new roads, drained reservoirs and cleared forest are.
- A change between two dates does not say what caused it. Corroborate before attributing it to anyone.
- Clouds, cloud shadows, haze and different sun angles can look like change. Use the flicker view to check.

## Limits

- NASA HLS coverage is not everywhere on every date; remote islands and some ocean areas may have no data. The
  script stops when it finds almost no usable data (under 5% clear), and warns when a picked picture is under 60%
  clear; check both pictures before publishing.
- Imagery credit: NASA GIBS asks to be acknowledged; HLS Sentinel-2 imagery must say "contains modified Copernicus
  Sentinel data [year]". The script writes both.

## Will not do

- Compare imagery of a private home or a private person's property to track them.
- Present a visible change as proof of who caused it.
