---
name: scene-diorama
description: Build a 3D miniature of a real place from OpenStreetMap and put the geolocation evidence on it - where the camera stood, its field of view, the line of sight and distance to the event - with an isometric view, a top view and an approximate camera's-eye view. Use when the user wants to show readers how a photo or video was geolocated, where it was filmed from, what a camera could see, or asks for a 3D scene, diorama or "how we found it" graphic.
---

# Scene diorama

Makes one self-contained HTML page: a picture-book 3D model of a square of the real world (60 to 250 m from the
centre to each side) with buildings, streets, water, parks and trees from OpenStreetMap, plus the evidence: a camera
marker at its height, a see-through field-of-view pyramid, a dashed line of sight with the distance, the event pin,
and labels for the largest named buildings. Views: Diorama (rotatable), Top, Camera's view. Exports: PNG, and a WebM
of the model turning.

## Before you start

1. **The place is already geolocated.** This skill illustrates a finding; it does not find places. Geolocate first.
2. **Coordinates** for the centre, and if known: the camera position (`--camera LAT,LON`), its height above ground
   (a window, a roof), its direction (`--camera-bearing`, or leave it out to face the target) and its field of view
   (`--fov`, about 65-75 for a phone's main camera), and the event (`--target LAT,LON`).
3. **Where the image came from**, for `--source`.

## Run

```
python3 scripts/diorama.py --lat 46.0514 --lon 14.5061 --radius 110 \
    --camera 46.05098,14.50712 --camera-height 9 --fov 65 \
    --target 46.05143,14.50606 --target-label "Crowd gathers here" \
    --title "..." --place "Prešeren Square, Ljubljana, Slovenia" --source "..."
```

Add `--los` to check whether the camera could actually see the target. It reads terrain from Mapzen Terrarium tiles
(keyless, cached) and uses the building heights already in the model, then draws the elevation profile with the
verdict:

```
python3 scripts/diorama.py --lat 46.0514 --lon 14.5061 --radius 200 \
    --camera 46.05070,14.50600 --camera-height 1.7 \
    --target 46.05130,14.50700 --target-height 1.7 --los \
    --title "Could this camera see the square?" --place "Ljubljana, Slovenia"
```

The building the camera stands in is left out of the check, on the assumption that the camera is on its facade
looking out. `--los-step` (default 2 m), `--los-clearance` (0.3 m) and `--los-z` (terrain zoom, 13 to 15) tune it.

It makes one request to the public Overpass API and caches it. Do not loop it over many places: Overpass is a shared
service with daily limits.

## How to report

- The camera's view is an approximation from map outlines and estimated heights. Use it to compare the layout of
  buildings and the angle with the footage, and say so; it is not a photograph or a rendering of the real facades.
- With `--los`, say which obstacle blocks the line and at what distance. A blocked line is strong evidence against
  a claimed camera position; a clear line is consistent with it, not proof of it.
- Check the model against satellite imagery before publishing: OpenStreetMap can be missing buildings or have old ones.
- Credit "© OpenStreetMap contributors" (the page does this on every export).

## Limits

- Heights come from OSM `height` or `building:levels` tags when present; otherwise from the building type (a guess).
- Roofs are flat; terrain is flat. Hilly places will not line up in the camera's view.
- Building interiors, temporary structures, vehicles and people are not in the data.
- Line of sight uses Mapzen Terrarium terrain (SRTM and others) and OSM heights. Flat roofs, no vegetation, no
  glass, no night or weather. It is a model of an open-air sight line, not a survey.

## Will not do

- Model a private home or identify which flat or window a private person filmed from.
- Present the camera's view as what the camera actually recorded.
- Use line of sight to work out which window or flat a private person filmed from.
