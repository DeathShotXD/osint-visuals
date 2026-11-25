---
name: attack-coverage
description: Draw an ATT&CK coverage matrix from your own technique counts - tactic columns, technique cells sized by count, sources and notes on the graphic, exportable as PNG or SVG. Use when the user has a list of techniques with counts or scores from incidents, detections, tabletop exercises or reports and wants a coverage or frequency matrix.
---

# ATT&CK coverage

Makes one self-contained HTML page: a matrix with one column per tactic, one cell per technique, a count, a colour
scale, a details panel, a table view, and PNG/SVG export. The input is yours. The skill deliberately does not bundle
the ATT&CK matrix, so the graphic answers your question instead of reproducing a poster.

## Before you start

1. **Rows with a tactic and a technique**, as CSV or JSON:

   ```
   tactic,technique_id,technique,count,source,note
   initial-access,T1566,Phishing,4,Incident review Q1,Two attempts and two successes
   ```

   A `tactic` column and a `technique_id` or `technique` column are required. `count`, `source` and `note` are
   optional. Duplicate tactic+technique rows are summed and their sources kept.
2. **What the count means.** Incidents, detections, reports, sightings: decide before you build, and say it in the
   caption. The graphic prints "count", not "risk".
3. **Tactic names.** Canonical ATT&CK tactic names work (`initial-access`, `command-and-control`). Unknown names are
   kept and shown last, so a custom taxonomy still renders.

## Run

```
python3 scripts/attack.py coverage.csv --title "..." --subtitle "..." --source "..." --out matrix.html
python3 scripts/attack.py coverage.json --theme light
```

The JSON form is a list of row objects, or an object with `techniques`, `rows` or `data`.

## How to report

- Say what a count is and where it came from. A frequency matrix is not a coverage assessment unless you define
  what "covered" means.
- Missing techniques are as interesting as present ones, but the graphic only shows what you supplied. Say what you
  left out.
- A technique mapping is an interpretation. Two analysts can map the same behaviour differently; note who mapped it.
- Do not describe a high count as sophistication or capability.

## Limits

- No ATT&CK data is bundled and nothing is fetched. You supply IDs, names and counts; the skill does not validate
  that a technique ID exists or that the name matches.
- Colour and count are the only encoding; there is no severity scale, because the input has no severity field.
- Narrow columns truncate tactic names; with all fourteen tactics, export at full width or split by tactic.
- Layout is fixed at 1600 px wide.

## Will not do

- Rank actors, sectors or victims for targeting, or produce a target-selection matrix.
- Present counts as proof of capability, intent or attribution.
- Bundle ATT&CK content in a way that ignores MITRE's terms; attribution is printed on every export.

## Data

Technique IDs and names belong to MITRE ATT&CK, which is free to use with attribution ("© MITRE ATT&CK"). Counts,
mappings, sources and notes are your input; their terms are yours to check.