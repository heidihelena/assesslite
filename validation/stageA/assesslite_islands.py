"""
Can a PLAUSIBLE DGP produce genuine islands in the claim-supporting subgraph?

Mechanism: two confounders with opposite-sign bias.
  Z1 is removable only by covariate adjustment.
  Z2's bias is removable only by a rank/robust model (it acts through outcome tails).
Correct BOTH or NEITHER -> unbiased positive effect recovered (+).
Correct exactly ONE -> the other bias dominates -> sign flips (-).
=> XOR over (adjustment, model): the +region should split into two separated corners.
"""
import numpy as np, pandas as pd, statsmodels.api as sm, networkx as nx
from itertools import product

def simulate(n=6000, strength=1.0, seed=1):
    rng = np.random.default_rng(seed)
    Z1 = rng.normal(0, 1, n)                       # linear confounder
    Z2 = rng.normal(0, 1, n)                       # tail confounder
    X  = rng.binomial(1, 1/(1+np.exp(-(0.9*Z1 + 0.9*Z2))), n)
    true = 0.5 * X                                 # true POSITIVE effect
    # Z1 exerts a NEGATIVE-inducing confounding path (removed by adjusting Z1)
    b1 = -strength * 1.3 * Z1
    # Z2 exerts a POSITIVE-inducing path concentrated in the tails
    #   (only a rank/robust fit neutralizes it; linear fit is dominated by it)
    b2 = strength * 1.3 * np.sign(Z2) * (Z2**2)
    Y = true + b1 + b2 + rng.normal(0, 1.0, n)
    return pd.DataFrame({"Y": Y, "X": X, "Z1": Z1, "Z2": Z2})

DIMS = {
    "adjust": ["none", "Z1"],            # correct the linear confounder or not
    "model":  ["ols", "rank"],           # correct the tail confounder or not
    "pop":    ["all", "trim"],           # nuisance dimension (should not flip sign)
    "miss":   ["cc", "mean"],            # nuisance dimension
}

def fit_route(df, r):
    d = df.copy()
    if r["pop"] == "trim":
        lo, hi = d["Y"].quantile([0.02, 0.98]); d = d[(d.Y>lo)&(d.Y<hi)]
    cols = ["X"] + (["Z1"] if r["adjust"] == "Z1" else [])
    Xd = sm.add_constant(d[cols], has_constant="add")
    y = d["Y"].values
    if r["model"] == "ols":
        return float(sm.OLS(y, Xd).fit().params["X"])
    else:
        yr = pd.Series(y).rank().values
        return float(sm.OLS(yr, Xd).fit().params["X"])

def run(df):
    keys_dim = list(DIMS)
    routes = [dict(zip(keys_dim, c)) for c in product(*DIMS.values())]
    res = {tuple(r[k] for k in keys_dim): fit_route(df, r) for r in routes}
    supp = {k: v > 0 for k, v in res.items()}
    G = nx.Graph(); G.add_nodes_from(res)
    ks = list(res)
    for i in range(len(ks)):
        for j in range(i+1, len(ks)):
            if sum(a!=b for a,b in zip(ks[i],ks[j])) == 1:
                G.add_edge(ks[i], ks[j])
    pos = [k for k,s in supp.items() if s]
    comps = sorted([len(c) for c in nx.connected_components(G.subgraph(pos))], reverse=True)
    return res, supp, comps, np.mean(list(supp.values()))

if __name__ == "__main__":
    for label, s in [("ONE-REGION", 0.0), ("ISLANDS?", 1.0)]:
        df = simulate(strength=s, seed=2)
        res, supp, comps, Spos = run(df)
        print(f"\n=== {label} (strength={s}) ===")
        print(f"S(+) = {Spos:.2f}   + components = {len(comps)}  sizes={comps}")
        # show the (adjust,model) sign pattern collapsed over nuisance dims
        print(" sign pattern over (adjust,model), pop=all,miss=cc:")
        for a in DIMS['adjust']:
            row = []
            for m in DIMS['model']:
                v = res[(a, m, 'all', 'cc')]
                row.append(f"{a:>4}/{m:<4}:{'+' if v>0 else '-'}({v:+.2f})")
            print("   " + "   ".join(row))
