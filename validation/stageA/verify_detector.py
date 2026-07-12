"""Two clean tests:
(A) Does Output 6 correctly COUNT components given a KNOWN sign field?  (validates the measure)
(B) What sign fields actually produce islands?  (validates what Output 6 detects)
"""
import networkx as nx, numpy as np
from itertools import product

# 4 dimensions, sizes 3x3x3x3 = 81 routes, Hamming-1 lattice
dims=[range(3)]*4
nodes=list(product(*dims))
G=nx.Graph(); G.add_nodes_from(nodes)
for a in nodes:
    for b in nodes:
        if a<b and sum(x!=y for x,y in zip(a,b))==1: G.add_edge(a,b)

def comps(supp):
    pos=[n for n in nodes if supp(n)]
    return sorted([len(c) for c in nx.connected_components(G.subgraph(pos))],reverse=True)

# --- field 1: one dominant dimension drives sign (typical single-mechanism flip)
f_contig = lambda n: n[0] <= 1                     # + on a contiguous slab
# --- field 2: threshold on a sum (typical confounding-strength flip)
f_thresh = lambda n: sum(n) <= 4
# --- field 3: parity / XOR on two dims (pathological)
f_parity = lambda n: (n[0]+n[1]) % 2 == 0
# --- field 4: parity on all four dims (maximally pathological)
f_par4  = lambda n: sum(n) % 2 == 0

for name,f in [("contiguous slab",f_contig),("sum threshold",f_thresh),
               ("XOR on 2 dims",f_parity),("parity on 4 dims",f_par4)]:
    c=comps(f)
    print(f"{name:20s}: +routes={sum(f(n) for n in nodes):2d}  components={len(c):2d}  sizes={c[:6]}{'...' if len(c)>6 else ''}")
