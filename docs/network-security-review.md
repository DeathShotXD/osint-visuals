# Network skill: verification and security review

Checked on 25 November 2026 for the HTML network visualisation contribution. The scope is the new skill, its two
fictional datasets, generated examples and review tools. This is a focused review, not a security audit of the other
skills or a guarantee against all vulnerabilities.

| Check | Result |
|---|---|
| Repository tests | All 28 tests passed with `python -m unittest discover -s tests`. Existing scripts emit file-handle ResourceWarnings; no test failures. |
| Skill metadata | Skill-creator validation passed. |
| Python compatibility | New Python files parse with the Python 3.9 grammar. Runtime tests used Python 3.12 on Windows. |
| Offline browser | Chromium opened the actual demo from a file with networking disabled; zero external requests, browser errors or warnings. |
| Interaction | Search, relationship/review filters, isolates, one/two-step neighbourhoods, source excerpts, graph/table switching, keyboard table access, physics sliders, pause/reheat, fit, drag/pin and label toggle passed. |
| Exports | Changed filters, physics, positions and pins survived download/copy fallback. PNG downloaded successfully; desktop, phone, print and exported images were visually inspected. |
| Unicode | Arabic, Hebrew, Chinese, Japanese, Korean, Cyrillic, Greek, Devanagari, accented Latin and mixed-script/emoji labels passed search, source inspection, table, print and PNG checks. JSON preserves the exact names and excerpts. Right-to-left inspector direction was checked. |
| Injection | Script-closing strings and HTML event payloads remained literal in titles, labels and quotations in the browser. No injected element or script execution occurred. |
| Input and links | Tests reject missing endpoints/support, duplicate IDs, malformed structures, executable schemes, URL credentials, absolute workstation paths and control characters. Relative source files are checked and rebased. |
| Library integrity | A modified library is rejected. The bundled vis-network 9.1.6 file matches the SHA-384 pin; Git preserves its exact bytes across checkouts. MIT and Apache licence texts accompany it. |
| Static analysis | Bandit 1.9.4 found no issues in the new builder. |
| Secret scan | Gitleaks 8.30.1 scanned the staged contribution. Three generic-key matches were the same public library method name, `_getDistanceToBezierEdge2`, in the vendor file and its two embedded copies. These were verified against the pinned upstream bytes; no credential was found. |
| Dependency advisory lookup | OSV returned no advisories for npm `vis-network` 9.1.6 on the review date. The [maintainer advisory page](https://github.com/visjs/vis-network/security/advisories) also listed none. This does not establish that every bundled transitive dependency is vulnerability-free. |
| Public-data review | New files were checked for private workspace names, workstation paths and inherited project dependencies. The examples contain only fabricated entities, records and quotations. |

The library is embedded only after its integrity check. Imported text uses text nodes, JSON escapes script delimiters,
and template substitution runs once. Source hyperlinks open only when clicked. Neither the builder nor graph
exploration uploads data or needs a server. All source records, including filtered-out layers, remain in the HTML and
native graph JSON: remove sensitive content before generating a distributable file. View-state JSON has no import
feature and is not a redacted dataset.

Browser review is repeatable with the commands in the [schema and build reference](../skills/html-network-visualisation/references/schema-and-build.md#commands).
It uses bounded synthetic fixtures; it does not establish large-network performance, remote source availability or
source truth. Font coverage depends on the viewer's installed fonts. Other browsers and operating systems have not
been visually verified by this review.
