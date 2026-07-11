# AssessLite

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

v0.1.0 — working end-to-end in R: declaration, invariance ledger, four transformation tests
(unit permutation, cluster holdout, temporal split, subgroup stability), three-way verdicts,
abstention-capable decision layer, JSON audit export, HTML report. Estimators: Cox
proportional hazards and GLM. See `inst/examples/worked-example.R` and `ROADMAP.md`.

The **Python** interface is built to the same spec (pure numpy/pandas; Cox reproduces R's
`coxph` Breslow fit exactly) with a pytest suite that validates its audit records against the
shared schema.

Not yet built: DAG implications (dagitty), confounding sensitivity (sensemakr/tipr),
simulation-based violation testing, spatial/network transformation groups, and the assumption
lattice view.

## What this is not

- Not a causal-discovery method and not a guarantee. A "stable" verdict means the conclusion
  survived the attacks that were run, at the precision the data allowed.
- Not a replacement for scientific judgment about which invariances are defensible — it is
  the ledger that makes that judgment visible and attackable.

## License

Apache License 2.0.
