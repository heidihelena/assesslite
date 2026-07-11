# Spatial attack (AssessLite core spec, v0.3 addition)

Spatial data are the setting the geometric-causal-models framing was built for: shifting the
whole field should not change the mechanism. That is the `spatial_translation` invariance —
one mechanism holds across locations, so a single pooled estimate is licensed.

`spatial_holdout` attacks it the way `cluster_holdout` attacks cluster exchangeability, but over
geography rather than a declared grouping. The analyst declares coordinates —
`structural_audit(..., coords = c("lon", "lat"))` (or `coords=("x", "y")` in Python) — two
numeric columns. The engine grids the coordinate space into a `k × k` lattice of blocks from
the quantile bins of each axis (so blocks hold roughly equal counts), and refits the exposure
estimate with each block removed in turn. Rows with missing coordinates are kept in every refit.

Each block-removed refit is a variant estimate. The result uses the same stability metrics and
three-way verdict as every holdout attack (spec/stability/metrics.md): `stable` if no block's
removal moves the estimate beyond sampling noise, `unstable` if some region's removal produces a
resolved shift (the mechanism is not spatially stationary — a particular area drives the
estimate), `not_resolvable` if the block-removed intervals are too wide to tell.

`k` defaults to 3 (up to nine blocks). Smaller `k` gives larger, better-powered blocks;
larger `k` gives finer spatial resolution but noisier per-block refits. As with `cluster_holdout`
this is a leave-one-region-out test of pooling, not a model of the spatial process itself; a
spatial-process model (e.g. a Gaussian-random-field mechanism in the sense of the paper) is a
later addition.

## Spatial autocorrelation (v0.4 addition)

`spatial_holdout` asks whether the mechanism is the same across regions. The
`spatial_autocorrelation` attack asks the complementary question: are observations
spatially **independent** given the model? It attacks the `spatial_independence`
invariance — the assumption licensing i.i.d.-style intervals on spatial data. This is the
spatial-process (random-field) concern made operational: correlated residuals mean nearby
units share unmodelled structure, the effective sample size is smaller than n, and the
pooled interval overstates precision.

Procedure: fit the declared outcome model and take its residuals — **martingale** residuals
for Cox (Breslow baseline hazard), **response** residuals (y − μ) for GLMs — then compute
**Moran's I** over a row-standardised k-nearest-neighbour weight matrix (default k = 8,
Euclidean distance on the declared coordinates), with mean and variance under the normality
assumption (Cliff & Ord), so the test is deterministic given the data.

Verdict rule (three-way): `unstable` if p < 0.05 and |I| ≥ `i_floor` (default 0.1);
else `not_resolvable` if the smallest resolvable I at this n (1.96 × se) exceeds the floor;
else `stable`. The `autocorrelation` block records I, its expectation and se, z, p, k, n,
and the residual type. The k, floor, and normality approximation are declared assessment
heuristics of spec v0.4. Fitting an explicit spatial-process (Gaussian-random-field)
mechanism model remains future work; this attack is the diagnostic that tells you whether
you need one.
