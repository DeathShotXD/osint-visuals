---
name: conflict-events
description: Turn a conflict event table (UCDP GED CSV or any table with a date, coordinates and deaths) into an offline, aggregate-first graphic - where events happened, how they change by month, what kind they were, and which reports they came from. Use when the user has an event dataset, wants a conflict map or timeline for a story, or needs to show reported violence over time without naming victims.
---

# Conflict events

Makes one self-contained HTML page from a table of events: a map of the reported events, a monthly chart of events
and reported deaths, a type breakdown, a country summary and a table, with filters and PNG/SVG export. The country
outlines come from Natural Earth, cached once; after that the page needs nothing. No API key, no victim names, no
individual targeting.

## Before you start

1. **A table.** CSV or JSON. UCDP GED column names are recognised as they come (`date_start`, `latitude`,
   `longitude`, `best`, `high`, `deaths_civilians`, `type_of_violence`, `country`, `source_headline`). Other names
   work if they match the aliases in the script (`date`, `year`, `lat`, `lon`, `fatalities`, `event_type`, ...).
2. **What the numbers are.** UCDP `best` is the most likely death count for an event, `high` the upper estimate.
   Decide whether you are showing events, deaths, or both, and say which in the caption.
3. **The source and version**, for `--source`: dataset name, version, download date, licence. UCDP is CC BY 4.0.
4. **What the dataset means.** UCDP records reported events in a curated taxonomy of organised violence. Coverage
   is uneven across countries and years, and a row is a report, not a verified fact.

## Run

```
python3 scripts/conflict.py events.csv --title "..." --subtitle "..." \
    --source "UCDP GED 25.1, CC BY 4.0, downloaded 2026-06-01" --out conflict.html

python3 scripts/conflict.py events.csv --from 2024-01 --to 2025-12 --type 1 --min-deaths 10
```

Filters: `--from`/`--to` (YYYY-MM), `--country`, `--type` (UCDP code 1, 2 or 3) and `--min-deaths`. `--no-basemap`
skips the Natural Earth outlines for a fully offline build. The script prints the totals, the period and the type
breakdown before writing the page.

## How to report

- Give the dataset version, the period and the filters with the graphic. Counts without a version are not checkable.
- Report the type: state-based conflict, non-state conflict and one-sided violence are different claims about who
  fought whom.
- Say that reporting is uneven. A quiet month can mean a quiet month or a month nobody reported.
- The page aggregates by default. If you publish a single event, cite its source row; do not present a death toll
  as established beyond the report.
- Never name victims, and do not combine the table with anything that identifies individuals.

## Limits

- The map is equirectangular and auto-fits the events; country outlines are Natural Earth's de facto lines. For
  disputed areas follow your outlet's style guide.
- Very large tables are capped at 4,000 drawn points (the aggregates still use every row); filter first for detail.
- Death counts are estimates with different definitions between datasets; do not add datasets together without
  checking.
- Type codes come from the input. The script maps UCDP's 1/2/3 to labels and passes anything else through as-is.

## Will not do

- Identify individuals, victims, units or locations as targets, or produce a target list.
- Present reported events or death tolls as verified fact, or add death estimates from different datasets without
  saying so.
- Use the event data to track a person or a private property.

## Data

Your table. UCDP GED is free for academic and non-commercial use under CC BY 4.0 with attribution; check the terms
for your use case. Natural Earth is public domain. The page makes no requests; the only download is the cached
country outlines.