---
name: geolocation-board
description: Draw a geolocation evidence board from your own notes - a plan view with bearings to numbered features, a sun and shadow check against a claimed time, a confidence checklist and score, and the sources on the graphic. Use when an analyst has frame notes and wants to show the reasoning and the confidence behind a place or time claim, without naming a person or publishing a residence.
---

# Geolocation evidence board

Makes one self-contained HTML page that shows how a place and time claim is built:

1. **Plan view from the frame.** The camera, a bearing line to each numbered feature, the distance
   scale and distance rings. A feature that does not fit is drawn in red.
2. **Sun and shadow check.** The sun's azimuth and elevation at the claimed time, computed from the
   place, the date and the time zone. If you give a measured shadow direction, the board says whether
   it fits. If you give a height and a shadow length, it checks the length too.
3. **Over-determination and confidence.** A checklist, the core checks that count, and a score of 0
   to 4.

The graphic states an inference. A coordinate is a claim about a camera and a frame, not about a
person's presence, and the board names no one.

## Before you start

1. **One JSON object.** The smallest useful board has features and checks; the sun panel needs a
   place, a date and a time.

   ```json
   {
     "title": "Was this frame taken here, in the afternoon?",
     "subtitle": "Optional line under the title.",
     "place": "Public square, town, country",
     "lat": 40.0, "lon": -75.0, "date": "2026-08-10", "tz": "-04:00",
     "claimed_time": "16:30",
     "shadow": {"azimuth_deg": 70, "tolerance_deg": 8, "height": 2.0, "length": 2.4},
     "features": [
       {"id": "F1", "label": "wall and factory roof", "bearing_deg": 55, "distance_m": 420, "match": true}
     ],
     "checks": [
       {"label": "Three independent features agree", "ok": true, "core": true},
       {"label": "Second sensor or source corroborates", "ok": false, "core": true}
     ],
     "sources": "Frame, imagery, DEM and coordinate source."
   }
   ```

2. **Bearings are clockwise from true north.** `bearing_deg` runs from 0 to 359.9. `distance_m` is
   metres; only the ratio between features matters for the plan view, so an estimate is fine.
3. **Checks.** Mark up to four as `"core": true`. The score is the number of core checks met, out of
   the core checks listed (capped at 4). Extra checks are shown but do not change the score.
4. **Sources.** Name where the frame, the imagery, the terrain model and the coordinate came from.
   They are drawn on the graphic and in the export.

## Run

```
python3 scripts/board.py board.json --out board.html

python3 scripts/board.py board.json --theme light --title "..." --source "..." --out board.html
```

`--title` and `--source` override the same fields in the input. `--theme dark|light` sets the page
theme. The page has PNG and SVG export and a Details table. It makes no network requests.

The demo is `assets/demo.json`, and the page it makes is `examples/geolocation/demo.html`:

```
python3 skills/geolocation-board/scripts/board.py skills/geolocation-board/assets/demo.json \
    --out examples/geolocation/demo.html
```

The demo is an invented scene with a synthetic coordinate. It is not a geolocation of a real place.

## The sun check

- The maths is the NOAA solar position equations, the same code as `shadow-diagram`. It ignores
  atmospheric refraction, so a result within about 3 degrees of the horizon is weak.
- `tz` takes an offset like `-04:00` or a zone name like `America/New_York`. With a name, the offset
  is resolved for that date; on Windows a name needs `pip install tzdata`.
- The expected shadow points 180 degrees from the sun. A measured shadow within `tolerance_deg`
  (default 5) of that direction fits.
- A height and a length give a second, independent check: the expected shadow length is
  `height / tan(elevation)`, compared within `length_tolerance_pct` (default 15).
- If the sun is below the horizon at the claimed time, the board says so and compares nothing.

## How to report

- Say that the board is an inference and give the score. "Three of four core checks met" is a
  finding with a stated gap; "geolocated" with no score hides the gap.
- A match on resemblance is not a match on geometry. The check "three independent features agree"
  means separately placed objects, not three windows of one building.
- A time claim is a window, not a clock reading. The sun bounds the hour; dated imagery bounds the
  day; weather and vegetation narrow the season.
- If the score is low, publish it as a lead, not as a finding. The board's own label says so.

## Limits

- The plan view is schematic. Distances and bearings are as you entered them; the board does not
  measure the frame for you.
- The sun check needs an accurate place, date and time zone. A coordinate off by a kilometre, or a
  time zone guessed wrong, changes the answer.
- Feature distance is not checked; only the bearing and the relative position are drawn. A wrong
  distance changes the plan view but not the sun check.
- The score is a checklist, not a probability. Two analysts can weigh the same evidence differently;
  the point is that the checks are named and visible.

## Will not do

- Name a person, a resident, an account or a device, or publish a home, a school or a routine.
- Present a lead as a finding, or a resemblance as a match.
- Produce a target list, a pattern-of-life timeline, or access planning for a person.
- Add new location detail about a named individual. Use a public place or a synthetic scene.

## Data

Your notes and your sources; their terms are yours to check. No network access. Method sources,
credited on the demo: Benjamin Strick's Haiti geolocation explainer (May 2024), Bellingcat's guide to
3D imagery (2019) and its guide to sun and shadows (2020). Natural Earth is not used here; the plan
view is schematic.