---
name: stix-timeline
description: Turn a STIX 2.1 bundle into an offline cyber incident timeline - threat actors, campaigns, infrastructure, malware, techniques, vulnerabilities, indicators, observations and reports placed by their recorded dates, with confidence and sources kept visible. Use when the user has a STIX or MISP/OpenCTI export, asks for a cyber incident timeline, wants to show how a campaign unfolded, or needs an attributable graphic for a cyber story.
---

# STIX timeline

Makes one self-contained HTML page from a STIX 2.1 bundle: lanes by object type, bars for objects with a start and
an end, dots for single dates, a details panel, lane filters, a confidence filter, a table view, and PNG/SVG export.
No network, no library, no key. Confidence and source references stay on the graphic and in the details panel.

## Before you start

1. **A STIX 2.1 bundle**, as JSON. Exports from MISP, OpenCTI or a hand-written analyst file all work if they keep
   the standard fields. The script reads `objects` from a bundle, or a plain list.
2. **Which dates mean what.** The timeline places an object by `first_seen`, then `valid_from`, then `published`,
   then `created`, in that order. A bar runs to `last_seen` or `valid_until` when present. Say in the caption which
   date the reader is looking at: `created` is when the record was written, not when the event happened.
3. **Where the bundle came from**, for `--source`, and whether it can be published. STIX bundles often contain
   victim names, credentials or unpatched-vulnerability detail. Remove what you do not need before building a page
   you intend to share.
4. **What confidence means here.** A STIX `confidence` is the producer's estimate, not a probability. Show it, do
   not treat it as a score to rank actors by.

## Run

```
python3 scripts/stix.py bundle.json --title "..." --subtitle "..." --source "MISP export, 2026-06-01" \
    --min-confidence 0 --out timeline.html
```

Useful options: `--min-confidence 60` hides weaker objects (and counts them in the terminal), `--theme light` for a
newsroom style. The script prints how many objects landed on each lane and what it skipped.

## How to report

- Distinguish the record from the event: "the bundle records the campaign from February to May" is accurate;
  "the campaign started in February" may not be.
- An `indicator` with `valid_from` and `valid_until` is an indicator lifetime, not proof that anything was active.
- A `relationship` is an assertion by the bundle's producer. Quote the relationship type; do not flatten `uses`,
  `targets` and `indicates` into "linked to".
- Attribution is an assessment. If the bundle names an actor, say who assessed it and link the source record.
- Keep victim organisations and individuals out unless they consented or are already public and relevant.

## Limits

- No STIX validation, no identity resolution, no merging of objects with different IDs. Same name does not mean
  same thing.
- Lanes are fixed. A very large bundle (thousands of objects) makes an unreadable page; filter to the campaign or
  the time window first.
- Layout is SVG at a fixed 1600 px width; export at that size. Overlapping labels are staggered, not solved.
- Only `external_references` with http(s) URLs become clickable. Opening one contacts that host.

## Will not do

- Publish credentials, victim PII, or unpatched-vulnerability detail that the bundle happens to contain.
- Rank actors, victims or techniques for targeting, or turn a timeline into a target list.
- Present a producer's attribution or confidence as established fact.

## Data

Your bundle. STIX 2.1 is an OASIS standard; object names and fields are public. If you use a MISP or OpenCTI export,
follow that platform's handling rules and your outlet's policy. The page makes no requests; source links open only
when a reader clicks them.