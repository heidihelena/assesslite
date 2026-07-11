"""Causal-graph check (AssessLite core spec v0.2, spec/graph/graph-check.md).

Declares a DAG, derives its implied conditional independencies (ordered local
Markov), and tests each against the data by partial correlation. Self-contained
numpy/pandas; no external graph package. Kept identical to the R engine.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

_COLS = ["label", "estimate", "se", "ci_low", "ci_high", "n"]


def parse_graph(edges) -> dict:
    """Parse edges like 'age -> adherence' into nodes, a parents map, and a topological order."""
    if not edges:
        raise ValueError("declare_graph needs at least one edge like 'a -> b'")
    frm, to = [], []
    for e in edges:
        parts = [p.strip() for p in str(e).split("->")]
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"edge '{e}' is not of the form 'a -> b'")
        frm.append(parts[0]); to.append(parts[1])
    nodes = list(dict.fromkeys(frm + to))
    parents = {v: list(dict.fromkeys(f for f, t in zip(frm, to) if t == v)) for v in nodes}
    placed, remaining = [], list(nodes)
    while remaining:
        ready = [v for v in remaining if all(p in placed for p in parents[v])]
        if not ready:
            raise ValueError("the declared graph is not acyclic")
        placed += ready
        remaining = [v for v in remaining if v not in ready]
    return {"edges": list(edges), "nodes": nodes, "parents": parents, "order": placed}


def coerce_numeric(x: pd.Series):
    """Coerce to a single numeric column, or None if a multi-level categorical."""
    if pd.api.types.is_bool_dtype(x):
        return x.astype(float).to_numpy()
    if pd.api.types.is_numeric_dtype(x) and not isinstance(x.dtype, pd.CategoricalDtype):
        return x.astype(float).to_numpy()
    u = sorted(pd.unique(x.dropna().astype(str)))
    if len(u) == 2:
        return x.astype(str).map({u[0]: 0.0, u[1]: 1.0}).to_numpy()
    return None


def _design(Zdf: pd.DataFrame) -> np.ndarray:
    blocks = [np.ones((len(Zdf), 1))]
    for c in Zdf.columns:
        s = Zdf[c]
        if isinstance(s.dtype, pd.CategoricalDtype) or not pd.api.types.is_numeric_dtype(s):
            d = pd.get_dummies(s, prefix=c, drop_first=True)
            if d.shape[1] > 0:
                blocks.append(d.to_numpy(dtype=float))
        else:
            blocks.append(s.to_numpy(dtype=float).reshape(-1, 1))
    return np.hstack(blocks)


def partial_cor(v: np.ndarray, w: np.ndarray, Zdf):
    if Zdf is None or Zdf.shape[1] == 0:
        rv = v - v.mean(); rw = w - w.mean(); k = 0
    else:
        X = _design(Zdf)
        bv, _, rank, _ = np.linalg.lstsq(X, v, rcond=None)
        bw, _, _, _ = np.linalg.lstsq(X, w, rcond=None)
        rv = v - X @ bv; rw = w - X @ bw
        k = int(rank) - 1
    n = len(v)
    denom = rv.std() * rw.std()
    r = float(np.corrcoef(rv, rw)[0, 1]) if denom > 0 else 0.0
    return r, n, k


def test_graph_check(assessment, alpha: float = 0.05, effect_floor: float = 0.1) -> dict:
    g = assessment.graph
    if g is None:
        raise ValueError("graph_check needs a declared graph; call declare_graph() first")
    d = assessment.data
    order, parents = g["order"], g["parents"]
    latent = set(g.get("latent", []))

    def observed(v):
        return v not in latent and v in d.columns

    imps = []

    for i, V in enumerate(order):
        preds = order[:i]
        par = parents[V]
        for W in [p for p in preds if p not in par]:
            cond = list(par)
            claim = "{} _||_ {} | {{{}}}".format(V, W, ", ".join(cond))
            # testable only if both endpoints and every conditioning node are observed
            testable = observed(V) and observed(W) and all(observed(c) for c in cond)
            vv = coerce_numeric(d[V]) if testable else None
            ww = coerce_numeric(d[W]) if testable else None
            if vv is None or ww is None:
                imps.append({"claim": claim, "conditioning": cond, "partial_r": None,
                             "p_value": None, "n": None, "status": "not_testable"})
                continue
            # complete cases across v, w, and conditioning columns
            frame = pd.DataFrame({"__v": vv, "__w": ww})
            Z = d[cond].reset_index(drop=True) if cond else None
            mask = frame.notna().all(axis=1)
            if Z is not None:
                mask = mask & Z.notna().all(axis=1)
            vvc = frame["__v"][mask].to_numpy()
            wwc = frame["__w"][mask].to_numpy()
            Zc = Z[mask].reset_index(drop=True) if Z is not None else None
            r, n, k = partial_cor(vvc, wwc, Zc)
            dfree = n - k - 3
            if not math.isfinite(r) or dfree < 1:
                status, p = "not_resolvable", None
            else:
                rc = max(min(r, 1 - 1e-12), -1 + 1e-12)
                z = math.atanh(rc) * math.sqrt(dfree)
                p = math.erfc(abs(z) / math.sqrt(2))
                mds = math.tanh(1.96 / math.sqrt(dfree))
                status = ("violated" if (p < alpha and abs(r) >= effect_floor)
                          else "not_resolvable" if mds > effect_floor else "consistent")
            imps.append({"claim": claim, "conditioning": cond, "partial_r": round(r, 4),
                         "p_value": None if p is None else round(p, 4), "n": int(n), "status": status})

    statuses = [im["status"] for im in imps]
    n_testable = sum(s != "not_testable" for s in statuses)
    if any(s == "violated" for s in statuses):
        verdict = "unstable"
    elif n_testable == 0 or any(s == "not_resolvable" for s in statuses):
        verdict = "not_resolvable"
    else:
        verdict = "stable"

    n_viol = sum(s == "violated" for s in statuses)
    if verdict == "unstable":
        first = next(im["claim"] for im in imps if im["status"] == "violated")
        reading = (f"the data contradict {n_viol} of the graph's {n_testable} implied independencies "
                   f"(e.g. {first}), so the declared causal graph does not hold up (partial-correlation "
                   f"test, a linear approximation to conditional independence)")
    elif verdict == "not_resolvable":
        reading = ("none of the graph's implied independencies were testable at this n (endpoints were "
                   "multi-level categoricals); the graph is not resolvable against this data"
                   if n_testable == 0 else
                   f"no implied independence was contradicted, but at least one of the {n_testable} "
                   f"testable implications was underpowered; the graph is not fully resolvable at this n")
    else:
        reading = (f"every one of the {n_testable} testable implied independencies is consistent with the "
                   f"data (partial-correlation test); the data do not contradict the declared graph. This "
                   f"does not establish the graph — Markov-equivalent graphs share these implications")

    return {"test": "graph_check", "invariance": "causal_graph", "verdict": verdict,
            "metrics": None, "implications": imps,
            "variants": pd.DataFrame(columns=_COLS), "n_failed": 0, "reading": reading}


# --- d-separation and the backdoor criterion (core spec v0.2, spec/graph/adjustment.md) ---

def _children_of(parents: dict) -> dict:
    ch = {v: [] for v in parents}
    for v, ps in parents.items():
        for p in ps:
            ch[p].append(v)
    return ch


def ancestors_of(parents: dict, S) -> set:
    seen, stack = set(), list(S)
    while stack:
        v = stack.pop()
        if v in seen:
            continue
        seen.add(v)
        stack.extend(parents.get(v, []))
    return seen


def descendants_of(parents: dict, node: str) -> set:
    ch = _children_of(parents)
    seen, stack = set(), list(ch.get(node, []))
    while stack:
        v = stack.pop()
        if v in seen:
            continue
        seen.add(v)
        stack.extend(ch.get(v, []))
    return seen


def d_separated(parents: dict, X: str, Y: str, Z) -> bool:
    """Moralised ancestral graph test: are X and Y d-separated given Z?"""
    Z = set(Z)
    A = ancestors_of(parents, {X, Y} | Z)
    adj = {v: set() for v in A}

    def link(a, b):
        adj[a].add(b); adj[b].add(a)

    for v in A:
        pv = [p for p in parents.get(v, []) if p in A]
        for p in pv:
            link(v, p)
        for i in range(len(pv)):
            for j in range(i + 1, len(pv)):
                link(pv[i], pv[j])
    keep = A - Z
    if X not in keep or Y not in keep:
        return True
    seen, stack = set(), [X]
    while stack:
        v = stack.pop()
        if v in seen:
            continue
        seen.add(v)
        stack.extend(n for n in adj[v] if n in keep)
    return Y not in seen


def backdoor_valid(parents: dict, X: str, Y: str, Z) -> bool:
    Z = list(Z)
    if set(Z) & descendants_of(parents, X):
        return False
    pxbar = {v: [p for p in ps if p != X] for v, ps in parents.items()}
    return d_separated(pxbar, X, Y, Z)


def test_adjustment_check(assessment, outcome_node=None) -> dict:
    g = assessment.graph
    if g is None:
        raise ValueError("adjustment_check needs a declared graph; call declare_graph() first")
    parents = g["parents"]
    X = assessment.analysis["exposure"]
    oc = assessment.analysis["outcome_cols"]
    if outcome_node is None:
        cand = [oc[1], oc[0]] if len(oc) == 2 else [oc[0]]
        outcome_node = next((c for c in cand if c in g["nodes"]), None)
    Y = outcome_node
    adjusted = list(assessment.analysis["covariates"])
    empty = pd.DataFrame(columns=_COLS)

    def mk(verdict, reading, adj):
        return {"test": "adjustment_check", "invariance": "adjustment_sufficiency",
                "verdict": verdict, "metrics": None, "adjustment": adj,
                "variants": empty, "n_failed": 0, "reading": reading}

    if Y is None or X not in g["nodes"] or Y not in g["nodes"]:
        return mk("not_resolvable",
                  f"cannot check the adjustment set: exposure '{X}' or outcome "
                  f"'{Y if Y else '<none>'}' is not a node in the declared graph",
                  {"exposure": X, "outcome": Y, "adjusted": adjusted, "sufficient_set": [],
                   "valid": None, "identifiable": None, "open_backdoor": None,
                   "over_adjustment": [], "missing": [], "repair": []})

    latent = set(g.get("latent", []))
    observed = [v for v in g["nodes"] if v not in latent]
    Z = [c for c in adjusted if c in observed]
    desc_X = descendants_of(parents, X)
    over = [c for c in adjusted if c in desc_X]
    pxbar = {v: [p for p in ps if p != X] for v, ps in parents.items()}
    open_backdoor = not d_separated(pxbar, X, Y, Z)

    # canonical observed adjustment set (van der Zander et al.): a valid adjustment set
    # exists iff this one is valid.
    anc = ancestors_of(parents, {X, Y})

    def canonical_set(obs_nodes):
        return [v for v in anc if v in obs_nodes and v not in ({X, Y} | desc_X)]

    z_all = canonical_set(set(observed))
    identifiable = backdoor_valid(parents, X, Y, z_all)

    # identification repair: which latent node sets, if measured, would restore an
    # identifiable effect? Minimal subsets of the latent nodes, size 1 then 2.
    repair = []
    latent_list = sorted(latent)
    if not identifiable and 0 < len(latent_list) <= 8:
        for L in latent_list:
            if backdoor_valid(parents, X, Y, canonical_set(set(observed) | {L})):
                repair.append([L])
        if not repair and len(latent_list) >= 2:
            from itertools import combinations
            for pr in combinations(latent_list, 2):
                if backdoor_valid(parents, X, Y, canonical_set(set(observed) | set(pr))):
                    repair.append(list(pr))
    valid = (len(over) == 0) and not open_backdoor and identifiable

    suff = list(z_all)
    if identifiable:
        changed = True
        while changed:
            changed = False
            for z in list(suff):
                if backdoor_valid(parents, X, Y, [s for s in suff if s != z]):
                    suff = [s for s in suff if s != z]
                    changed = True
                    break
    missing = [s for s in suff if s not in Z]

    adj = {"exposure": X, "outcome": Y, "adjusted": adjusted,
           "sufficient_set": suff if identifiable else [],
           "valid": valid, "identifiable": identifiable, "open_backdoor": open_backdoor,
           "over_adjustment": over, "missing": missing, "repair": repair}

    def fmt(s):
        return ", ".join(s) if s else "empty"

    if not identifiable:
        lat_txt = (f" (e.g. through the unmeasured node(s) {{{fmt(sorted(latent))}}})"
                   if latent else "")
        if repair:
            rep_txt = (". Identification repair: measuring {"
                       + "} or {".join(" + ".join(r) for r in repair)
                       + "} would make the effect identifiable by adjustment")
        elif latent:
            rep_txt = ". No single latent node (or pair) restores identifiability by adjustment"
        else:
            rep_txt = ""
        reading = (f"given the declared graph, the effect of {X} on {Y} is not identifiable by "
                   f"adjusting for measured covariates: a backdoor path cannot be blocked by any "
                   f"observed set{lat_txt}. No adjustment is sufficient; this is not resolvable by "
                   f"covariate adjustment{rep_txt}")
        return mk("not_resolvable", reading, adj)

    if valid:
        reading = (f"the adjusted covariates {{{fmt(Z)}}} satisfy the backdoor criterion for "
                   f"{X} -> {Y} in the declared graph; the adjustment agrees with the graph "
                   f"(a sufficient set is {{{fmt(suff)}}})")
        return mk("stable", reading, adj)

    problems = []
    if open_backdoor:
        problems.append(f"a backdoor path from {X} to {Y} is left open (missing: {{{fmt(missing)}}})")
    if over:
        problems.append(f"it conditions on {{{fmt(over)}}}, which is a descendant of the exposure "
                        f"(over-adjustment / collider or mediator bias)")
    reading = ("the adjustment does not agree with the declared graph: " + "; and ".join(problems)
               + f". A sufficient set per the graph is {{{fmt(suff)}}}")
    return mk("unstable", reading, adj)
