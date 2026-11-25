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

It makes one request to the public Overpass API and caches it. Do not loop it over many places: Overpass is a shared
service with daily limits.

## How to report

- The camera's view is an approximation from map outlines and estimated heights. Use it to compare the layout of
  buildings and the angle with the footage, and say so; it is not a photograph or a rendering of the real facades.
- Check the model against satellite imagery before publishing: OpenStreetMap can be missing buildings or have old ones.
- Credit "© OpenStreetMap contributors" (the page does this on every export).

## Limits

- Heights come from OSM `height` or `building:levels` tags when present; otherwise from the building type (a guess).
- Roofs are flat; terrain is flat. Hilly places will not line up in the camera's view.
- Building interiors, temporary structures, vehicles and people are not in the data.

## Will not do

- Model a private home or identify which flat or window a private person filmed from.
- Present the camera's view as what the camera actually recorded.
