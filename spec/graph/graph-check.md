# Causal-graph check (AssessLite core spec, v0.2 addition)

The transformation and sensitivity attacks probe whether a *result* holds up. The
`graph_check` attack probes whether the *declared causal structure* is contradicted by the
data. The analyst declares a directed acyclic graph (DAG); the engine derives the
conditional independencies the DAG implies and tests each against the data. It attacks the
`causal_graph` invariance — the assumption that the declared graph is correct.

This is the testable-implications idea (as in DAGitty), implemented self-contained and folded
into the same three-way verdict grammar and decision rules. It does not learn a graph and it
does not prove one correct; it reports which of the graph's own implications the data
contradict.

## Declaring the graph

The analyst declares directed edges, e.g. `age -> adherence`, `stage -> survival`. Nodes are
the union of everything named. The graph must be acyclic. Declaring the graph is separate from
the invariance ledger; the ledger still carries `causal_graph` as an assumed (or rejected)
claim.

## Implied conditional independencies

Using a topological ordering of the nodes, the **ordered local Markov** property gives a
complete basis of implied independencies: for each node V and each predecessor W (earlier in
the ordering) that is not a parent of V,

```
V  ⟂  W  |  parents(V)
```

Each such statement is a testable claim. A statement is **testable** here only when V and W are
each numeric or binary (coercible to one column) and every node it touches is observed; a
statement whose V or W is a multi-level categorical, or whose endpoints or conditioning set
include a **latent** node (declared via `declare_graph(..., latent = ...)`) or any node absent
from the data, is recorded as **not testable** and skipped, never silently passed. Conditioning
variables of any observed type are allowed (categoricals are expanded to indicator columns).

## Test

Each testable statement `V ⟂ W | Z` is checked by **partial correlation**: residualise V and W
on the conditioning set Z by ordinary least squares (Z expanded with indicators and an
intercept), correlate the residuals to get `r`, and test it with Fisher's z,
`z = atanh(r) * sqrt(n - k - 3)`, where k is the rank of Z. This is a linear/Gaussian
approximation to conditional independence and is named as such in the reading — it is the same
kind of stated assumption as the rare-outcome approximation in `confounding_sensitivity`.

Per-statement reading:
- **violated** if `p < alpha` and `|r| >= effect_floor` — the data resolve a dependence the
  graph says should not exist.
- **not resolvable** if not violated but the smallest detectable partial correlation at this n,
  `tanh(1.96 / sqrt(n - k - 3))`, exceeds `effect_floor` — the test could not have seen a
  material dependence.
- **consistent** otherwise.

Defaults `alpha = 0.05`, `effect_floor = 0.1` are declared assessment heuristics of spec v0.2,
versioned here and adjustable per analysis.

## Verdict rule (three-way)

Over all testable statements:

1. `unstable` if any statement is **violated** — the data contradict an independence the graph
   implies, so the declared graph does not hold up.
2. else `not_resolvable` if no statement is violated but at least one is **not resolvable**, or
   no statement was testable — the graph's implications could not be assessed at this n.
3. else `stable` — every implied independence the data could resolve is consistent with the
   graph.

The verdict flows through the ordinary decision rules (spec/abstention/rules.md): an `unstable`
result on an assumed `causal_graph` drives `abstain`; `untested`/`not_resolvable` caps at
`conditional`.

A `stable` verdict does not establish the graph — many graphs share the same implications
(Markov equivalence), and untestable statements are skipped. It records only that the data did
not contradict the implications that could be tested.
