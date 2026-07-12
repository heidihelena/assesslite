import numpy as np, networkx as nx
from assesslite_stageA import simulate, run

df = simulate(islands_strength=1.6, seed=1)   # MID regime: S(+)=0.67, one component
out = run(df); G = out["graph"]; supp = out["supports"]
nodes = list(supp)

def rho(n):  # weighted-unit shortest path to nearest disagreeing route
    tgt = [m for m in nodes if supp[m] != supp[n]]
    if not tgt: return np.inf
    d = nx.multi_source_dijkstra_path_length(G, set(tgt))  # dist from any target
    return d.get(n, np.inf)

def L1(n):
    nb = list(G.neighbors(n))
    if not nb: return np.nan
    return np.mean([supp[m]==supp[n] for m in nb])

pos = [n for n in nodes if supp[n]]                 # routes supporting the claim
rhos = [rho(n) for n in pos]
l1s  = [L1(n)  for n in pos]
import collections
print("among the", len(pos), "claim-supporting routes (global S=0.67):")
print("  rho distribution:", dict(sorted(collections.Counter(rhos).items(), key=lambda x:(x[0]==np.inf,x[0]))))
print("  fraction at rho=1 :", np.mean([r==1 for r in rhos]).round(2))
print("  L1 range          : %.2f .. %.2f" % (np.nanmin(l1s), np.nanmax(l1s)))
print("  # routes with L1<0.5 (neighbors mostly DISAGREE): ", sum(x<0.5 for x in l1s))
# the divergence test: can two supporting routes share global support but differ sharply in local stability?
best = max(pos, key=lambda n:(rho(n), L1(n)))
worst= min(pos, key=lambda n:(rho(n), L1(n)))
print("\n  divergence within identical global S=0.67:")
print("   safest  route: rho=%s L1=%.2f  %s" % (rho(best), L1(best), best))
print("   fragile route: rho=%s L1=%.2f  %s" % (rho(worst),L1(worst),worst))
