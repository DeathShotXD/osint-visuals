---
name: locator-map
description: Make a clean newsroom locator map from a place name or coordinates - the country highlighted, neighbours and nearby cities labelled, a scale bar and an inset globe - in web, social (4:5, 1:1, 9:16) and print sizes, light or dark. Use when the user needs a "where is this" map for a story, a locator graphic, or a quick map of a place mentioned in a report.
---

# Locator map

Makes one self-contained HTML page (an SVG, exported as PNG or SVG): the place marked and labelled, its country
highlighted, neighbouring countries and the main nearby cities named without overlaps, a scale bar, and an inset
globe showing where the map sits in the world. Sizes: 3:2 web (1200), 4:5, 1:1, 9:16, 16:9 and print (2400).

## Before you start

1. **A place name or coordinates.** Names are looked up with OpenStreetMap's Nominatim (one request, cached). Check
   the result: the script prints what it matched. For anything ambiguous, give `--lat` and `--lon`.
2. **A headline** for the map (`--title`), and optionally a subtitle and a source for the story's facts.

## Run

```
python3 scripts/locator.py --place "Beira, Mozambique" --title "..." [--subtitle "..."] [--half-width 300] [--theme dark]
python3 scripts/locator.py --lat 19.83 --lon -155.08 --label "Hilo" --title "..."
```

`--half-width` (km from the marker to the side of the map) overrides the automatic extent, which fits the country.
The zoom slider on the page also adjusts it.

## Data and its rules

- Country shapes and cities: Natural Earth (public domain), downloaded once and cached in `~/.cache/osint-visuals`.
- Place lookup: Nominatim, at most one request per second, with an identifying User-Agent. Do not batch-geocode long
  lists through it; use your own geocoder for that.
- Borders follow Natural Earth's de facto boundaries. For disputed territory, check your outlet's style guide and say
  how the map draws it.

## Will not do

- Mark a private person's home or exact address.
