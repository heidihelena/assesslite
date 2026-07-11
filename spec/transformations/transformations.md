# Transformation tests (core spec v0.1)

Each test attacks one named invariance by refitting the declared estimator under a
transformation or exclusion and comparing variant estimates to the full-sample estimate.
All comparisons happen on the estimator's natural scale (log hazard ratio, log odds
ratio, linear coefficient). Implementations must record every variant estimate with its
interval and n — never only a summary statistic.

## `unit_permutation`

Attacks: `unit_permutation` (and, with cluster fixed, `unit_permutation_within_cluster`).
Procedure: permute row order (within cluster if declared) `n_perm` times, refit.
Reading: estimates must be identical to machine precision. Any movement means the
estimator itself depends on unit ordering — an implementation or data problem, not a
scientific finding. This is the sanity floor under every other test.

## `cluster_holdout` (leave-one-cluster-out)

Attacks: `cluster_exchangeability`.
Procedure: for each cluster c, refit on data excluding c.
Reading: if pooling across clusters is licensed, no single cluster's removal should move
the pooled estimate materially. A material shift means at least one cluster has a
privileged causal role — pooling and transport to unobserved clusters lose their licence.

## `temporal_split`

Attacks: `temporal_translation`.
Procedure: split the time variable at its median into early/late windows (or refit per
declared period when few unique periods exist), refit per window.
Reading: if the mechanism is calendar-invariant, window estimates should agree with the
pooled estimate up to sampling noise. Divergence means the mechanism drifted — pooling
across periods and extrapolation to future periods lose their licence.

## `subgroup_stability`

Attacks: `subgroup_transport` for each declared subgroup variable.
Procedure: refit within each level of the subgroup variable.
Reading: divergence means one pooled effect misdescribes the subgroups; report
subgroup-specific effects or restrict the claim's domain.

## Not yet specified (reserved)

`spatial_shift`, `network_relabelling`, `simulated_violation` (parametric simulation of a
declared violation to measure estimator failure). To be specified here before any
implementation.
