# Optional adaptations

The supplied builder produces offline snapshots. Database loading, community detection and centrality scores require
additional implementation and tests; none is an automatic feature of this skill.

For a growing dataset, keep credentials and database queries on a read-only server. Preserve string IDs and explicit
support when returning aggregates. A local service should bind to loopback, validate Host/Origin and serve an explicit
asset allowlist. Show data-as-of time, refresh state and coverage. Publish a consistent snapshot atomically; a failed
refresh should retain the last complete one. Measure query plans before optimising a slow load.

For analysis, define the universe before display limits and neighbourhood filters. State arrow meaning, weight units,
self-link treatment, algorithm parameters and convergence limits. Compute scores on that declared universe, then
filter the view. Graph centrality is not proof of real-world influence. Community membership is an algorithmic
partition, not established affiliation; report its method, seed, resolution and sensitivity. Keep evidence status and
node type distinguishable through shapes and dashes when community colours are added.

Test adapters on bounded synthetic data with known endpoints, directions, counts and scores. Verify incomplete and
failed refreshes, identity preservation, evidence inspection and coverage notices. Do not claim full archive coverage
or large-network performance from the bundled six-node browser fixture.
