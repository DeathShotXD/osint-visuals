---
name: track-map
description: Turn ship (AIS) or aircraft (ADS-B) position data into an animated, publication-ready track map that flags what investigators look for - signal gaps ("went dark"), impossible jumps (spoofed or bad positions), vessels meeting at sea (ship-to-ship transfers) and who was nearby when a transponder went silent. Use when the user has a CSV of positions, asks to map or animate a vessel or flight track, or mentions AIS gaps, dark activity, STS transfers, spoofing or flight tracking.
---

# Track map

Makes one self-contained HTML page from a CSV of position reports: an animated map with a clock, a timeline, the
gaps and anomalies labelled on the map, and buttons to export a PNG or record a WebM video (16:9, 1:1, 4:5 or a 9:16
Reel). Every export carries the data source and the map attribution.

## Before you start

1. **A CSV of positions**: one row per report with a time, a latitude and a longitude. An id column (MMSI, IMO, ICAO
   hex, callsign or name) splits it into several tracks. Column names are detected; times can be ISO 8601 or Unix
   seconds (no zone means UTC).
2. **Where the data came from.** Ask if it isn't clear. It goes on the graphic (`--source`). Positions from
   MarineTraffic, VesselFinder, Global Fishing Watch, ADS-B Exchange or OpenSky each have their own terms: say which,
   and respect them.
3. **What kind of track**: ships (`--kind ship`, default) or aircraft (`--kind aircraft`). The defaults for a "gap"
   and an "impossible" speed differ (2 h and 50 kn for ships, 5 min and 700 kn for aircraft).

## Run

```
python3 scripts/track.py positions.csv --title "..." --subtitle "..." --source "..." [--tz +04:00] [--out file.html]
python3 scripts/track.py flights.csv --kind aircraft --gap 5m --max-speed 650
```

Useful options: `--tz Asia/Dubai` or `--tz +04:00` for the clock (a zone name follows daylight-saving changes during
the track; offsets don't, and the default is UTC), `--gap 6h` (what counts as going dark), `--meet-km 0.5 --meet-min 60` (what counts as side by side),
`--theme light`. The script prints every gap, jump and meeting it found: read them before describing anything.

## How to report

- Describe what the data shows, not what it means: "no position reports for 31 hours" is a fact; "switched off its
  transponder" is an inference. AIS gaps also come from poor satellite coverage, congested areas and receiver outages.
- "Side by side" means two tracks were within the set distance at the same time. It is consistent with a transfer; it
  does not show one. Look for corroboration: draught changes, satellite images of the two hulls together, port records.
- A "position out of line" is one report far from the others. It can be spoofing, a GPS fault or a data error.
- Give the source, the time zone of the clock, and the thresholds you used (they are on the graphic).

## Limits

- Lines between reports are straight; a ship's real path between two reports is unknown, more so across a gap.
- The map style comes from OpenFreeMap (OpenStreetMap data, no key). Exports need the page to have loaded the tiles.
- Very large files (hundreds of thousands of rows) make a heavy page: filter to the vessels and dates you need first.

## Will not do

- Track private individuals, private boats or small aircraft to locate a person, or map the movements of a named
  private person.
- Present an inference (a transfer, a sanctions breach) as established by the track alone.
