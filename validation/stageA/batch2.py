"""
BATCH 2 — boundary-proximate thoracic oncology settings.

Batch 1 (CheckMate 816 / KEYNOTE-189 / ADAURA) was DEGENERATE: those trials were designed
to be unambiguous, effects sit far from any decision boundary, every route agreed.
That is the selection principle for Batch 2: pick effects that sit ON the boundary.

Real published effects (verified):
  IMpower010 adjuvant atezolizumab, OS ITT          HR 0.995 (95% CI 0.78-1.28)  <- ON directional boundary
  KEYNOTE-091 adjuvant pembrolizumab, DFS ITT       HR 0.76  (0.63-0.91)         <- just INSIDE threshold 0.80
  KEYNOTE-091 DFS, PD-L1 TPS >=50% subgroup         HR 0.82  (0.57-1.18)         <- just OUTSIDE threshold 0.80
  IMpower010 OS, stage II-IIIA PD-L1 TC >=1%        HR 0.71  (0.49-1.03)         <- INSIDE band [0.50,0.80]
  IMpower010 OS, stage II-IIIA PD-L1 TC >=50%       HR 0.43  (0.24-0.78)         <- BELOW band [0.50,0.80]

Claim rules (exogenous, declared a priori, scale-free on the HR):
  directional  HR < 1.00
  threshold    HR < 0.80          (clinically meaningful benefit)
  interval     0.50 <= HR <= 0.80 (meaningful AND plausible as an OS surrogate)

Cohorts are SIMULATED and calibrated to the published HRs and sample sizes.
No trial individual patient data is used and none is claimed. This tests the
MONOTONICITY MECHANISM, not the trials themselves.
"""
import numpy as np, collections, warnings, itertools
warnings.filterwarnings("ignore")
from onco_claimtest import simulate_cohort, analyse, DIMNAMES, BAND, TAU_MEANINGFUL

BATCH2 = [
 # label                                    true_hr   n    cens  rule
 ("IMpower010 OS ITT",                       0.995,  1005, 0.75, "directional"),
 ("KEYNOTE-091 DFS ITT",                     0.76,   1177, 0.60, "threshold"),
 ("KEYNOTE-091 DFS PD-L1>=50%",              0.82,    333, 0.65, "threshold"),
 ("IMpower010 OS PD-L1 TC>=1%",              0.71,    476, 0.75, "interval"),
 ("IMpower010 OS PD-L1 TC>=50%",             0.43,    229, 0.75, "interval"),
]
NSEED = 4

def boundary_gap(hr, rule):
    if rule=="directional": return hr-1.0
    if rule=="threshold":   return hr-TAU_MEANINGFUL
    if BAND[0] <= hr <= BAND[1]: return 0.0
    return min(abs(hr-BAND[0]), abs(hr-BAND[1])) * (1 if hr>BAND[1] else -1)

if __name__=="__main__":
    print("="*100)
    print("BATCH 2 — BOUNDARY-PROXIMATE SETTINGS  (simulated cohorts calibrated to published HRs)")
    print("="*100)
    res={}
    for lab,hr0,n,cens,rule in BATCH2:
        runs=[]
        for seed in range(1,NSEED+1):
            df=simulate_cohort(hr0,n,cens,seed)
            o=analyse(df,rule)
            if o: runs.append(o)
        res[lab]=(runs,hr0,rule)

    print(f"\n{'setting':<30}{'rule':<12}{'HR':>7}{'gap':>7}{'S':>7}{'comps':>10}{'split':>7}{'L1 min':>8}{'L1 med':>8}")
    for lab,hr0,n,cens,rule in BATCH2:
        runs,_,_=res[lab]
        if not runs: print(f"{lab:<30} no executable routes"); continue
        S=np.mean([r['S'] for r in runs])
        nc=[len(r['comps']) if r['comps'] else 0 for r in runs]
        splits=sum(1 for x in nc if x>1)
        L=[x for r in runs for x in r['L1'].values() if not np.isnan(x)]
        print(f"{lab:<30}{rule:<12}{hr0:>7.2f}{boundary_gap(hr0,rule):>+7.2f}{S:>7.2f}"
              f"{f'{min(nc)}-{max(nc)}':>10}{f'{splits}/{len(runs)}':>7}{np.min(L):>8.2f}{np.median(L):>8.2f}")

    print("\n--- component sizes per seed (separated support regions) ---")
    for lab,_,_,_,_ in BATCH2:
        runs,_,_=res[lab]
        print(f"  {lab:<30} {[r['comps'] for r in runs]}")

    print("\n--- D_j : which analytic dimension drives disagreement ---")
    print(f"  {'setting':<30}" + "".join(f"{d:>11}" for d in DIMNAMES))
    for lab,_,_,_,_ in BATCH2:
        runs,_,_=res[lab]
        if not runs: continue
        print(f"  {lab:<30}" + "".join(f"{np.nanmean([r['D'][d] for r in runs]):>11.3f}" for d in DIMNAMES))

    print("\n--- HR range across the 108-route lattice (how far analytic choice moves the estimate) ---")
    for lab,hr0,_,_,_ in BATCH2:
        runs,_,_=res[lab]
        if not runs: continue
        lo=min(r['hr_rng'][0] for r in runs); hi=max(r['hr_rng'][1] for r in runs)
        print(f"  {lab:<30} published {hr0:.2f}  ->  routes span {lo:.2f} - {hi:.2f}")
