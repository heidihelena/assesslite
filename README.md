# AssessLite

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21306424.svg)](https://doi.org/10.5281/zenodo.21306424)
[![PyPI](https://img.shields.io/pypi/v/assesslite.svg)](https://pypi.org/project/assesslite/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**Test what your analysis depends on.**

Structural assumption assessment for causal analysis, for R and Python.

Every causal result borrows strength across units, places, or times. That borrowing is
licensed by invariance assumptions — "these transformations of the system leave the causal
mechanism unchanged" — usually left implicit inside exchangeability, i.i.d. sampling, or
transportability. AssessLite makes them explicit, attacks them, and records what survived.

```
scientific structure  →  declared invariances  →  what each one licenses
    →  transformation attacks  →  three-way verdicts  →  decision (proceed / conditional / abstain)
    →  exported audit record
```

It does not report truth. It records which invariances were asserted, why, which were
attacked, what happened, and whether the conclusion survived. Verdicts are three-way —
stable / unstable / **not resolvable at this n** — because every stability gate is a bright
line on a noisy estimate.

## Sibling to recoverlite

The two tools ask complementary questions:

- **recoverlite** asks: can the method *recover* the quantity it claims to estimate?
- **AssessLite** asks: what assumptions does the result *depend on*, and does it survive
  their violation?

## Product, process, output

The distinction is deliberate and shows up in the code:

- **AssessLite** is the product.
- an **assessment** is the process — you open one, declare its ledger, attack it, decide.
- an **audit record** is the durable output — the exported, portable analytic object.

```r
library(assesslite)

assessment <- structural_audit(
  data       = lung_registry,
  outcome    = c("time", "status"),
  exposure   = "adherence",
  covariates = c("age", "sex", "stage"),
  cluster    = "hospital",
  time       = "diagnosis_year",
  subgroups  = "stage"
)

assessment <- assume_invariance(assessment, "cluster_exchangeability",
  rationale = "hospitals follow the same national guideline; assumed provisionally",
  licenses  = "one pooled effect across hospitals; transport to a hospital outside the sample")

assessment <- test_invariance(assessment,
  tests = c("unit_permutation", "cluster_holdout", "temporal_split", "subgroup_stability"))

assessment <- decide(assessment, abstain_if = list(estimate_sign_changes = TRUE))

write_audit(assessment, "audit.json")     # durable audit record
render_report(assessment, "report.html")  # human-readable report
```

## Install

```r
# from r-universe
install.packages("assesslite",
                 repos = "https://heidihelena.r-universe.dev")
```

```bash
# Python interface
pip install assesslite
```

## Repository layout

```
assesslite/                R package (repo root — what r-universe builds)
├── R/                      engine: assessment, ledger, attacks, verdicts, decision, export
├── tests/                  testthat suite
├── inst/examples/          worked example + its rendered audit record and report
spec/                       language-neutral core specification — never forks
├── schema/                 assumption ledger + audit file format (JSON Schema, YAML example)
├── transformations/        canonical transformation-test definitions
├── stability/              stability metric + three-way verdict rules
├── abstention/             decision and abstention rules
└── reporting/              report structure
python/                     Python interface (pip install assesslite)
├── src/assesslite/         engine mirroring R module-for-module
├── examples/               worked example (mirrors the R one)
└── tests/                  pytest suite incl. cross-schema validation
```

`spec/` is a **specification, not a shared binary**. Both packages implement it natively; an
audit record written by either the R or the Python engine validates against the same
`spec/schema/audit.schema.json`. Conceptual objects stay identical across languages; APIs feel
native to each. Anything in `spec/` may not be redefined inside a language package — that is how
semantic drift is prevented. `spec/` and `python/` are excluded from the R build via
`.Rbuildignore`, so the R package builds cleanly from the repo root; the Python package builds
from `python/`.

## Status

v0.3.0 (development) — working end-to-end in both R and Python against one shared schema.
The baseline: declaration, invariance ledger, the four transformation attacks (unit
permutation, cluster holdout, temporal split, subgroup stability), three-way verdicts, an
abstention-capable decision layer, JSON audit export, and an HTML report. Estimators: Cox
proportional hazards and GLM. See `inst/examples/worked-example.R` and `ROADMAP.md`.

The **Python** interface is built to the same spec (pure numpy/pandas; Cox reproduces R's
`coxph` Breslow fit exactly) with a pytest suite that validates its audit records against the
shared schema. Released versions are on [PyPI](https://pypi.org/project/assesslite/) and
archived on Zenodo.

On top of the baseline, v0.2 and v0.3 add:
- `confounding_sensitivity` — an E-value attack (VanderWeele & Ding) on a new
  `unobserved_confounding` invariance: how strong an unmeasured confounder would have to be to
  move the interval to no effect (`spec/stability/sensitivity.md`).
- `confounding_scenarios` — the bias-analysis complement to the E-value: a deterministic grid of
  unmeasured-confounder scenarios showing where the conclusion tips, targetable at a declared
  decision threshold (`tip_ratio`), not just the null (`spec/scenarios.md`).
- `graph_check` — declare a causal DAG with `declare_graph()`, and the engine tests the
  conditional independencies the graph implies against the data (partial correlation),
  attacking a new `causal_graph` invariance (`spec/graph/graph-check.md`).
- `adjustment_check` — given the same declared DAG, does the covariate set you adjusted for
  satisfy the backdoor criterion? Flags open backdoor paths (under-adjustment) and adjusted
  descendants of the exposure (over-adjustment / mediator or collider bias), and reports a
  minimal sufficient set. Mark unmeasured confounders with `declare_graph(..., latent = ...)`
  and it reports **non-identifiability** — "no measured adjustment can block this backdoor path"
  (`spec/graph/adjustment.md`). Self-contained d-separation engine, no `dagitty` dependency.

- `positivity_check` — fits a propensity score and checks overlap: are there units with a
  near-deterministic exposure, and does the finding lean on them? Attacks the `positivity`
  invariance, the third identification assumption alongside exchangeability and consistency
  (`spec/positivity.md`).

All fold into the same three-way verdicts and decision rules.

For spatial data, `structural_audit(..., coords = c("lon", "lat"))` enables `spatial_holdout` —
leave-one-spatial-block-out over a grid, attacking the `spatial_translation` invariance (does any
region drive the estimate?). See `spec/spatial.md`. For networked data,
`structural_audit(..., unit_id = "id", edges = ...)` enables `interference_check` — does the
outcome depend on neighbours' exposure? A resolved neighbour effect is interference, attacking
`network_relabelling` (SUTVA). See `spec/network.md`.

It also builds an **assumption lattice** (`assumption_lattice()`): the pooling invariances
("pool across clusters / time") are the "stronger symmetry → one number" commitments, so the
lattice refits the exposure estimate under every pool-or-stratify combination and shows, as a
Hasse diagram, whether the conclusion depends on those commitments (`spec/lattice.md`). This is
the geometric-causal-models trade-off made navigable.

The full v0.3 attack set — confounding sensitivity and scenarios, DAG consistency and adjustment
(with latent-node non-identifiability), positivity, spatial holdout, and network interference —
is in place in both languages. Not yet built: a spatial-process (random-field) mechanism model,
richer interference exposure mappings, and a re-estimating identification lattice; see `ROADMAP.md`.

## What this is not

- Not a causal-discovery method and not a guarantee. A "stable" verdict means the conclusion
  survived the attacks that were run, at the precision the data allowed.
- Not a replacement for scientific judgment about which invariances are defensible — it is
  the ledger that makes that judgment visible and attackable.

## Citation

Archived on Zenodo. Cite the concept DOI (always resolves to the latest version):

> Andersén, H. H. AssessLite: test what your analysis depends on.
> https://doi.org/10.5281/zenodo.21306424

Version 0.1.0 is `10.5281/zenodo.21306425`. See `CITATION.cff` for machine-readable
metadata (GitHub's "Cite this repository" uses it).

## Acknowledgement

AssessLite's assumptions-first framing was sparked by **Weinstein & Blei, "Geometric Causal
Models"** ([arXiv:2607.05153](https://arxiv.org/abs/2607.05153), 2026). Their central point —
that generalisation from dependent data requires an explicit invariance assumption, and that the
substantive scientific question is *which* invariances may legitimately be imposed — is the idea
this toolkit is built to serve. Geometric causal models describe which causal structure permits
generalisation; AssessLite is the auditing layer that makes the analyst's invariance and
structural assumptions explicit, attacks them, and records which conclusions survive. The
mapping onto specific transformation groups, the three-way verdicts, the abstention layer, and
the graph and sensitivity checks are AssessLite's own; the framing debt is to that paper.

## License

Apache License 2.0.
