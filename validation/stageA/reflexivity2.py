"""Redo T3 with COMMENSURABLE claim rules (per-model-family standardized theta),
which is what spec §1 requires. Then ask again: is the instrument too close to the object?"""
import numpy as np, networkx as nx, itertools, collections
from scipy.stats import spearmanr
from assesslite_stageA import simulate, fit_route, DIMS, enumerate_routes, route_key

df = simulate(islands_strength=1.6, seed=1)
theta={}
for r in enumerate_routes():
    t=fit_route(df,r)
    if t is not None: theta[route_key(r)]=t
keys=list(theta); dimnames=list(DIMS); mi=dimnames.index("model")

# standardize theta WITHIN model family -> commensurable across the lattice
byfam=collections.defaultdict(list)
for k in keys: byfam[k[mi]].append(theta[k])
mu={f:np.mean(v) for f,v in byfam.items()}; sd={f:np.std(v) for f,v in byfam.items()}
z={k:(theta[k]-mu[k[mi]])/sd[k[mi]] for k in keys}   # standardized effect

G=nx.Graph(); G.add_nodes_from(keys)
for a,b in itertools.combinations(keys,2):
    if sum(x!=y for x,y in zip(a,b))==1: G.add_edge(a,b)

def L1(supp):
    return {n:(np.mean([supp[m]==supp[n] for m in G.neighbors(n)]) if G.degree(n) else np.nan) for n in G}
def ncomp(supp):
    pos=[k for k in keys if supp[k]]
    return len(list(nx.connected_components(G.subgraph(pos)))) if pos else 0

# commensurable rules: sign of raw theta (scale-free) + z-thresholds (now comparable)
rules={
 "sign(theta)>0"      : {k:theta[k]>0 for k in keys},
 "z > -0.5"           : {k:z[k]>-0.5 for k in keys},
 "z > 0"              : {k:z[k]>0    for k in keys},
 "z > +0.5"           : {k:z[k]>0.5  for k in keys},
}
print("=== T1b  connectedness under COMMENSURABLE rules ===")
for n,s in rules.items():
    print(f"  {n:14s} S={np.mean(list(s.values())):.2f}  components={ncomp(s)}")

mat=np.array([[L1(s)[k] for s in rules.values()] for k in keys])
signal=mat.mean(axis=1).std(); instr=mat.std(axis=1).mean()
print(f"\n=== T3b  RESOLVING POWER (commensurable rules) ===")
print(f"  signal (sd of route-mean L1 across routes) = {signal:.3f}")
print(f"  instrument (mean sd of L1 across rules)    = {instr:.3f}")
print(f"  ratio                                      = {signal/instr:.2f}")
rs=[spearmanr(mat[:,i],mat[:,j]).correlation for i,j in itertools.combinations(range(mat.shape[1]),2)]
print(f"  pairwise Spearman of fragility ranking     = {np.round(rs,2)}  (mean {np.nanmean(rs):.2f})")

# separate the two sources: rule-change vs encoding-change, holding the other fixed
print("\n=== which protocol knob does the damage? ===")
# (a) vary rule only, fixed encoding  -> above
print(f"  vary CLAIM RULE only : mean rank corr = {np.nanmean(rs):.2f}")
# (b) vary encoding only, fixed rule (sign): drop one dim, compare L1 on surviving routes
base=L1(rules["sign(theta)>0"])
cors=[]
for d in dimnames:
    idx=[i for i,x in enumerate(dimnames) if x!=d]
    proj=collections.defaultdict(list)
    for k in keys: proj[tuple(k[i] for i in idx)].append(theta[k])
    nodes=list(proj); th2={n:np.mean(proj[n]) for n in nodes}
    G2=nx.Graph(); G2.add_nodes_from(nodes)
    for a,b in itertools.combinations(nodes,2):
        if sum(x!=y for x,y in zip(a,b))==1: G2.add_edge(a,b)
    s2={n:th2[n]>0 for n in nodes}
    L2={n:(np.mean([s2[m]==s2[n] for m in G2.neighbors(n)]) if G2.degree(n) else np.nan) for n in G2}
    # map each full route to its projection, compare
    x=[base[k] for k in keys]; y=[L2[tuple(k[i] for i in idx)] for k in keys]
    c=spearmanr(x,y).correlation; cors.append(c)
    print(f"  drop '{d:6s}' vs baseline : rank corr = {c:+.2f}")
print(f"  vary ENCODING only   : mean rank corr = {np.nanmean(cors):+.2f}")
