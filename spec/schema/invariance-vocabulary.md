# Invariance vocabulary (core spec v0.1)

Canonical names for invariance claims. Language packages must use these identifiers in
ledgers, audit files, and reports. New identifiers are added here first, never invented
ad hoc in a package.

An invariance claim always has the form: *applying transformation T to the observed
system leaves the causal mechanism for the estimand unchanged*. Each claim licenses
something — pooling, transport, or identification. Declaring a claim does not make it
true; the ledger records it so it can be attacked.

## Identifiers

| id | transformation | typical licence |
|---|---|---|
| `unit_permutation` | permute the order of units | any estimator that treats units symmetrically; the i.i.d.-style baseline |
| `unit_permutation_within_cluster` | permute units within each cluster, clusters fixed | pooling units into one within-cluster likelihood |
| `cluster_exchangeability` | permute cluster identities | pooling across clusters; transport of the estimate to an unobserved cluster |
| `temporal_translation` | shift the calendar window | pooling across periods; applying the estimate to a future period |
| `subgroup_transport` | move the mechanism across declared subgroups | one pooled effect rather than subgroup-specific effects |
| `unobserved_confounding` | none — this is the assumption that the measured adjustment set is sufficient (conditional exchangeability given measured covariates) | reading the adjusted association as the causal effect |
| `causal_graph` | none — this is the assumption that the analyst's declared DAG is correct | licensing every adjustment-set and identification claim read off the graph |
| `adjustment_sufficiency` | none — this is the assumption that the covariates adjusted identify the effect (satisfy the backdoor criterion in the declared graph) | reading the adjusted estimate as the causal effect |
| `spatial_translation` | translate the spatial field | pooling one mechanism across locations; attacked by `spatial_holdout` (leave-one-spatial-block-out) |
| `network_relabelling` | relabel nodes preserving graph structure | treating units as non-interfering (SUTVA); attacked by `interference_check` (does the outcome depend on neighbours' exposure?) |

`unobserved_confounding` is different in kind from the transformation invariances above:
it is not a symmetry of the data but the no-unmeasured-confounding assumption itself. Its
attack is not a refit under a transformation but a **sensitivity analysis** — how strong an
unmeasured confounder would have to be to overturn the result (see
`spec/stability/sensitivity.md`). It carries a `verdict` in the same three-way vocabulary.

## Ledger statuses

Each declared invariance carries exactly one status:

- `assumed` — the analysis relies on it; it should be attacked if a test exists.
- `rejected` — the analyst asserts it does not hold; the analysis must not rely on it
  (e.g. rejected `cluster_exchangeability` means cluster must enter the model as
  structure, and transport claims to new clusters are out of scope).
- `untested` — assumed but no attack was run. The audit must list these; they are the
  exposed surface of the argument.

Every `assumed` or `rejected` entry requires a `rationale` (why it is scientifically
defensible or not) and a `licenses` field (what inferential step it buys). An assumption
with no stated licence should be questioned: if it buys nothing, why assume it?
