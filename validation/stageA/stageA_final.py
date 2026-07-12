"""Stage A final run.
 1. Connectedness across THREE claim-rule families on the SAME executed lattice:
    directional (sign), exogenous thresholds, BINNED INTERVAL classes.
 2. Gamma matrix: pairwise Spearman of L1 rankings across protocols (not a mean).
 3. Resolution ratio R, per protocol pair family.
 4. Revised Output 5: D_j(x) = dimension-specific neighbour disagreement (no shortest paths).
All rules EXOGENOUS on a scale-free standardized effect. 10 seeds x 3 regimes.
"""
import numpy as np, pandas as pd, statsmodels.api as sm, networkx as nx, itertools, collections, warnings
warnings.filterwarnings("ignore")
from scipy.stats import spearmanr
from assesslite_stageA import simulate, build_design, DIMS, enumerate_routes, route_key

ROUTES=enumerate_routes(); DIMNAMES=list(DIMS)

def fit_std(df,route):
    d,cols=build_design(df,route)
    if d is None: return None
    Xd=sm.add_constant(d[cols],has_constant="add"); y=d["Y"].values
    try:
        if route["model"]=="ols": yy=y; b=sm.OLS(yy,Xd).fit().params["X"]
        elif route["model"]=="logit_median":
            yy=(y>np.median(y)).astype(float); b=sm.Logit(yy,Xd).fit(disp=0).params["X"]
        else:
            yy=pd.Series(y).rank().values; b=sm.OLS(yy,Xd).fit().params["X"]
        sx=d["X"].std(); sy=np.std(yy)
        if sx==0 or sy==0: return None
        return float(b*sx/sy)
    except Exception: return None

def lattice(keys):
    G=nx.Graph(); G.add_nodes_from(keys)
    for a,b in itertools.combinations(keys,2):
        if sum(x!=y for x,y in zip(a,b))==1: G.add_edge(a,b)
    return G

# ---- claim-rule families (ALL exogenous, fixed a priori) ----
BINS=[-np.inf,-0.10,0.0,0.10,0.25,np.inf]   # declared substantive bins on standardized effect
BINLAB=["strong neg","weak neg","null-ish +","small +","moderate +"]
def rule_sets(th,keys):
    R={}
    R["directional: sign>0"]      = {k: (th[k]>0) for k in keys}
    for t in (0.05,0.10,0.15):
        R[f"threshold: b>{t:.2f}"] = {k:(th[k]>t) for k in keys}
    # binned interval: claim = membership of the bin containing the MOST routes (the modal claim class)
    binof={k:int(np.digitize(th[k],BINS)-1) for k in keys}
    modal=collections.Counter(binof.values()).most_common(1)[0][0]
    R[f"binned: class='{BINLAB[modal]}'"] = {k:(binof[k]==modal) for k in keys}
    return R, binof

def L1(G,s,keys):
    return np.array([(np.mean([s[m]==s[n] for m in G.neighbors(n)]) if G.degree(n) else np.nan) for n in keys])
def ncomp(G,s,keys):
    pos=[k for k in keys if s[k]]
    return (len(list(nx.connected_components(G.subgraph(pos)))), sorted([len(c) for c in nx.connected_components(G.subgraph(pos))],reverse=True)) if pos else (0,[])
def Dj(G,s,keys,j):
    """dimension-specific neighbour disagreement (revised Output 5), uniform w"""
    out={}
    for n in keys:
        nb=[m for m in G.neighbors(n) if n[j]!=m[j]]   # one-step changes in dimension j only
        out[n]= (1-np.mean([s[m]==s[n] for m in nb])) if nb else np.nan
    return out

