"""Replication of the reflexivity finding across SEEDS and DGP regimes.
Q1: does signal/instrument stay < 1?
Q2: does fragility-ranking rank-correlation across claim rules stay low?
Q3: does connectedness (1 component) hold?
"""
import numpy as np, networkx as nx, itertools, collections, warnings
warnings.filterwarnings("ignore")
from scipy.stats import spearmanr
from assesslite_stageA import simulate, fit_route, DIMS, enumerate_routes, route_key

dimnames=list(DIMS); mi=dimnames.index("model")
ROUTES=enumerate_routes()

def one_run(seed, knob):
    theta={}
    df=simulate(islands_strength=knob, seed=seed)
    for r in ROUTES:
        t=fit_route(df,r)
        if t is not None: theta[route_key(r)]=t
    keys=list(theta)
    if len(keys)<20: return None
    # standardize within model family -> commensurable
    byfam=collections.defaultdict(list)
    for k in keys: byfam[k[mi]].append(theta[k])
    mu={f:np.mean(v) for f,v in byfam.items()}; sd={f:(np.std(v) or 1) for f,v in byfam.items()}
    z={k:(theta[k]-mu[k[mi]])/sd[k[mi]] for k in keys}
    G=nx.Graph(); G.add_nodes_from(keys)
    for a,b in itertools.combinations(keys,2):
        if sum(x!=y for x,y in zip(a,b))==1: G.add_edge(a,b)
    rules={"sign":{k:theta[k]>0 for k in keys},
           "z>-0.5":{k:z[k]>-0.5 for k in keys},
           "z>0":{k:z[k]>0 for k in keys},
           "z>+0.5":{k:z[k]>0.5 for k in keys}}
    def L1(s): return np.array([ (np.mean([s[m]==s[n] for m in G.neighbors(n)]) if G.degree(n) else np.nan) for n in keys])
    def ncomp(s):
        pos=[k for k in keys if s[k]]
        return len(list(nx.connected_components(G.subgraph(pos)))) if pos else 0
    mat=np.column_stack([L1(s) for s in rules.values()])
    ok=~np.isnan(mat).any(axis=1); mat=mat[ok]
    if mat.shape[0]<10 or np.allclose(mat.std(axis=1),0) and mat.mean(axis=1).std()==0: return None
    signal=mat.mean(axis=1).std(); instr=mat.std(axis=1).mean()
    rs=[spearmanr(mat[:,i],mat[:,j]).correlation for i,j in itertools.combinations(range(mat.shape[1]),2)]
    comps=[ncomp(s) for s in rules.values()]
    S=[np.mean(list(s.values())) for s in rules.values()]
    return dict(signal=signal, instr=instr,
                ratio=(signal/instr if instr>1e-9 else np.nan),
                corr=np.nanmean(rs), comps_max=max(comps), S_sign=S[0], n=len(keys))

print(f"{'regime':<10}{'seed':>5}{'n':>5}{'S(+)':>7}{'signal':>9}{'instr':>8}{'ratio':>8}{'rankcorr':>10}{'maxcomp':>9}")
rows=collections.defaultdict(list)
for label,knob in [("ONE-REG",0.0),("MID",1.6),("STRONG",2.6)]:
    for seed in range(1,11):
        r=one_run(seed,knob)
        if r is None: 
            print(f"{label:<10}{seed:>5}  (degenerate)"); continue
        rows[label].append(r)
        print(f"{label:<10}{seed:>5}{r['n']:>5}{r['S_sign']:>7.2f}{r['signal']:>9.3f}{r['instr']:>8.3f}"
              f"{r['ratio']:>8.2f}{r['corr']:>10.2f}{r['comps_max']:>9d}")

print("\n=== SUMMARY across seeds ===")
for label,rs in rows.items():
    ratios=np.array([x['ratio'] for x in rs]); corrs=np.array([x['corr'] for x in rs])
    comps=np.array([x['comps_max'] for x in rs])
    ratios_f=ratios[np.isfinite(ratios)]
    print(f"{label:<9} n_seeds={len(rs):2d} | ratio: med={np.median(ratios_f):.2f} "
          f"[{np.min(ratios_f):.2f},{np.max(ratios_f):.2f}]  frac<1 = {np.mean(ratios_f<1):.0%}"
          f" | rankcorr: med={np.nanmedian(corrs):+.2f} [{np.nanmin(corrs):+.2f},{np.nanmax(corrs):+.2f}]"
          f" | any seed with >1 component: {(comps>1).any()}")
