# Input schema and build

The input is a UTF-8 JSON object. See [the synthetic fixture](../assets/demo.json) for a complete working example.

| Field | Meaning |
|---|---|
| `title`, `handling`, `scope_note` | Required text displayed on the page. Define the graph's scope and limits. |
| `subtitle`, `identity_note`, `footer_note` | Optional context and qualifications. |
| `primary_type` | Optional node type to emphasise; defaults to the first type. |
| `links` | Optional header links: `{label, href}`. |
| `types` | Nonempty object keyed by type ID. Values have `label` and optional `shape`: dot, square, triangle, diamond, hexagon, triangleDown, ellipse, box or star. |
| `relations` | Object keyed by relation ID. Values have `label`, optional boolean `default` (true if omitted) and `description`. |
| `nodes` | List of `{id, label, kind, records: [record_id], details?}`. `kind` names a type. |
| `edges` | List of `{id, from, to, relation, records: [record_id], directed?: true}`. Use false for undirected links. |
| `records` | Object keyed by record ID. Values have `label`, `status` (`recorded` or `review`), optional `details`, `fields` object, `uncertainty` list of text and `sources` list. |
| Record sources | Objects with optional `label`, `href`, `locator` and `quote` text. A locator can identify a page, section, row or timestamp. |

Use string IDs, including for large numeric identifiers. Node and edge IDs must be unique within their respective
lists. Record references and edge endpoints must exist. Every edge needs support. Nodes can inherit support from
incident edges, but isolates need their own. Duplicate support IDs count once. The names `__proto__`, `constructor`
and `prototype` are reserved identifiers. Non-finite numbers are rejected.

Two entities may share a label. Self-links are allowed when meaningful. Parallel edge objects are preserved; combine
only equivalent direction/relation pairs in the adapter and retain their support. The graph export preserves source
records and adds `mentions`, `own_mentions`, counts and renderer metadata for the interface. No identities or edges
are inferred. Dates belong in record fields or details; no time-range filter is implemented.

Labels, IDs and record text retain their original Unicode spelling in HTML and JSON. The English interface accepts
Arabic, Hebrew, CJK, Cyrillic, Greek, Devanagari and mixed-script names. Search uses compatibility normalisation,
lowercase and removal of combining marks (also matching German sharp s to `ss`); this affects search only. It does
not equate transliterations or establish identity. The inspector automatically directs right-to-left text; canvas
labels and PNG use system fonts, so install suitable fonts if a script appears as missing-glyph boxes. Long canvas
labels shorten at grapheme boundaries on browsers with `Intl.Segmenter`; the inspector retains the full label.
The fallback uses Unicode code points. See [the multilingual fixture](../assets/multilingual.json).

## Commands

From the repository root:

```
python3 skills/html-network-visualisation/scripts/network.py --input skills/html-network-visualisation/assets/demo.json --output examples/network/new-demo.html
python3 -m unittest discover -s tests
```

Only Python 3.9+ and the standard library are needed to build. The skill is portable: its `assets/vendor` directory
contains vis-network 9.1.6, including its standalone dependencies and upstream MIT/Apache licence notices. The
`assets/library.json` pin is checked even when `--vis-js path/to/library.js` selects a different local file. See
[third-party notices](../assets/vendor/NOTICE.md). Updating the version requires updating the pin, licences and browser
checks. The builder never fetches a missing library.

The optional browser review needs Playwright and Chromium:

```
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tools/review_network.py --html examples/network/demo.html --output review/network
```

The helper uses the bundled synthetic graph and blocks networking. It exercises source inspection, filters, search,
neighbourhoods, layout, dragging/pinning, view export, clipboard fallback, PNG, print and narrow screens. Inspect its
screenshots as well as the JSON results. It is a development tool, not a runtime dependency.

## Source links and output safety

Links may be HTTP(S) without credentials, fragments or forward-slash relative file paths. Executable schemes,
protocol-relative URLs, controls, backslashes and absolute workstation paths are rejected. Relative file links are
resolved from the input JSON directory, checked and rebased relative to the output HTML; their fragments and query
strings are preserved. Local fragments refer to the generated page. Remote targets are not fetched or verified.

Source text uses DOM text nodes. Embedded JSON escapes script delimiters and Unicode line separators. Template
replacement runs once so token-like source text stays literal. The library is embedded only after integrity validation.
Keep the HTML and graph JSON together; current-view JSON contains layout and filter state rather than source records.
