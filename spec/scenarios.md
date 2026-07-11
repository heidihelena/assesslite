# Confounding scenario array (AssessLite core spec, v0.3 addition)

`confounding_sensitivity` reports the E-value — one number, the confounding strength that would
move the estimate to the null. `confounding_scenarios` is the map: a deterministic bias-analysis
array over a grid of unmeasured-confounder scenarios, showing the adjusted estimate in each and
where the conclusion tips. It is the simulation-based-violation attack in the sense of injecting
a declared violation at increasing strength and recording where the estimate crosses the
decision target. Both attack the same `unobserved_confounding` invariance; the ledger keeps the
worse of the two verdicts.

Three things distinguish it from the E-value: it produces the full grid rather than a single
number; it can target a declared **decision threshold**, not only the null ("what confounder
would move my hazard ratio past a clinically meaningful 0.80?"); and it uses a declared
confounder **prevalence** and **plausibility bound**.

Ratio-scale estimators only (`coxph`, `glm_binomial`), under the rare-outcome approximation,
exactly as for the E-value.

## Bias array

For a binary unmeasured confounder U with outcome risk ratio `rr_uy`, prevalence `p0` in the
unexposed and `p1 = p0 + delta` in the exposed, the bias factor (Lin, Psaty & Kronmal 1998;
VanderWeele & Arah 2011) is

```
BF = [1 + (rr_uy - 1)(p0 + delta)] / [1 + (rr_uy - 1) p0]
```

The array sweeps `rr_uy ∈ {1.5, 2, 3, 4}` and `delta ∈ {0.1, 0.2, 0.3, 0.4}` at the declared
prevalence (default 0.2). Each cell shifts the estimate toward the null (target) by the bias
magnitude: `adjusted = observed − sign(observed)·log(BF)`. A cell **tips** if the adjusted
estimate crosses the target (the null, or the declared `tip_ratio` on the ratio scale).

## Verdict rule (three-way)

- `not_resolvable` if the interval already includes the target — the effect is not established
  beyond the target, so the confounding needed to reach it is undefined.
- `unstable` if any cell **within the plausible bound** (default `rr_uy ≤ 2` and `delta ≤ 0.2`)
  tips — a plausible confounder overturns the conclusion.
- `stable` if only cells beyond the plausible bound tip.

The `scenarios` block records the target, the declared prevalence and plausibility bound, the
minimal tipping scenario within the bound, and every cell (`rr_uy`, `delta`, `bias_factor`,
`adjusted_estimate`, `tips`). The grids, the 0.2 default prevalence, and the plausibility bound
are declared assessment heuristics of spec v0.3.
