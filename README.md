# osint-visuals

**Evidence graphics for open-source investigations, made by your AI agent.** Ask in plain words and get a
publication-ready visual that carries its own sources: an animated ship track that flags where it went dark, a shadow
diagram that tests a claimed time, a 3D miniature of the scene with the camera's line of sight, or a newsroom
locator map.

Four skills in the open [Agent Skills](https://agentskills.io) format, for Claude Code and other agents. Each one
writes **a single HTML file** with export built in: PNG for all four, WebM video for track-map and scene-diorama, SVG
for shadow-diagram and locator-map. Python 3.9+, standard library only (on Windows, `--tz` zone names need
`pip install tzdata`; offsets like +03:00 work everywhere), no API keys.

| | |
|---|---|
| ![An animated tanker track with a 31-hour signal gap and a meeting at sea](docs/gallery/track-map.png) | ![A 3D miniature of a city square with a camera's field of view and the event marked](docs/gallery/scene-diorama.png) |
| **track-map**: AIS or ADS-B positions become an animated map that labels signal gaps, who was nearby when a ship went dark, ships side by side at sea and positions out of line. | **scene-diorama**: a real place from OpenStreetMap as a miniature, with where the camera stood, what it could see and how far away the event was. |
| ![A sun-path compass showing a photo fits 09:08 to 09:24, not the claimed 16:30](docs/gallery/shadow-diagram.png) | ![A locator map of Beira, Mozambique, with an inset globe](docs/gallery/locator-map.png) |
| **shadow-diagram**: when could this shadow have been cast? The windows that fit, and a claimed time tested against them. | **locator-map**: a clean "where is this" map from a place name, in web, social and print sizes. |

![The approximate view from the camera position in the diorama](docs/gallery/scene-diorama-camera-view.png)

*The diorama's camera's view: the scene from where the footage was filmed, to compare with the frame.*

All the examples use invented scenarios (fictional ships, claims and events) on real maps.

## Why

Investigations are often published with a screenshot of a map and a paragraph of explanation. Readers trust what they
can see. These skills make the graphic that shows the method, and they put the evidence trail on the graphic itself:
where the data came from, the thresholds used, and what a finding does and does not show. They also keep the agent
from overclaiming: a gap is "no reports for 31 hours", not "switched off its transponder".

## Install

**Claude Code, for yourself:**

```
git clone https://github.com/Ghongha007/osint-visuals.git
mkdir -p ~/.claude/skills
cp -r osint-visuals/skills/* ~/.claude/skills/
```

**Claude Code, for one project:** copy the folders into `.claude/skills/` in that project.

**Other agents:** copy the folders to wherever your agent reads skills from. Each skill is self-contained.

Then ask, for example:

- "Map this AIS export and show where the tanker went dark" (attach the CSV)
- "Make a shadow diagram: Nairobi, 10 August, shadow pointing 250 degrees, the post claims 4:30 pm"
- "Build a diorama of Prešeren Square in Ljubljana with the camera on the first floor at 46.05098, 14.50712 looking at
  the crowd at 46.05143, 14.50606"
- "Locator map for Beira, Mozambique, 4:5 for Instagram"

## The scripts work without an agent

```
python3 skills/track-map/scripts/track.py examples/track/demo-tankers.csv --title "A tanker goes dark" --tz +04:00
python3 skills/shadow-diagram/scripts/shadow.py --lat -1.2864 --lon 36.8172 --date 2026-08-10 --tz +03:00 \
    --shadow-azimuth 250 --tolerance 6 --height 1.75 --shadow-length 2.3 --claimed 16:30
python3 skills/scene-diorama/scripts/diorama.py --lat 46.0514 --lon 14.5061 --radius 110 \
    --camera 46.05098,14.50712 --camera-height 9 --target 46.05143,14.50606
python3 skills/locator-map/scripts/locator.py --place "Beira, Mozambique" --title "Cyclone makes landfall near Beira"
```

Each prints what it found (gaps, windows, matches) and writes the page. Open it in a browser, pick a frame (16:9, 1:1,
4:5 or 9:16 Reel; locator-map also has 3:2 web and print) and export. The track, diorama and locator pages load pinned
libraries (MapLibre, three.js, d3) from unpkg, and the track map loads its tiles from OpenFreeMap, so they need a
connection when opened. The shadow page is fully self-contained.

## Data, and the rules that come with it

| Used by | Source | Licence and rules |
|---|---|---|
| track-map | your CSV; basemap from [OpenFreeMap](https://openfreemap.org) | Map: OpenFreeMap © OpenMapTiles, data © OpenStreetMap contributors (credit is drawn on every export). Your data's own terms apply. |
| scene-diorama | [Overpass API](https://overpass-api.de) (OpenStreetMap) | ODbL: credit "© OpenStreetMap contributors". One request per place (up to two retries if the server is busy), cached; Overpass is shared, so no bulk loops. |
| locator-map | [Natural Earth](https://www.naturalearthdata.com), [Nominatim](https://nominatim.org) | Natural Earth is public domain. Nominatim: max 1 request per second, identifying User-Agent, results cached ([policy](https://operations.osmfoundation.org/policies/nominatim/)). |
| shadow-diagram | none | Sun positions computed locally (NOAA equations). |

The scripts' downloads are cached in `~/.cache/osint-visuals` and never expire; delete a file there to fetch fresh
OpenStreetMap data. The scripts send an identifying User-Agent and only what each lookup needs (the place name, or the
area's coordinates) to OpenStreetMap's servers. Opening a page fetches libraries and tiles from third-party servers,
which see your IP address and the area you are viewing: keep that in mind for sensitive investigations.

## What these skills will not do

- Track, map or model a private person: their home, their movements, the window they filmed from.
- Present an inference as a finding: a meeting at sea is not a transfer, a matching shadow is not proof of a time, and
  the camera's view is an approximation, not a photograph.

These limits are written into the skills. If you fork the pack, please keep them.

## Limits

- Lines between track reports are straight; the real path, above all across a gap, is unknown.
- The diorama's heights come from OpenStreetMap tags or are estimated from the building type; roofs and terrain are
  flat. Check it against satellite imagery before you publish.
- The shadow maths ignores refraction, so it is unreliable within about 3 degrees of the horizon.
- Locator borders follow Natural Earth's de facto lines. For disputed areas, follow your outlet's style guide.

## Tests

```
python3 -m unittest discover -s tests
```

The tests run offline: track analysis on the regenerated demo data, the sun position against a known value (London's
noon sun at the December solstice), the shadow windows and claim check, page writing for track and shadow, and the
diorama and locator geometry helpers.

## Related

- [osint-skills](https://github.com/Ghongha007/osint-skills): verification skills (geolocate, chronolocate, archive evidence, attribute claims)
- [groundline](https://github.com/Ghongha007/groundline): check every sentence of a draft against its source documents
- [verify-mcp](https://github.com/Ghongha007/verify-mcp): an MCP server with keyless, read-only verification lookups

## Licence

MIT. Made by [OSINT JOURNO](https://github.com/OSINT-JOURNO).
