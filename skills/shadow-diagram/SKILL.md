---
name: shadow-diagram
description: Make a publication-ready chronolocation graphic - a sun-path compass, the day's sun height and the windows of local time that fit a measured shadow - and test a claimed time against it. Use when the user wants to show readers when a photo or video was taken from its shadows, check or debunk a claimed time, or asks for a shadow, sun-position or chronolocation diagram.
---

# Shadow diagram

Makes one self-contained HTML page (an SVG you can export as PNG or SVG in 4:5, 1:1, 16:9 or 9:16): where the sun
was through the day, the shadow measured in the image, the times that fit (in green) and, if given, a claimed time
(in red) with how far it is from the evidence. The sun positions are computed by the script and embedded; nothing is
fetched.

## Before you start

You need the same things as for any chronolocation. If one is missing, say which and stop.

1. **The place**, as latitude and longitude (geolocate first if it isn't known).
2. **The date** and the **time zone** (an offset like `+03:00` or a zone name like `Africa/Nairobi`).
3. **A shadow you measured** from a vertical object on roughly level ground:
   - its compass direction (match the image to satellite imagery and read the bearing; give a range), and/or
   - the object's height and the shadow's length (same unit), which fixes the sun's elevation.

Both together give a narrow window; direction alone near the equator can fit for hours.

## Run

```
python3 scripts/shadow.py --lat -1.2864 --lon 36.8172 --date 2026-08-10 --tz +03:00 \
    --shadow-azimuth 250 --tolerance 6 --height 1.75 --shadow-length 2.3 \
    --claimed 16:30 --place "Nairobi, Kenya" --title "..." --source "where the image came from"
```

Set `--tolerance` to half the width of your measured range. The script prints the windows and the claim check.

## How to report

- Give a window, never a single minute, and say what you measured and the tolerance you used.
- A fit is *consistent with* a time. A claimed time that does not fit is strong evidence against the claim, as long
  as the place, the date and the measurement are right: say those assumptions.
- Shadow length alone matches twice a day; direction tells morning from afternoon.

## Limits

- NOAA solar position equations without a refraction correction (the same maths as
  `osint-skills/chronolocate/sun.py`); unreliable within about 3 degrees of the horizon.
- Assumes a vertical object on level ground; slopes, leaning poles and lens distortion near the frame edge all shift
  the reading.

## Will not do

- Use shadows to narrow down where a private person lives or is.
- Present a fit as proof of when something happened.
