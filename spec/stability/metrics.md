# Stability metrics and verdict rules (core spec v0.1)

Notation: full-sample estimate `est_0` with standard error `se_0`; variant estimates
`est_j` with standard errors `se_j`, j = 1..k. All on the estimator's natural scale,
null value 0 on that scale (log HR, log OR, linear coefficient).

## Metrics (all recorded in the audit file)

- `max_shift_z` = max_j |est_j − est_0| / se_diff_j, with
  `se_diff_j` = sqrt(se_j² − se_0²) when se_j > se_0, else se_0.
  — largest variant shift in units of the standard error of the *difference*.
  Because est_0 is (approximately) a precision-weighted combination that contains the
  variant, cov(est_j, est_0) ≈ se_0², so var(est_j − est_0) ≈ se_j² − se_0². This holds
  for both leave-one-out variants and disjoint-split variants. Dividing by se_0 instead
  would flag expected sampling wobble of small variants as instability: a variant fitted
  on a subset is *supposed* to move by more than the full-sample noise level under a
  perfectly stable mechanism.
- `sign_flips_resolved` = count of j where sign(est_j) ≠ sign(est_0) AND the variant's
  95% interval excludes 0 — sign changes distinguishable from noise.
- `sign_flips_unresolved` = count of j where sign(est_j) ≠ sign(est_0) but the variant's
  interval includes 0.
- `mds` (minimal detectable shift) = 1.96 × median_j(se_j)
  — roughly the smallest shift this attack could have resolved at this n.
- `null_crossings` = count of variants whose interval includes 0 when the full-sample
  interval excludes 0 (or vice versa) — variants that change the qualitative reading.

## Verdict rule (three-way; deterministic given the metrics)

1. `unstable` if `sign_flips_resolved` ≥ 1 OR `max_shift_z` > 2.
2. else `not_resolvable` if `mds` > max(2 × se_0, |est_0|)
   — the attack could not have detected a shift as large as the estimate itself, or
   twice the full-sample noise level, so "no shift seen" is uninformative.
3. else `stable`.

Special case `unit_permutation`: `unstable` if any |est_j − est_0| exceeds numerical
tolerance (1e−8); `not_resolvable` only if refits fail; otherwise `stable`. No interval
logic — this test is deterministic.

These thresholds (2 se, 1.96, the mds comparison) are declared assessment heuristics of
spec v0.1, not laws. They are versioned here so that a verdict in any audit file is
reproducible from its recorded metrics, and so that changing them is a spec change, not
a silent package change. Implementations must record the spec version in every audit.
