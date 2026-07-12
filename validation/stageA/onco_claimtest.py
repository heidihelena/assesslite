"""
AssessLite — Thoracic oncology claim-structure test (Stage A-bis, NOT Stage B).

WHAT THIS IS:
  Tests the monotonicity mechanism (does claim-rule monotonicity predict separated
  support regions?) on SIMULATED survival cohorts calibrated to PUBLISHED effect sizes
  from three real settings. No trial IPD is used and none is claimed.

  Neoadjuvant  CheckMate 816   EFS HR 0.63 (97.38% CI 0.43-0.91)   -> DIRECTIONAL claim  HR<1
  First-line   KEYNOTE-189     OS  HR 0.56 (0.46-0.69)             -> THRESHOLD claim    HR<0.80
  Adjuvant     ADAURA          DFS HR 0.20 ; OS HR 0.49            -> INTERVAL claim     0.50<=HR<=0.80

  The interval claim is the real live question in the adjuvant setting: is the DFS effect
  clinically meaningful AND plausible as an OS surrogate, or so extreme it suggests
  surrogate inflation? That is a BAND, not a one-sided rule.

  The claim rules below are ILLUSTRATIVE reconstructions, not the trials' registered
  analyses. They are declared a priori and are exogenous (fixed HR thresholds, scale-free).

ROUTE LATTICE — real thoracic-oncology analytic choices (4 dims):
  eligibility : all | ECOG 0-1 only | exclude stage IB
  adjustment  : none | age+sex | age+sex+stage | age+sex+stage+PD-L1
  missing     : complete-case | missing-indicator | mean-impute   (PD-L1 is MNAR-ish)
  model       : Cox PH | Cox stratified by stage | Weibull AFT (converted to HR scale)

Effect measure: hazard ratio for treatment (scale-free, comparable across all three models).
"""
import numpy as np, pandas as pd, networkx as nx, itertools, collections, warnings
warnings.filterwarnings("ignore")
from lifelines import CoxPHFitter, WeibullAFTFitter

# ---------------- published calibration targets ----------------
SETTINGS = {
    "neoadjuvant (CM816-like)": dict(true_hr=0.63, n=350,  cens=0.55, rule="directional"),
    "first-line (KN189-like)" : dict(true_hr=0.56, n=616,  cens=0.35, rule="threshold"),
    "adjuvant  (ADAURA-like)" : dict(true_hr=0.20, n=682,  cens=0.70, rule="interval"),
}
TAU_MEANINGFUL = 0.80     # one-sided clinically meaningful benefit threshold
BAND = (0.50, 0.80)       # interval claim: meaningful AND plausible-as-surrogate

# ---------------- cohort simulation ----------------
def simulate_cohort(true_hr, n, cens, seed):
    rng = np.random.default_rng(seed)
    age   = rng.normal(66, 9, n)
    sex   = rng.binomial(1, 0.45, n)
    stage = rng.choice([1,2,3], n, p=[0.30,0.40,0.30])          # IB / II / IIIA
    ecog  = rng.binomial(1, 0.25, n)                            # 1 = ECOG >=2
    pdl1  = rng.normal(30, 25, n).clip(0,100)                   # PD-L1 TPS %
    trt   = rng.binomial(1, 0.5, n)
    # hazard: treatment effect modified by PD-L1 (real biology: IO works better PD-L1 high)
    lp = (np.log(true_hr)*trt
          + 0.30*(stage-2) + 0.02*(age-66) + 0.15*sex + 0.55*ecog
          - 0.004*(pdl1-30)
          + trt*(-0.008)*(pdl1-30))                             # effect modification
    lam = 0.03*np.exp(lp)
    t   = rng.exponential(1/lam)
    c   = rng.exponential(1/(0.03*cens/(1-cens+1e-9)))          # censoring
    time = np.minimum(t, c); event = (t<=c).astype(int)
    df = pd.DataFrame(dict(time=time.clip(0.1,120), event=event, trt=trt, age=age,
                           sex=sex, stage=stage, ecog=ecog, pdl1=pdl1))
    # PD-L1 missing, more often in ECOG>=2 and stage IB (realistic: less tissue / less tested)
    miss = rng.binomial(1, 0.15 + 0.15*ecog + 0.10*(stage==1), n).astype(bool)
    df["pdl1_obs"] = df["pdl1"].where(~miss, np.nan)
    return df

# ---------------- route lattice ----------------
DIMS = {
  "elig":   ["all", "ecog01", "excl_IB"],
  "adjust": ["none", "age_sex", "age_sex_stage", "age_sex_stage_pdl1"],
  "missing":["complete", "indicator", "mean"],
  "model":  ["cox", "cox_strat", "weibull_aft"],
}
DIMNAMES = list(DIMS)

