---
name: incident-map
description: Draw an aggregate incident map from your own table - countries shaded by incident count, sectors and months broken out, sources on the graphic, PNG/SVG export. Use when the user has a CSV of incidents with country, sector and date and wants a map, a sector breakdown or a trend, without naming victims or organisations.
---

# Incident map

Makes one self-contained HTML page from a table of incidents: a choropleth of countries, a sector breakdown, a
monthly chart, a country summary and a table, with sector filters and PNG/SVG export. Country outlines come from
Natural Earth, cached once and simplified to the view. No API key, no network at open time.

The graphic is aggregate by design. The script reads country, sector, date and count, and ignores any column that
looks like an organisation, victim, host or leak-site name. The page never names one.

## Before you start

1. **A table**, CSV or JSON, one row per incident or per already-counted country/sector/month:

   ```
   date,country,sector,count,source
   2026-02-11,Germany,Manufacturing,2,Incident review Q1
   2026-03-02,Japan,Transport,1,Incident review Q1
   ```

   `date` (or `year`), `country` are required; `sector`, `count` (default 1) and `source` are optional. Country
   names, ISO 3166 alpha-2 and alpha-3 codes all match the Natural Earth names.
2. **What a count means.** Incidents, victims, reports, sightings: decide, and say it. The graphic prints
   "incidents", not "severity".
3. **No victim columns.** Do not pass organisation, domain, host or leak-site columns. If they are present the
   script ignores them and tells you so; remove them from the file anyway.
4. **The dataset and its window**, for `--source`. Counts without a collection window are not comparable.

## Run

```
python3 scripts/incident.py incidents.csv --title "..." --subtitle "..." \
    --source "Dataset, version, downloaded 2026-06-01" --out incidents.html

python3 scripts/incident.py incidents.csv --from 2025-01 --to 2025-12 --sector Energy --min-count 2
```

Filters: `--from`/`--to` (YYYY-MM), `--sector` (repeatable), `--min-count`. `--no-basemap` skips the outlines for a
fully offline build. The script prints the row count, the totals, the top countries and any country spellings that
had no outline.

## How to report

- Aggregate. "Germany, 6 incidents in Q1" is publishable when the dataset and window are stated; a named victim is
  not this skill's business.
- Say what the count is and which dataset produced it. Two datasets counting "incidents" differently cannot be added.
- Country spellings that do not match the outline set still appear in the tables, not on the map. Mention them if the
  difference changes the picture.
- A dark country is not a safe country; it may be a country with no reporting. The page says so in its note.

## Limits

- Choropleth only: no city-level points, no time animation. A country is the unit.
- Natural Earth 110m outlines are coarse; small states may be missing. Borders follow Natural Earth's de facto lines.
- Sector names are free text. Long lists make a long bar chart; the page shows the top nine and the table has all.
- Counts are shown as given. The script does not deduplicate rows; if your table has duplicates, fix it first.

## Will not do

- Name victims, organisations, domains or leak sites, or deanonymise any of them.
- Turn a count into a severity rating or a target list, or rank countries for action.
- Present an aggregate as a complete record of what happened.

## Data

Your table; its terms are yours to check. Natural Earth is public domain and is credited on every export. The page
makes no requests.