---
name: html-network-visualisation
description: Make an explorable, source-linked relationship network from JSON, with search, evidence filters, one/two-step neighbourhoods, graph physics and a connection table. Use when the user asks to visualise relationships between entities or inspect the records behind a network. Produces an offline HTML snapshot and native graph JSON.
---

# HTML network visualisation

Makes one HTML page with the graph, its supporting records and its library embedded. Open it offline, inspect a
node or connection, change the layout and filters, then export a PNG or save the current view as JSON. The native
graph JSON accompanies the page; no server, API key or Python package is needed.

## Before you start

1. **A JSON network** in [the input schema](references/schema-and-build.md). Start from `assets/demo.json`, which
   contains fictional entities and quotations. Keep actual data in the user's working directory, outside the skill.
2. **What each connection means**, its direction, dates and scope. Use stable IDs: equal names do not establish
   identity, and shared attributes do not establish a relationship. The builder draws only supplied connections.
3. **Supporting records and their sources.** Every edge needs a record; an isolated node needs its own. Include
   source labels, locators, quotations and uncertainty. State handling and scope prominently, and check reuse rights.

Entity names, IDs and source text can use any Unicode script. The interface stays in English. Search normalises
Unicode and ignores case and combining marks; it does not transliterate between scripts or merge matching names.
Arabic/Hebrew source text uses automatic direction. Font coverage depends on the browser and installed fonts.

## Run

From the skill directory:

```
python3 scripts/network.py --input network.json --output network.html
```

The script validates the graph and writes `network.html` and `network.graph.json`. It checks the bundled vis-network
library against its SHA-384 pin before embedding it. It makes no downloads. Existing outputs are protected: choose a
new filename for another edition. Relative source links resolve from the input directory, are checked for existing
files and are rebased for the output. Deliver those companion files too.

## Explore and export

- Search a label, then select a one- or two-step neighbourhood. IDs keep same-name entities separate. Use the
  connection table for keyboard access to sources, including when the canvas is crowded.
- Relationship filters hide layers; **All connections** also shows supported isolates. Excluding review candidates
  removes their support, and removes a connection if it has no active support left.
- Adjust repulsion, spring length and damping; pause/reheat, fit, drag, pin or hide labels. Physics positions do not
  measure geography, hierarchy or influence. Node size counts visible incident edges; line weight counts records.
- **Export PNG** captures the graph with its title, handling, scope, coverage and source labels. The HTML and native
  graph JSON retain full record detail. **Download view** and **Copy view** save filters, physics settings,
  positions and pins. A selectable fallback appears if clipboard access fails. View JSON is not the full dataset and
  cannot currently be re-imported. Printing uses the filtered connection table rather than the canvas.

## How to report

- `recorded` means source support was included, not that a claim or identity is verified. `review` marks unresolved
  support. Mixed support stays dashed until unresolved records are filtered out. Repeated records need not be
  independent corroboration.
- Check direction, relationship definitions, dates, quotations and source targets against the input. Explain excluded
  layers and transformations in `scope_note`. Keep inference and uncertainty visible in labels and captions.
- Inspect the actual saved page at desktop and phone widths, source inspection, print and exports. Check wording and
  source attribution before delivery. Saving a graphic does not itself authorise publication.

## Limits

- Dense graphs need filtering; simultaneous readability of every label is not guaranteed. This pack's browser checks
  use a small synthetic fixture, not a large-network performance benchmark.
- No identity resolution, relationship extraction, community detection, centrality analysis or database service is
  included. See [optional adaptations](references/adaptations.md) when the user requests those features.
- The HTML and native JSON contain the whole supplied dataset, including layers hidden by default. Filters do not
  redact data. Remove sensitive records before building a distributable snapshot.
- Safe links and inert source text reduce script injection risk; the builder cannot verify source truth or remote
  availability. Opening a source link can contact its host; exploring the graph requires no network access.

## Will not do

- Map a private person's contacts or associations to target, track or expose them.
- Treat proximity, a matching label or a graph score as proof of identity, affiliation or influence.
