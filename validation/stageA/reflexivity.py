"""
Three tests:
 T1. Claim-rule sensitivity: is 'route spaces are connected' a fact, or an artifact of sign()?
 T2. Reflexivity: does AssessLite's own answer depend on AssessLite's own choices (encoding, pi-tilde)?
 T3. Resolving power: signal variance (across routes) vs instrument variance (across protocols).
     If instrument >= signal, the measurement is too close to the object.
"""
import numpy as np, pandas as pd, networkx as nx, itertools, collections
from assesslite_stageA import simulate, fit_route, DIMS, enumerate_routes, route_key

df = simulate(islands_strength=1.6, seed=1)
routes = enumerate_routes()
theta = {}
for r in routes:
    t = fit_route(df, r)
    if t is not None: theta[route_key(r)] = t
keys = list(theta); vals = np.array([theta[k] for k in keys])
print("executable routes:", len(keys), " theta range: %.3f .. %.3f" % (vals.min(), vals.max()))

def graph(nodes):
    G = nx.Graph(); G.add_nodes_from(nodes)
    for a,b in itertools.combinations(nodes,2):
        if sum(x!=y for x,y in zip(a,b))==1: G.add_edge(a,b)
    return G
Gfull = graph(keys)

def comps_and_S(supp):
    pos=[k for k in keys if supp[k]]
    if not pos: return 0,[],0.0
    c=sorted([len(x) for x in nx.connected_components(Gfull.subgraph(pos))],reverse=True)
    return len(c), c, len(pos)/len(keys)

# ---------- T1: claim-rule sensitivity ----------
print("\n=== T1  connectedness across CLAIM RULES ===")
q = np.quantile(vals,[.25,.5,.75])
rules = {
 "sign>0"            : lambda t: t>0,
 "threshold t>q25"   : lambda t: t>q[0],
 "threshold t>median": lambda t: t>q[1],
 "threshold t>q75"   : lambda t: t>q[2],
 "interval |t-med|<=d(band)": lambda t: abs(t-q[1])<= (vals.std()*0.5),
}
for name,f in rules.items():
    supp={k:f(theta[k]) for k in keys}
    n,c,S = comps_and_S(supp)
    print(f"  {name:26s} S={S:.2f}  components={n:2d} sizes={c[:5]}")

# ---------- T2 + T3: reflexivity ----------
# The scientific signal AssessLite claims to detect = spread in L1 ACROSS ROUTES (fixed protocol).
# The instrument noise = spread in L1 FOR A GIVEN ROUTE ACROSS PROTOCOLS.
def L1_all(supp, G):
    out={}
    for n in G.nodes():
        nb=list(G.neighbors(n))
        out[n]= np.mean([supp[m]==supp[n] for m in nb]) if nb else np.nan
    return out

# protocol variants = alternative ENCODINGS (drop/merge a dimension) x claim rules
dimnames=list(DIMS)
protocols={}
supp_sign={k:theta[k]>0 for k in keys}
protocols["baseline (4 dims, sign)"]=(Gfull, supp_sign)
# encoding variant: drop each dimension (marginalize) -> lattice on remaining 3 dims
for d in dimnames:
    idx=[i for i,x in enumerate(dimnames) if x!=d]
    proj=collections.defaultdict(list)
    for k in keys: proj[tuple(k[i] for i in idx)].append(theta[k])
    nodes=list(proj); th2={n:np.mean(proj[n]) for n in nodes}
    G2=graph(nodes); s2={n:th2[n]>0 for n in nodes}
    protocols[f"encoding: drop '{d}'"]=(G2,s2)
# claim-rule variant on full lattice
protocols["rule: t>median"]=(Gfull,{k:theta[k]>q[1] for k in keys})

print("\n=== T2  does AssessLite's own answer move with AssessLite's own choices? ===")
rows=[]
for name,(G,supp) in protocols.items():
    L=L1_all(supp,G); v=[x for x in L.values() if not np.isnan(x)]
    pos=[n for n in G.nodes() if supp[n]]
    nc=len(list(nx.connected_components(G.subgraph(pos)))) if pos else 0
    rows.append((name,len(G),np.mean(list(supp.values())),nc,np.mean(v),np.std(v)))
    print(f"  {name:26s} |V|={len(G):3d} S={np.mean(list(supp.values())):.2f} comps={nc} meanL1={np.mean(v):.2f} sdL1={np.std(v):.2f}")

# T3: for routes present in ALL protocols that keep the full lattice, compare variances
common=[p for p in protocols if "encoding" not in p]   # full-lattice protocols only
Ls={p:L1_all(protocols[p][1],protocols[p][0]) for p in common}
mat=np.array([[Ls[p][k] for p in common] for k in keys])  # routes x protocols
signal = mat.mean(axis=1).std()      # spread across ROUTES (what we want to detect)
instr  = mat.std(axis=1).mean()      # spread across PROTOCOLS for same route (noise)
print("\n=== T3  RESOLVING POWER (L1) ===")
print(f"  signal: sd of route-mean L1 across routes      = {signal:.3f}")
print(f"  instrument: mean sd of L1 across protocols     = {instr:.3f}")
print(f"  ratio signal/instrument                        = {signal/instr:.2f}" if instr>0 else "  instrument variance = 0")
# rank stability: does the ORDERING of routes by fragility survive protocol change?
from scipy.stats import spearmanr
if len(common)>1:
    rs=[spearmanr(mat[:,i],mat[:,j]).correlation for i,j in itertools.combinations(range(len(common)),2)]
    print(f"  Spearman rank corr of route fragility across protocols: {np.round(rs,2)}")
