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