def hr_for_route(df, r):
    d = df.copy()
    # missing-data strategy for PD-L1
    if r["missing"]=="complete":
        if r["adjust"]=="age_sex_stage_pdl1": d = d.dropna(subset=["pdl1_obs"])
        d["pdl1_c"]=d["pdl1_obs"].fillna(d["pdl1_obs"].mean())
    elif r["missing"]=="mean":
        d["pdl1_c"]=d["pdl1_obs"].fillna(d["pdl1_obs"].mean())
    else:
        d["pdl1_miss"]=d["pdl1_obs"].isna().astype(float)
        d["pdl1_c"]=d["pdl1_obs"].fillna(d["pdl1_obs"].mean())
    # eligibility
    if r["elig"]=="ecog01":  d = d[d.ecog==0]
    elif r["elig"]=="excl_IB": d = d[d.stage>1]
    if len(d)<80 or d.event.sum()<20 or d.trt.nunique()<2: return None
    # adjustment set
    cov=["trt"]
    if r["adjust"] in ("age_sex","age_sex_stage","age_sex_stage_pdl1"): cov += ["age","sex"]
    if r["adjust"] in ("age_sex_stage","age_sex_stage_pdl1"): cov += ["stage"]
    if r["adjust"]=="age_sex_stage_pdl1": cov += ["pdl1_c"]
    if r["missing"]=="indicator" and "pdl1_miss" in d and r["adjust"]=="age_sex_stage_pdl1":
        cov += ["pdl1_miss"]
    cols = cov+["time","event"]
    if r["model"]=="cox_strat" and "stage" in cov: cols=[c for c in cols if c!="stage"]
    dd = d[list(dict.fromkeys(cols))].dropna()
    if dd["trt"].nunique()<2 or dd["event"].sum()<15: return None
    try:
        if r["model"]=="cox":
            m=CoxPHFitter(penalizer=0.01).fit(dd,"time","event"); return float(np.exp(m.params_["trt"]))
        if r["model"]=="cox_strat":
            dd2=dd.copy(); dd2["stage"]=d.loc[dd.index,"stage"]
            m=CoxPHFitter(penalizer=0.01).fit(dd2,"time","event",strata=["stage"])
            return float(np.exp(m.params_["trt"]))
        if r["model"]=="weibull_aft":
            m=WeibullAFTFitter(penalizer=0.01).fit(dd,"time","event")
            b=m.params_[("lambda_","trt")]; rho=np.exp(m.params_[("rho_","Intercept")])
            return float(np.exp(-b*rho))     # AFT -> HR scale
    except Exception:
        return None
    return None

def lattice(keys):
    G=nx.Graph(); G.add_nodes_from(keys)
    for a,b in itertools.combinations(keys,2):
        if sum(x!=y for x,y in zip(a,b))==1: G.add_edge(a,b)
    return G

def claim(hr, rule):
    if rule=="directional": return hr < 1.0
    if rule=="threshold":   return hr < TAU_MEANINGFUL
    if rule=="interval":    return BAND[0] <= hr <= BAND[1]

def analyse(df, rule):
    routes=[dict(zip(DIMNAMES,c)) for c in itertools.product(*DIMS.values())]
    hr={}
    for r in routes:
        v=hr_for_route(df,r)
        if v is not None and 0.01<v<20: hr[tuple(r[k] for k in DIMNAMES)]=v
    if len(hr)<20: return None
    keys=list(hr); G=lattice(keys)
    supp={k:claim(hr[k],rule) for k in keys}
    pos=[k for k in keys if supp[k]]
    comps=sorted([len(c) for c in nx.connected_components(G.subgraph(pos))],reverse=True) if pos else []
    L1={n:(np.mean([supp[m]==supp[n] for m in G.neighbors(n)]) if G.degree(n) else np.nan) for n in keys}
    D={DIMNAMES[j]: np.nanmean([1-np.mean([supp[m]==supp[n] for m in G.neighbors(n) if n[j]!=m[j]])
        if any(n[j]!=m[j] for m in G.neighbors(n)) else np.nan for n in keys]) for j in range(4)}
    return dict(n=len(keys), hr=hr, S=np.mean(list(supp.values())), comps=comps,
                L1=L1, D=D, hr_rng=(min(hr.values()),max(hr.values())))

if __name__=="__main__":
    print("="*84)
    print("THORACIC ONCOLOGY CLAIM-STRUCTURE TEST — 10 seeds per setting")
    print("Simulated cohorts calibrated to published HRs. No trial IPD used.")
    print("="*84)
    store=collections.defaultdict(list)
    for name,cfg in SETTINGS.items():
        for seed in range(1,11):
            df=simulate_cohort(cfg["true_hr"],cfg["n"],cfg["cens"],seed)
            o=analyse(df,cfg["rule"])
            if o: store[name].append(o)
    print(f"\n{'setting':<26}{'rule':<13}{'routes':>7}{'HR range':>16}{'S':>7}{'components':>26}")
    for name,cfg in SETTINGS.items():
        rs=store[name]
        if not rs: print(f"{name:<26} no executable routes"); continue
        nc=[len(r['comps']) for r in rs]
        cs=[r['comps'] for r in rs]
        lo=min(r['hr_rng'][0] for r in rs); hi=max(r['hr_rng'][1] for r in rs)
        print(f"{name:<26}{cfg['rule']:<13}{np.mean([r['n'] for r in rs]):>7.0f}"
              f"{f'{lo:.2f}-{hi:.2f}':>16}{np.mean([r['S'] for r in rs]):>7.2f}"
              f"{f'{min(nc)}-{max(nc)}  (split in {sum(1 for x in nc if x>1)}/10)':>26}")
    print("\n--- component sizes, per seed ---")
    for name in SETTINGS:
        print(f"  {name}: {[r['comps'] for r in store[name]][:10]}")
    print("\n--- D_j : which analytic dimension drives disagreement (mean over seeds) ---")
    print(f"  {'setting':<26}" + "".join(f"{d:>12}" for d in DIMNAMES))
    for name in SETTINGS:
        rs=store[name]
        if not rs: continue
        print(f"  {name:<26}" + "".join(f"{np.nanmean([r['D'][d] for r in rs]):>12.3f}" for d in DIMNAMES))
    print("\n--- L1 spread among claim-supporting routes (local stability hidden by global S) ---")
    for name in SETTINGS:
        rs=store[name]
        if not rs: continue
        v=[x for r in rs for x in r['L1'].values() if not np.isnan(x)]
        print(f"  {name:<26} L1 min={np.min(v):.2f}  median={np.median(v):.2f}  max={np.max(v):.2f}")
