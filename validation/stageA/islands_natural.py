"""The binned-interval rule produced 2 components WITHOUT deliberate construction.
Characterise: how often, which bins, what sizes, and is it noise or structure?"""
import numpy as np, networkx as nx, collections, itertools, warnings; warnings.filterwarnings("ignore")
from stageA_final import fit_std, lattice, ROUTES, BINS, BINLAB, DIMNAMES
from assesslite_stageA import simulate, route_key

print("Binned-interval claim classes: bins on standardized effect", BINS[1:-1])
print("Component structure of EVERY bin class (not just modal), 10 seeds x 3 regimes\n")
hit=[]
for lab,knob in [("ONE-REG",0.0),("MID",1.6),("STRONG",2.6)]:
    for seed in range(1,11):
        df=simulate(islands_strength=knob,seed=seed)
        th={}
        for r in ROUTES:
            v=fit_std(df,r)
            if v is not None: th[route_key(r)]=v
        keys=list(th); G=lattice(keys)
        binof={k:int(np.digitize(th[k],BINS)-1) for k in keys}
        for b in sorted(set(binof.values())):
            pos=[k for k in keys if binof[k]==b]
            if len(pos)<2: continue
            cs=sorted([len(c) for c in nx.connected_components(G.subgraph(pos))],reverse=True)
            if len(cs)>1:
                hit.append((lab,seed,BINLAB[b],len(pos),cs))
print(f"{'regime':<9}{'seed':>4}  {'claim class':<14}{'n routes':>9}  component sizes")
for h in hit: print(f"{h[0]:<9}{h[1]:>4}  {h[2]:<14}{h[3]:>9}  {h[4]}")
print(f"\nSEEDS WITH >=1 DISCONNECTED CLAIM CLASS: {len(set((h[0],h[1]) for h in hit))} / 30")
byreg=collections.Counter(h[0] for h in hit)
print("by regime:",dict(byreg))
# Are the islands stable across seeds (structure) or sporadic (noise)?
byclass=collections.Counter(h[2] for h in hit)
print("by claim class:",dict(byclass))
