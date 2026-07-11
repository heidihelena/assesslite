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

## Latent (unmeasured) nodes and identifiability

`declare_graph(edges, latent = ...)` marks nodes that are part of the causal structure but not
measured — an unmeasured confounder, say. Latent nodes may not enter an adjustment set. This
lets the check answer the identifiability question honestly.

A valid observed adjustment set exists iff the **canonical set** is valid (van der Zander,
Liśkiewicz & Textor, 2014): `Z0 = (An(X) ∪ An(Y)) ∩ observed \ ({X, Y} ∪ De(X))` — the observed
ancestors of X or Y, excluding X, Y, and descendants of X. If `Z0` does not satisfy the backdoor
criterion, then **no** observed set does: the effect is not identifiable by covariate
adjustment given the graph (a backdoor path runs through unmeasured variables and cannot be
blocked). When a valid set exists, the minimal `sufficient_set` is a greedy reduction of `Z0`.

## Verdict rule

1. `not_resolvable` if X or Y is not a node in the declared graph, **or** the effect is not
   identifiable by adjustment (no observed set blocks all backdoor paths) — the adjustment
   question cannot be settled by covariate adjustment.
2. `unstable` if a valid set exists but Z is not one — either a backdoor path is left open, or Z
   conditions on a descendant of X. The reading names which, and gives a sufficient set.
3. `stable` if Z satisfies the backdoor criterion.

The `identifiable` flag is recorded in the audit's `adjustment` block. A `stable` verdict is
conditional on the declared graph being correct (which `graph_check` probes separately). The
verdict flows through the ordinary decision rules on the `adjustment_sufficiency` invariance —
a non-identifiable effect caps the decision at `conditional`.
