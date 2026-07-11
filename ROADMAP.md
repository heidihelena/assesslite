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

## v0.3 — in progress

- **Simulation-based violation (confounding scenario array)** — **done.**
  `confounding_scenarios` is a deterministic bias-analysis array (Lin–Psaty–Kronmal;
  VanderWeele–Arah): over a grid of unmeasured-confounder scenarios it shifts the estimate toward
  the target by the implied bias and records where the conclusion tips. Distinct from the E-value
  in three ways — a full failure-map grid rather than one number, a declarable decision threshold
  (`tip_ratio`) not just the null, and a declared confounder prevalence and plausibility bound.
  Both attacks target `unobserved_confounding`; `mark_tested` now keeps the **worst** verdict when
  several attacks share an invariance. Ratio-scale, both R and Python, a `scenarios` block and a
  rendered grid. Spec: `spec/scenarios.md`.
- **Positivity** — **done.** `positivity_check` attacks the `positivity` invariance — the third
  identification assumption alongside exchangeability and consistency. It fits a propensity score
  P(exposure | covariates), records the weak-overlap fraction (propensity < 0.05 or > 0.95), and
  trims those units at increasing thresholds, refitting each time. `unstable` if trimming resolves
  a shift; `not_resolvable` if weak overlap is ≥ 10% (positivity strained but its effect
  unresolved); `stable` on good overlap. Both R and Python; an `overlap` block in the schema.
  Spec: `spec/positivity.md`.
- **Network interference** — **done.** `structural_audit(..., unit_id = "id", edges = ...)`
  declares a network; `interference_check` attacks the `network_relabelling` invariance by adding
  each unit's neighbour exposure to the model and testing whether the outcome depends on it — a
  resolved neighbour-exposure effect is interference (SUTVA fails). Three-way verdict, a
  `spillover` block (neighbour effect, exposure estimate with/without neighbours, units with
  neighbours), both R and Python, `structure.unit_id`/`n_edges` in the schema. Spec: `spec/network.md`.
- **Spatial attack** — **done.** `structural_audit(..., coords = c(x, y))` declares
  coordinates; `spatial_holdout` attacks the `spatial_translation` invariance by
  leave-one-spatial-block-out over a k×k quantile grid — does any region drive the estimate?
  Three-way verdict, both R and Python, `structure.coords` in the schema. Spec: `spec/spatial.md`.
- **Multiplicity fix in the holdout verdict rule** — **done (spec v0.3).** Spatial holdout (many
  blocks) exposed that the old `max_shift_z > 2` rule flags ~m times too often under stability;
  with 9 blocks the false-positive rate is ~34%. The verdict now uses a Bonferroni-adjusted
  `shift_p_bonf` (min over variants of m × the two-sided shift p-value). This corrected a
  spurious `cluster_holdout` → abstain in the worked example (12 hospitals). Applies to every
  holdout attack (cluster, temporal, subgroup, spatial); R `pnorm` and Python `erfc` agree
  bit-for-bit. See `spec/stability/metrics.md`.
- **Latent (unmeasured) nodes** — **done.** `declare_graph(edges, latent = ...)` marks graph
  nodes that are part of the causal structure but not measured. `adjustment_check` now answers
  identifiability: a valid observed adjustment set exists iff the canonical set (van der Zander
  et al.) is valid; if not, the effect is not identifiable by covariate adjustment and the
  verdict is `not_resolvable` (capping the decision at `conditional`), with the `identifiable`
  flag recorded. `graph_check` skips any implication touching a latent node as not-testable.
  Both R and Python; schema gains an `identifiable` field. Verified on a latent-confounder DAG.
- Still ahead: simulation-based violation testing; spatial/network transformation groups; a
  richer lattice that re-estimates identifiability per node.

## v0.2 — wrap the established tools (the defensible product line)

- **Confounding sensitivity** — **done (v0.2.0).** New `unobserved_confounding` invariance
  attacked by `confounding_sensitivity`, an E-value analysis (VanderWeele & Ding, 2017):
  how strong an unmeasured confounder would have to be, on the risk-ratio scale, to move the
  interval to no effect. Self-contained (no external package), ratio-scale estimators
  (Cox HR, logistic OR) under the stated rare-outcome approximation; undefined on a linear
  scale (an error, not a silent pass). Folds into the same three-way verdict grammar —
  `not_resolvable` when the interval already includes no effect — and the same decision
  rules. Spec: `spec/stability/sensitivity.md`. Implemented in both R and Python; audit
  records carry a `sensitivity` block that validates against the shared schema. This is a
  first-class sensitivity attack rather than a `sensemakr`/`tipr` wrapper, which keeps the
  dependency footprint at numpy/pandas and base R.
- **DAG implications** — **done in part (v0.2.0).** New `causal_graph` invariance attacked by
  `graph_check`: the analyst declares a DAG (`declare_graph`), the engine derives the implied
  conditional independencies (ordered local Markov) and tests each against the data by partial
  correlation, returning a three-way verdict per implication and overall. Self-contained (no
  `dagitty`), both R and Python; audit records carry an `implications` block that validates
  against the shared schema. Spec: `spec/graph/graph-check.md`. Correctly leaves colliders
  unconditioned and skips multi-level-categorical endpoints as not-testable rather than
  mis-testing them.
- **DAG adjustment set** — **done (v0.2.0).** New `adjustment_sufficiency` invariance attacked by
  `adjustment_check`: given the declared graph, does the covariate set the model adjusted for
  satisfy the backdoor criterion? Reports open backdoor paths (under-adjustment), descendants of
  the exposure that were adjusted (over-adjustment / collider or mediator bias), and a minimal
  sufficient set derived from the graph. Backdoor validity via a self-contained d-separation
  engine (moralised ancestral graph), verified on the confounding triangle, mediator, and M-bias
  cases. Both R and Python; audit records carry an `adjustment` block that validates against the
  shared schema. Spec: `spec/graph/adjustment.md`. Still to add: latent-node support (marking
  graph variables unmeasured, so no valid observed adjustment set may exist → not identifiable);
  a non-linear conditional-independence test for `graph_check` beyond partial correlation.
- **Simulation-based violation** (spec `simulated_violation`): parametrically inject a
  declared violation at increasing strength, record where the estimate crosses the
  decision threshold. This is the direct estimator-failure map.
- Geographical holdout as a first spatial-flavoured attack (leave-one-region-out),
  ahead of true spatial translation.

## The lattice — done in part (v0.2.0)

Brought forward from v0.3. `assumption_lattice()` renders the **pooling** commitments as a
lattice: the axes are the pooling invariances (cluster, time), each node pools some axes and
stratifies the rest (Cox `strata()` / GLM fixed effects), and the exposure estimate is refit at
every node. Nodes are classified consistent / attenuated / reversed against the fully-pooled
estimate, giving a three-way lattice verdict — does the conclusion depend on the pooling
commitments? Rendered as a Hasse diagram plus a node table; stored as a top-level `lattice`
object validated against the shared schema. Spec: `spec/lattice.md`. This realises the paper's
"stronger symmetry buys a stronger (single) number, at the cost of a stronger assumption" for
the pooling axes. Still to generalise: a lattice over the identification invariances that
**re-estimates** what becomes identifiable at each node (needs per-node estimand definitions), and
richer visual layout for more axes.

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
