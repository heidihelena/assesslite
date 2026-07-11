# Roadmap

The build order is deliberate: stabilise the core spec and the R interface before adding
either new transformation groups or a second language. Anything that changes the meaning
of an audit file is a `spec/` change and bumps the spec version.

## v0.1 — done

- Core spec: invariance vocabulary, identification/decision vocabulary, transformation
  definitions, stability metrics + verdict rule, abstention rules, report structure,
  audit JSON Schema, example declaration.
- `assesslite`: declaration, invariance ledger (vocabulary-enforced, rationale +
  licence required), four attacks (unit permutation, cluster holdout, temporal split,
  subgroup stability), three-way verdicts, abstention-capable decision layer, JSON audit
  export, self-contained HTML report with an auto-drafted limitations paragraph.
- Cox and GLM estimators. Worked example on fully synthetic multicentre data. Test suite.
- **Python interface** (`python/`, `pip install assesslite`): native `StructuralAudit`
  class over pandas, mirroring the R engine module-for-module. Pure numpy/pandas —
  Cox (Breslow partial likelihood, Newton-Raphson) and GLM (IRLS) implemented in-package,
  no fragile stats dependency; the Cox fit reproduces R's `coxph(ties="breslow")` exactly.
  pytest suite validates its audit records against the shared JSON Schema, and R- and
  Python-written audits both conform to `spec/schema/audit.schema.json` (the round-trip
  contract). Brought forward from v0.5 once the spec froze.

## v0.2 — wrap the established tools (the defensible product line)

- **DAG implications** via `dagitty`: derive the adjustment set from a declared graph,
  list testable conditional-independence implications, and flag when the fitted
  adjustment set disagrees with the declared one. Feeds the ledger.
- **Confounding sensitivity** via `sensemakr` (continuous) and `tipr` (binary): add an
  `unobserved_confounding` invariance whose "attack" is the robustness value, folded into
  the same three-way verdict grammar.
- **Simulation-based violation** (spec `simulated_violation`): parametrically inject a
  declared violation at increasing strength, record where the estimate crosses the
  decision threshold. This is the direct estimator-failure map.
- Geographical holdout as a first spatial-flavoured attack (leave-one-region-out),
  ahead of true spatial translation.

## v0.3 — the lattice

- Render results as a lattice of progressively stronger structural commitments rather
  than a flat list: each node is a set of assumed invariances, each edge adds one, and
  each node shows what became identifiable and whether it stayed stable. This is the
  view that shows "stronger symmetry buys stronger identification, at the cost of a
  stronger assumption" — the paper's central trade-off, made navigable.

## v0.4 — structured dependence and the GCM bridge

- Spatial translation and network relabelling attacks (`spatial_translation`,
  `network_relabelling`), specified in `spec/` first.
- Inspect the geometric-causal-models paper's own code before writing any GCM estimator;
  treat it as the technical dependency, not as evidence the product exists.

## Python interface — done (see v0.1)

Brought forward from its original v0.5 slot once the spec froze. Future Python work:
optional `polars` input, and `DoWhy`/`networkx` bridges for the v0.2–v0.4 attacks as they
land in the spec.

## Not in scope

- A causal-discovery algorithm. This audits declared structure; it does not learn it.
- Any claim of truth, validity about people, or a guarantee. The vocabulary rules in
  `spec/reporting/report-structure.md` are enforced in rendered text.

## Naming

Do not ship as "InvariantVahti" or claim a new general theory — "invariant" collides with
Invariant Causal Prediction. Category: **structural assumption auditing for causal
analysis**. A product name can sit on top of that category later; the package name
`assesslite` is descriptive and safe to keep.
