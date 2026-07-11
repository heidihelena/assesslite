# Assumption lattice (AssessLite core spec, v0.2 addition)

The pooling invariances are the "stronger symmetry buys a stronger (single) number"
commitments: assuming `cluster_exchangeability` licenses pooling one effect across clusters;
assuming `temporal_translation` licenses pooling across time. The assumption lattice makes that
trade-off navigable — it refits the exposure estimate under **every combination** of pooling or
stratifying on those axes and shows whether the conclusion depends on the pooling commitments.

This is the geometric-causal-models point made operational: at the top of the lattice you pool
everything (the strongest commitment, one number — the main estimate); at the bottom you
stratify everything (separate baselines per cluster and per period, the weakest pooling
assumption); each step up adds one pooling commitment.

## Axes and nodes

Axes are the declared structural pooling variables among {cluster, time}. (Subgroup
transportability is effect-modification rather than a single-estimate pool, and is handled by
the `subgroup_stability` attack, not here.) For k axes there are 2^k nodes, one per subset of
axes pooled; the complement is stratified. Stratifying an axis means a Cox `strata()` (separate
baseline hazards) or, for a GLM, fixed-effect factors — the exposure effect stays a single
number, so nodes are comparable.

## Node status

Each node's refit estimate is compared to the top (fully-pooled) estimate on the natural scale
(null = 0):

- `consistent` — same sign as the main estimate and the interval excludes no-effect.
- `attenuated` — the interval includes no-effect (direction may hold, but it is not resolved).
- `reversed` — opposite sign with the interval excluding no-effect (a resolved sign change).

## Lattice verdict (three-way)

1. `unstable` if any node is `reversed` — the conclusion's direction depends on the pooling
   commitments.
2. else `not_resolvable` if any node is `attenuated` — the direction holds throughout, but
   whether the effect is resolved depends on the pooling commitments.
3. else `stable` — the conclusion holds under every pool-or-stratify choice.

The lattice is a reporting layer over refits, not an attack on a single invariance, so it is not
in the `tests` list and does not itself set a ledger verdict; it is stored as a top-level
`lattice` object in the audit and rendered as a Hasse diagram plus a node table. It complements
the per-axis `cluster_holdout` and `temporal_split` attacks: those ask whether one axis is
exchangeable; the lattice asks whether the *conclusion* survives every pooling choice jointly.
