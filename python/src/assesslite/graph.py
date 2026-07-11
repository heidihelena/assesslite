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
    imps = []

    for i, V in enumerate(order):
        preds = order[:i]
        par = parents[V]
        for W in [p for p in preds if p not in par]:
            cond = list(par)
            claim = "{} _||_ {} | {{{}}}".format(V, W, ", ".join(cond))
            vv = coerce_numeric(d[V]) if V in d.columns else None
            ww = coerce_numeric(d[W]) if W in d.columns else None
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
