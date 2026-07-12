"""
AssessLite Stage A validation harness.

Goal: test whether Output 6 (connected-component structure of the claim-supporting
subgraph) recovers a PLANTED structure on a simulated cohort, using REAL analytic
choices (adjustment / missingness / population / model) and REAL regression fits.

We are NOT proving usefulness here. We are proving discriminability:
  - Can we manufacture a one-region regime?
  - Can we manufacture a genuine multi-island regime?
  - Does the component count recover what we planted?

Claim rule: directional, sign(theta_hat) > 0  (effect of X on Y is positive).
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import networkx as nx
from itertools import product

# ----------------------------------------------------------------------
# 1. DGP with one knob: `islands_strength`.
#    - At 0: strong additive positive effect of X, no interaction. One region.
#    - Cranked: a suppressor Z and a collider-ish path that, when adjusted under
#      some model families, flips the apparent sign only for INTERMEDIATE
#      specifications -> the +sign region breaks into separated corners.
# ----------------------------------------------------------------------
def simulate(n=4000, islands_strength=0.0, seed=0):
    rng = np.random.default_rng(seed)
    S = rng.binomial(1, 0.5, n)                     # subgroup
    Z = rng.normal(0, 1, n) + 0.8 * S               # confounder, assoc w/ subgroup
    X = rng.binomial(1, 1/(1+np.exp(-(0.9*Z - 0.4))), n)  # exposure depends on Z
    # true positive effect of X, plus a suppressor structure controlled by knob
    base = 0.6 * X                                  # true positive effect
    conf = 0.7 * Z                                  # confounding
    # interaction that flips mid-lattice: effect of X reverses inside subgroup S
    # only when the model is on a scale that lets the sign cross zero
    flip = islands_strength * (X * (2*S - 1)) * 1.5
    Y = base + conf + flip + rng.normal(0, 1.0, n)
    df = pd.DataFrame({"Y": Y, "X": X, "Z": Z, "S": S})
    # inject missingness in Z (so missingness handling is a real choice)
    miss_mask = rng.binomial(1, 0.15 + 0.10*S, n).astype(bool)
    df["Z_obs"] = df["Z"].where(~miss_mask, np.nan)
    return df

# ----------------------------------------------------------------------
# 2. Route lattice: real analytic-choice dimensions.
# ----------------------------------------------------------------------
DIMS = {
    "adjust":   ["none", "Z", "Z+S", "Z+S+ZS"],     # incl. an interaction term
    "miss":     ["complete", "mean", "indicator"],  # missing-data strategy
    "pop":      ["all", "drop_S1", "drop_lowZ"],     # eligibility restriction
    "model":    ["ols", "logit_median", "rank"],     # functional form / estimator
}

def build_design(df, route):
    d = df.copy()
    # --- missingness ---
    if route["miss"] == "complete":
        d = d.dropna(subset=["Z_obs"]).copy(); d["Zc"] = d["Z_obs"]
    elif route["miss"] == "mean":
        d["Zc"] = d["Z_obs"].fillna(d["Z_obs"].mean())
    else:  # indicator
        d["Zmiss"] = d["Z_obs"].isna().astype(float)
        d["Zc"] = d["Z_obs"].fillna(d["Z_obs"].mean())
    # --- population ---
    if route["pop"] == "drop_S1":
        d = d[d["S"] == 0].copy()
    elif route["pop"] == "drop_lowZ":
        d = d[d["Zc"] > d["Zc"].quantile(0.15)].copy()
    if len(d) < 100 or d["X"].nunique() < 2:
        return None, None
    # --- adjustment set ---
    cols = ["X"]
    if route["adjust"] in ("Z", "Z+S", "Z+S+ZS"): cols.append("Zc")
    if route["adjust"] in ("Z+S", "Z+S+ZS"):      cols.append("S")
    if route["adjust"] == "Z+S+ZS":
        d["ZS"] = d["Zc"] * d["S"]; cols.append("ZS")
    if route["miss"] == "indicator" and "Zmiss" in d:
        cols.append("Zmiss")
    return d, cols

def fit_route(df, route):
    d, cols = build_design(df, route)
    if d is None:
        return None
    X = sm.add_constant(d[cols], has_constant="add")
    y = d["Y"].values
    try:
        if route["model"] == "ols":
            theta = sm.OLS(y, X).fit().params["X"]
        elif route["model"] == "logit_median":
            yb = (y > np.median(y)).astype(float)
            theta = sm.Logit(yb, X).fit(disp=0).params["X"]
        else:  # rank: OLS on rank-transformed outcome (a real robust choice)
            yr = pd.Series(y).rank().values
            theta = sm.OLS(yr, X).fit().params["X"]
    except Exception:
        return None
    return float(theta)

# ----------------------------------------------------------------------
# 3. Enumerate routes, compute claim, build graph, Output 6.
# ----------------------------------------------------------------------
def enumerate_routes():
    keys = list(DIMS)
    return [dict(zip(keys, combo)) for combo in product(*DIMS.values())]

def route_key(r):  # hashable
    return tuple(r[k] for k in DIMS)

def run(df):
    routes = enumerate_routes()
    results = {}
    for r in routes:
        theta = fit_route(df, r)
        if theta is not None:
            results[route_key(r)] = theta
    # claim rule: directional, sign>0
    supports = {k: (v > 0) for k, v in results.items()}
    # graph: Hamming-1 edges among executable routes
    G = nx.Graph()
    G.add_nodes_from(results.keys())
    keys = list(results.keys())
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            diff = sum(a != b for a, b in zip(keys[i], keys[j]))
            if diff == 1:
                G.add_edge(keys[i], keys[j])
    # Output 2: global support (unweighted here; uniform pi-tilde)
    S_pos = np.mean(list(supports.values()))
    # Output 6: components of the +supporting subgraph
    pos_nodes = [k for k, s in supports.items() if s]
    Gpos = G.subgraph(pos_nodes)
    comps = sorted([len(c) for c in nx.connected_components(Gpos)], reverse=True)
    return {
        "n_routes": len(results),
        "S_pos": S_pos,
        "pos_component_sizes": comps,
        "n_pos_components": len(comps),
        "supports": supports,
        "results": results,
        "graph": G,
    }

# ----------------------------------------------------------------------
# 4. Three regimes.
# ----------------------------------------------------------------------
if __name__ == "__main__":
    for label, knob in [("ONE-REGION", 0.0), ("MID", 1.6), ("ISLANDS", 2.6)]:
        df = simulate(islands_strength=knob, seed=1)
        out = run(df)
        print(f"\n=== {label} (islands_strength={knob}) ===")
        print(f"executable routes : {out['n_routes']}")
        print(f"S(+)  global supp : {out['S_pos']:.2f}")
        print(f"+ components      : {out['n_pos_components']}  sizes={out['pos_component_sizes']}")
