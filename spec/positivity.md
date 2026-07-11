# Positivity attack (AssessLite core spec, v0.3 addition)

Positivity — every unit could plausibly have received either exposure level given its
covariates — is one of the three identification assumptions alongside exchangeability
(the confounding and graph checks) and consistency. Where it fails, the covariate space
contains a region in which exposure is near-deterministic, and a single pooled effect
extrapolates a contrast that the data barely support there.

`positivity_check` attacks the `positivity` invariance. It requires a binary 0/1 exposure and
at least one covariate. It fits a propensity score P(exposure = 1 | covariates) by logistic
regression, then trims units whose propensity is near 0 or 1 — outside [α, 1−α] for increasing
α ∈ {0.01, 0.02, 0.05, 0.10} — and refits the outcome model on each trimmed sample. It also
records the fraction of units in the weak-overlap region (propensity < 0.05 or > 0.95).

## Verdict rule (three-way)

1. `unstable` if trimming the weak-overlap units produces a **resolved** shift in the estimate
   (the shared holdout stability rule, spec/stability/metrics.md) — the conclusion demonstrably
   depends on units with poor overlap.
2. else `not_resolvable` if the weak-overlap fraction is ≥ 0.10 — positivity is strained (many
   units have a near-deterministic exposure), but trimming did not resolve a shift, so whether
   the conclusion depends on those units cannot be settled at this n.
3. else `stable` — good overlap and no resolved trimming shift; positivity holds and the finding
   does not lean on weak-overlap regions.

The 0.10 weak-overlap threshold and the 0.05/0.95 propensity cut are declared assessment
heuristics of spec v0.3. The `overlap` block records the weak-overlap fraction and counts.

Trimming naturally inflates variance faster than it moves the point estimate, so a resolved
`unstable` is deliberately hard to reach — the honest signal for strained positivity is the
`not_resolvable` overlap verdict, not a manufactured instability. Richer treatments (a genuine
positivity region test, or bounds under near-violation) are later additions.
