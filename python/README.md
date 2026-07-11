# AssessLite (Python)

**Test what your analysis depends on.**

Structural assumption assessment for causal analysis — the native Python interface to
the AssessLite core specification v0.1. The R package (`assesslite` on r-universe) implements
the same spec; audit records written by either conform to the same JSON Schema.

Every causal result borrows strength across units, places, or times, licensed by invariance
assumptions usually left implicit inside exchangeability or i.i.d. sampling. AssessLite makes
them explicit, attacks them, and records what survived — with three-way verdicts (stable /
unstable / **not resolvable at this n**), because every stability gate is a bright line on a
noisy estimate.

## Install

```bash
pip install assesslite
```

Pure `numpy` + `pandas`; the Cox (Breslow partial likelihood) and GLM (IRLS) estimators are
implemented in-package, so there is no heavy or version-fragile stats dependency.

## Use

```python
from assesslite import StructuralAudit

assessment = StructuralAudit(
    data=lung_registry,                 # pandas DataFrame
    outcome=("time", "status"),         # Cox; or "y" for a GLM
    exposure="adherence",
    covariates=["age", "sex", "stage"],
    cluster="hospital",
    time="diagnosis_year",
    subgroups=["stage"],
    unit="patient",
)

assessment.assume(
    "cluster_exchangeability",
    rationale="hospitals follow the same national guideline; assumed provisionally",
    licenses="one pooled effect across hospitals; transport to a hospital outside the sample",
)

assessment.test(
    ["unit_permutation", "cluster_holdout", "temporal_split", "subgroup_stability"]
).decide(abstain_if={"estimate_sign_changes": True})

print(assessment)
audit = assessment.export_audit("audit.json")   # durable audit record (also returned as a dict)
assessment.render_report("report.html")          # self-contained HTML report
```

## Product, process, output

- **AssessLite** is the product.
- an **assessment** — a `StructuralAudit` — is the process: open it, declare its ledger,
  attack it, decide.
- an **audit record** is the durable output: `export_audit()` returns it as a dict and writes
  it as schema-conforming JSON.

## Estimators

- `("time", "status")` → Cox proportional hazards (Breslow ties), log hazard ratio.
- binary 0/1 outcome → logistic GLM, log odds ratio.
- continuous outcome → linear GLM, linear coefficient.

The Cox implementation reproduces R's `coxph(ties="breslow")` coefficients and standard errors
exactly.

See `examples/worked_example.py` for a complete run on simulated multicentre data.
Apache License 2.0.
