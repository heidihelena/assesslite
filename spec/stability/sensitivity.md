# Sensitivity attacks (AssessLite core spec, v0.2 addition)

Transformation attacks (spec/transformations/transformations.md) refit the estimator under
a symmetry and compare variant estimates. A **sensitivity attack** instead asks how strong a
declared, unobserved violation would have to be to overturn the conclusion. It produces no
variant refits; it produces a scalar on an interpretable scale and a three-way verdict in the
same vocabulary as every other attack.

The first sensitivity attack is `confounding_sensitivity`, which attacks the
`unobserved_confounding` invariance using the **E-value** (VanderWeele & Ding, 2017).

## `confounding_sensitivity` (E-value)

Applies to ratio-scale estimators only: `coxph` (hazard ratio) and `glm_binomial` (odds
ratio). It is **not defined** for a linear coefficient (`glm_gaussian`); requesting it there
is an error, not a silent pass. For hazard and odds ratios the E-value is computed on the
risk-ratio scale under the **rare-outcome approximation** (OR, HR ≈ RR); this is a stated
assumption and is named in the reading text so the analyst can judge it.

Let `RR = exp(estimate)` be the point estimate on the ratio scale, with confidence limits
`LL = exp(ci_low)`, `UL = exp(ci_high)`.

The E-value of a ratio `r` (the minimum strength of association, on the risk-ratio scale,
that an unmeasured confounder would need with **both** exposure and outcome to explain the
association away) is:

```
e(r) = r* + sqrt(r* * (r* - 1)),   where r* = max(r, 1/r)   (so r* >= 1, e >= 1)
```

Reported metrics (always recorded, whatever the verdict):

- `e_value_point = e(RR)`
- `e_value_ci`:
  - `1` if the interval already includes the null (`LL <= 1 <= UL`) — no unmeasured
    confounding is needed to reach no effect;
  - else `e(LL)` if `RR > 1` (the limit nearest the null is the lower one);
  - else `e(UL)` if `RR < 1`.
- `rr_point = RR`, `rr_ci_low = LL`, `rr_ci_high = UL`
- `benchmark` — the analyst-declared plausible confounding strength (E-value scale, >= 1).

## Benchmark

The verdict compares `e_value_ci` to a `benchmark`: the strength of unmeasured confounding
the analyst considers **plausible** given the measured covariates, expressed on the same
risk-ratio scale as an E-value. Default `benchmark = 1.25` (a weak-to-moderate confounder) —
a declared assessment heuristic of spec v0.2, versioned here and adjustable per analysis.
Setting it to the E-value implied by the strongest measured confounder is the recommended,
data-grounded choice.

## Verdict rule (three-way)

1. `not_resolvable` if `e_value_ci == 1` — the interval already includes no effect, so
   "how much confounding would explain it away" is not answerable; the effect itself is not
   established at this n. This is not a pass.
2. else `unstable` if `e_value_ci <= benchmark` — confounding no stronger than what the
   analyst already considers plausible would move the interval to include no effect.
3. else `stable` — overturning the interval would require confounding stronger than the
   declared plausible benchmark.

The verdict then flows through the ordinary decision rules (spec/abstention/rules.md): an
`unstable` result on the assumed `unobserved_confounding` invariance drives `abstain`; an
`untested` or `not_resolvable` one caps the decision at `conditional`.

The thresholds and the rare-outcome approximation are declared heuristics of spec v0.2, not
laws; they are versioned here so any audit's verdict is reproducible from its recorded
metrics, and changing them is a spec change.
