"""DECISIVE test: exogenous, scale-free claim rules (NOT route-relative).
Effect measure: standardized beta  b_std = beta * sd(X)/sd(Y_used)  -> comparable across
OLS / rank / logit-median fits. Thresholds are fixed scientific values, declared a priori:
  R1 sign>0 ; R2 b_std>0.05 (small) ; R3 b_std>0.10 ; R4 b_std>0.15 (moderate)
None depends on the distribution of results. Replicate across 10 seeds x 3 regimes.
"""
import numpy as np, pandas as pd, statsmodels.api as sm, networkx as nx, itertools, collections, warnings
warnings.filterwarnings("ignore")
from scipy.stats import spearmanr
from assesslite_stageA import simulate, build_design, DIMS, enumerate_routes, route_key

ROUTES=enumerate_routes()
def fit_std(df, route):
    """return standardized beta for X: scale-free, exogenous-threshold-comparable"""
    d,cols=build_design(df,route)
    if d is None: return None
    Xd=sm.add_constant(d[cols],has_constant="add"); y=d["Y"].values
    try:
        if route["model"]=="ols": yy=y
        elif route["model"]=="logit_median": yy=(y>np.median(y)).astype(float)
        else: yy=pd.Series(y).rank().values
        b=sm.OLS(yy,Xd).fit().params["X"] if route["model"]!="logit_median" \
          else sm.Logit(yy,Xd).fit(disp=0).params["X"]
        sx=d["X"].std(); sy=np.std(yy)
        if sy==0 or sx==0: return None
        return float(b*sx/sy)          # standardized effect, scale-free
    except Exception: return None

def one_run(seed,knob):
    df=simulate(islands_strength=knob,seed=seed)
    th={}
    for r in ROUTES:
        v=fit_std(df,r)
        if v is not None: th[route_key(r)]=v
    keys=list(th)
    if len(keys)<20: return None
    G=nx.Graph(); G.add_nodes_from(keys)
    for a,b in itertools.combinations(keys,2):
        if sum(x!=y for x,y in zip(a,b))==1: G.add_edge(a,b)
    rules={"sign>0":0.0,"b>0.05":0.05,"b>0.10":0.10,"b>0.15":0.15}   # EXOGENOUS
    supps={n:{k:th[k]>t for k in keys} for n,t in rules.items()}
    def L1(s): return np.array([(np.mean([s[m]==s[n] for m in G.neighbors(n)]) if G.degree(n) else np.nan) for n in keys])
    def nc(s):
        pos=[k for k in keys if s[k]]
        return len(list(nx.connected_components(G.subgraph(pos)))) if pos else 0
    mat=np.column_stack([L1(s) for s in supps.values()])
    ok=~np.isnan(mat).any(axis=1); mat=mat[ok]
    if mat.shape[0]<10: return None
    signal=mat.mean(axis=1).std(); instr=mat.std(axis=1).mean()
    rs=[spearmanr(mat[:,i],mat[:,j]).correlation for i,j in itertools.combinations(range(mat.shape[1]),2)]
    return dict(ratio=signal/instr if instr>1e-9 else np.nan, corr=np.nanmean(rs),
                maxc=max(nc(s) for s in supps.values()),
                S=[np.mean(list(s.values())) for s in supps.values()],
                brange=(min(th.values()),max(th.values())))

print("EXOGENOUS scale-free rules (standardized beta). ratio<1 => instrument noisier than signal\n")
print(f"{'regime':<9}{'seed':>4}{'b_std range':>18}{'S(sign)':>9}{'S(.15)':>8}{'ratio':>8}{'rankcorr':>10}{'maxcomp':>9}")
agg=collections.defaultdict(list)
for lab,knob in [("ONE-REG",0.0),("MID",1.6),("STRONG",2.6)]:
    for seed in range(1,11):
        r=one_run(seed,knob)
        if r is None: continue
        agg[lab].append(r)
        print(f"{lab:<9}{seed:>4}  [{r['brange'][0]:+.2f},{r['brange'][1]:+.2f}]{r['S'][0]:>9.2f}{r['S'][3]:>8.2f}"
              f"{r['ratio']:>8.2f}{r['corr']:>10.2f}{r['maxc']:>9d}")
print("\n=== SUMMARY (exogenous rules) ===")
for lab,rs in agg.items():
    rt=np.array([x['ratio'] for x in rs]); co=np.array([x['corr'] for x in rs]); mc=np.array([x['maxc'] for x in rs])
    rt=rt[np.isfinite(rt)]
    print(f"{lab:<9} ratio med={np.median(rt):.2f} [{rt.min():.2f},{rt.max():.2f}] frac<1={np.mean(rt<1):.0%} | "
          f"rankcorr med={np.nanmedian(co):+.2f} [{np.nanmin(co):+.2f},{np.nanmax(co):+.2f}] | >1 component ever: {(mc>1).any()}")
