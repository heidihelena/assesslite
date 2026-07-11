# Adjustment-set check (AssessLite core spec, v0.2 addition)

`graph_check` asks whether the declared DAG is contradicted by the data. `adjustment_check`
asks the complementary question: **given the declared DAG, is the set of covariates the model
actually adjusted for a valid one?** It attacks the `adjustment_sufficiency` invariance — the
assumption that the adjusted covariates identify the exposure effect.

This is a purely structural check on the graph (no sampling), so its verdict is deterministic
given the graph, not a bright line on a noisy estimate. It still reports in the three-way
vocabulary: `stable` (adjustment agrees with the graph), `unstable` (it does not), and
`not_resolvable` (the check cannot be run — exposure or outcome is not a node in the graph).

## Backdoor criterion

A covariate set Z is a valid adjustment set for the effect of exposure X on outcome Y (Pearl's
backdoor criterion) when:

1. no member of Z is a descendant of X, and
2. Z blocks every backdoor path from X to Y — equivalently, Z d-separates X from Y in the graph
   with X's outgoing edges removed.

d-separation is decided by the moralised-ancestral-graph algorithm (Lauritzen et al.): take the
ancestral subgraph of X, Y, and Z; connect the parents of each node (moralise); drop edge
directions; remove Z; X and Y are d-separated iff they are then disconnected.

## What the attack reports

For the declared graph, the exposure X, the outcome node Y, and the covariates Z the model
adjusted for:

- **valid** — whether Z satisfies the backdoor criterion.
- **open_backdoor** — whether a backdoor path remains unblocked (under-adjustment → residual
  confounding the graph implies).
- **over_adjustment** — members of Z that are descendants of X (mediators or colliders; adjusting
  them introduces bias).
- **sufficient_set** — a minimal valid adjustment set derived from the graph (greedily reduced
  from the parents of X, which always block the backdoor paths when observed).
- **missing** — nodes in the sufficient set that were not adjusted for.

## Verdict rule

1. `not_resolvable` if X or Y is not a node in the declared graph — the adjustment cannot be
   checked against the graph.
2. `unstable` if Z is not a valid adjustment set — either a backdoor path is left open, or Z
   conditions on a descendant of X. The reading names which, and gives a sufficient set.
3. `stable` if Z satisfies the backdoor criterion.

A `stable` verdict is conditional on the declared graph being correct (which `graph_check`
probes separately) and on all confounders in the graph being observed; latent-variable support
(marking graph nodes as unmeasured, so that no valid observed set may exist) is a later
addition. The verdict flows through the ordinary decision rules on the `adjustment_sufficiency`
invariance.