def one(seed,knob):
    df=simulate(islands_strength=knob,seed=seed)
    th={}
    for r in ROUTES:
        v=fit_std(df,r)
        if v is not None: th[route_key(r)]=v
    keys=list(th)
    if len(keys)<20: return None
    G=lattice(keys); R,binof=rule_sets(th,keys)
    names=list(R)
    comps={n:ncomp(G,R[n],keys) for n in names}
    mat=np.column_stack([L1(G,R[n],keys) for n in names])
    ok=~np.isnan(mat).any(axis=1); M=mat[ok]
    # Gamma matrix
    m=len(names); Gam=np.full((m,m),np.nan)
    for i,j in itertools.combinations(range(m),2):
        if M[:,i].std()>0 and M[:,j].std()>0:
            Gam[i,j]=Gam[j,i]=spearmanr(M[:,i],M[:,j]).correlation
    np.fill_diagonal(Gam,1.0)
    sig=M.mean(axis=1).std(); ins=M.std(axis=1).mean()
    # D_j under the directional rule
    D={DIMNAMES[j]: np.nanmean(list(Dj(G,R["directional: sign>0"],keys,j).values())) for j in range(len(DIMNAMES))}
    return dict(names=names, comps=comps, Gam=Gam, R=(sig/ins if ins>1e-9 else np.nan), D=D,
                S={n:np.mean(list(R[n].values())) for n in names}, keys=keys, G=G, th=th)

# ---------- run ----------
print("="*78)
print("1. CONNECTEDNESS ACROSS CLAIM-RULE FAMILIES (10 seeds x 3 regimes)")
print("="*78)
allc=collections.defaultdict(list); Gams=collections.defaultdict(list); Rs=collections.defaultdict(list); Ds=collections.defaultdict(list)
demo=None
for lab,knob in [("ONE-REG",0.0),("MID",1.6),("STRONG",2.6)]:
    for seed in range(1,11):
        o=one(seed,knob)
        if o is None: continue
        if demo is None and lab=="MID": demo=o
        for n in o['names']: allc[(lab,n)].append(o['comps'][n][0])
        Gams[lab].append(o['Gam']); Rs[lab].append(o['R']); Ds[lab].append(o['D'])
names=demo['names']
print(f"{'regime':<9}{'claim rule':<26}{'mean S':>8}{'components (min-max over seeds)':>34}")
for lab in ["ONE-REG","MID","STRONG"]:
    for n in names:
        c=allc[(lab,n)]
        if not c: continue
        print(f"{lab:<9}{n:<26}{'':>8}{f'{min(c)} - {max(c)}':>34}")
    print()

print("="*78)
print("2. GAMMA MATRIX — pairwise Spearman of L1 rankings across claim rules (MID, mean of 10 seeds)")
print("="*78)
Gm=np.nanmean(np.stack(Gams["MID"]),axis=0)
hdr="".join(f"{n.split(':')[0][:8]:>10}" for n in names)
print(f"{'':<26}{hdr}")
for i,n in enumerate(names):
    print(f"{n:<26}"+"".join(f"{Gm[i,j]:>10.2f}" if not np.isnan(Gm[i,j]) else f"{'--':>10}" for j in range(len(names))))

print("\n=== 3. RESOLUTION RATIO R (signal/instrument), by regime ===")
for lab in ["ONE-REG","MID","STRONG"]:
    r=np.array([x for x in Rs[lab] if np.isfinite(x)])
    if len(r)==0: print(f"  {lab:<9} degenerate (all rules agree)"); continue
    print(f"  {lab:<9} R med={np.median(r):.2f} [{r.min():.2f},{r.max():.2f}]  frac R>1 = {np.mean(r>1):.0%}")

print("\n=== 4. REVISED OUTPUT 5 — D_j: which dimension drives disagreement (MID, sign rule) ===")
dd=collections.defaultdict(list)
for d in Ds["MID"]:
    for k,v in d.items(): dd[k].append(v)
for k in DIMNAMES:
    v=np.array(dd[k]); print(f"  D_{k:<8} = {np.nanmean(v):.3f}  (sd {np.nanstd(v):.3f})")
print("  [D_j = fraction of one-step changes in dimension j that flip the claim]")
