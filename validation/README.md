# AssessLite — validation

Simulation studies that check whether AssessLite's outputs do what the
specification claims. These are **reproducibility scripts, not part of the
package** and not run in CI; they document how the design decisions in the spec
were tested.

## Status of the numbers

**Provisional.** Every figure produced here is from simulated data — one or a
few DGP families, small numbers of seeds, point estimates only. They are
indicative of *mechanism*, not estimates of *effect*. Do not cite specific
numbers (support fractions, correlations, island frequencies) as results; the
transferable content is the qualitative mechanism each script demonstrates.
Separating genuine specification sensitivity from sampling noise is a v2 concern
(the resampling layer), not tested here.

## Stage A (`stageA/`)

Discriminability of the descriptive stability outputs (§7 of the spec) on
simulated cohorts with real analytic choices (adjustment / missingness /
population / model), under exogenous, prespecified claim rules.

| Script | What it checks |
|---|---|
| `assesslite_stageA.py` | The reusable Stage-A harness: cohort DGP, 4-dimension route lattice, route graph, component detection, three effect regimes. Imported by the others. |
| `verify_detector.py` | Correctness of the component counter on planted sign fields — contiguous → 1 component, XOR → 2, parity → 8. The measure recovers known structure exactly. |
| `stageA_final.py` | Connectedness across three claim-rule families; the Γ matrix (pairwise rank correlation of local-agreement orderings across rules); the resolution ratio R; and D_j (which analytic dimension drives disagreement). |
| `assesslite_islands.py`, `islands_natural.py` | When disconnected support ("islands") do and do not arise — an XOR/parity construction vs. interval-rule fragmentation. |
| `rho_dist.py` | Distributions of ρ (distance-to-flip) and L₁ (local agreement); shows unweighted ρ is near-degenerate on dense lattices while L₁ discriminates. |
| `reflexivity.py`, `reflexivity2.py`, `replicate.py`, `replicate2.py` | Whether the stability metrics are themselves sensitive to the analyst's protocol choices. Includes a deliberately retained record of an invalid (route-relative) claim rule and its corrected, exogenous replacement. |
| `onco_claimtest.py`, `batch2.py` | Survival-outcome lattice (Cox / stratified Cox / Weibull AFT on the HR scale) over simulated cohorts calibrated to published oncology effect sizes. Demonstrates the resolving-power-near-a-boundary property. No trial IPD is used; nothing here is a claim about any named trial. |

### Findings the scripts support (qualitative, transferable)

- The component counter is correct (`verify_detector`).
- Practical fragility is **local** — local agreement (L₁) and the directional
  dimension decomposition (D_j) carry the signal; unweighted hop-distance ρ does
  not discriminate on dense lattices.
- D_j **recovers the planted flip mechanism** with order-of-magnitude separation
  from nuisance dimensions.
- Claim-support connectedness depends on the **monotonicity of the claim rule**
  (one-sided rules define connected upper sets; interval rules can fragment) and
  on the roughness of the estimate field — so disconnected support is uncommon in
  smooth realistic lattices.
- Stability rankings are interpretable only relative to a **prespecified,
  exogenous** claim rule; route-relative rules (percentiles/z-scores of the
  multiverse's own results) invert conclusions and are prohibited.
- Resolving power is a function of **distance from the claim boundary**: effects
  far from any decision threshold are unanimous across routes (nothing to
  measure); the method separates safe from fragile routes only near a boundary.

## Running

Python ≥ 3.9 with `numpy`, `scipy`, `pandas`, `statsmodels`, `networkx`; the
survival scripts also need `lifelines`. Each script is standalone and prints its
tables to stdout; run from within `validation/stageA/` so the shared harness
imports resolve.
