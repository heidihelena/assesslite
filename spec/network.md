# Network interference attack (AssessLite core spec, v0.3 addition)

Networked units — patients in a contact network, clinicians who refer to one another,
individuals exposed to a public-health intervention that spills over — are the other
dependent-data setting the geometric-causal-models framing targets. The `network_relabelling`
invariance says relabelling the nodes, preserving the graph structure, leaves the causal
mechanism unchanged: equivalently, a unit's outcome does not depend on who its neighbours are or
on their exposure. That is the no-interference (SUTVA) assumption.

`interference_check` attacks it directly. The analyst declares a network —
`structural_audit(..., unit_id = "id", edges = edge_frame)` (one row per unit; `edge_frame` a
two-column frame of undirected unit-id pairs). The engine computes each unit's **neighbour
exposure** — the mean exposure among its neighbours present in the data — imputing the sample
mean for units with no neighbours (a neutral value that keeps them in the model). It refits the
estimator with `neighbor_exposure` added as a covariate, and reads two things: the
neighbour-exposure coefficient (the spillover) and the own-exposure estimate before and after
accounting for neighbours.

## Verdict rule (three-way)

Let the neighbour-exposure coefficient have standard error `se_nb`, and let the exposure effect
be `|est_0|` on its natural scale.

1. `unstable` if the neighbour-exposure interval excludes zero — the outcome demonstrably depends
   on neighbours' exposure. Interference is present, so relabelling the network changes the
   mechanism and SUTVA does not hold; a single per-unit estimate that ignores spillover is
   suspect.
2. else `not_resolvable` if `1.96 × se_nb` exceeds `max(|est_0|, 0.1)` — the spillover could not
   be resolved at this n (a neighbour effect as large as the exposure effect could not have been
   detected); interference can neither be shown nor ruled out.
3. else `stable` — no detectable dependence on neighbours' exposure, resolved to be smaller than
   the exposure effect.

The `spillover` block records the neighbour-exposure coefficient and interval, the exposure
estimate ignoring and accounting for neighbours, and the number of units with at least one
neighbour. Neighbour exposure as mean-of-neighbours is the simplest interference summary; richer
exposure mappings (fraction exposed above a threshold, distance-weighted, second-order
neighbours) and a genuine node-relabelling permutation test are later additions.
