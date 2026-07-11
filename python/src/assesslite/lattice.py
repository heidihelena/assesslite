"""Assumption lattice (AssessLite core spec v0.2, spec/lattice.md).

The pooling invariances (pool across clusters / time) are the "stronger symmetry ->
one number" commitments. This refits the exposure estimate under every pool-or-stratify
combination and reports whether the conclusion depends on those pooling commitments.
Kept identical to the R engine.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

from .estimator import fit_estimate


def build_lattice(assessment) -> dict:
    s = assessment.structure
    axes, var_of = [], {}
    if s["cluster"] is not None:
        axes.append("cluster_exchangeability"); var_of["cluster_exchangeability"] = s["cluster"]
    if s["time"] is not None:
        axes.append("temporal_translation"); var_of["temporal_translation"] = s["time"]

    if not axes:
        return {"axes": [], "variables": {}, "nodes": [], "verdict": "not_resolvable",
                "reading": "no poolable structural axes (cluster or time) were declared; "
                           "the pooling lattice is empty"}

    main = assessment.estimate
    k = len(axes)
    nodes = []
    for r in range(k + 1):
        for P in combinations(axes, r):
            P = list(P)
            stratified = [ax for ax in axes if ax not in P]
            fit = fit_estimate(assessment.analysis, assessment.data,
                               strata=[var_of[a] for a in stratified])
            if fit is None:
                continue
            same_sign = np.sign(fit["value"]) == np.sign(main["value"]) or np.sign(main["value"]) == 0
            excl_null = fit["ci_low"] > 0 or fit["ci_high"] < 0
            status = ("reversed" if (not same_sign and excl_null)
                      else "attenuated" if not excl_null else "consistent")
            nodes.append({"pooled": P, "stratified": stratified, "n_pooled": len(P),
                          "estimate": fit["value"], "ci_low": fit["ci_low"],
                          "ci_high": fit["ci_high"], "n": fit["n"], "status": status})

    statuses = [nd["status"] for nd in nodes]
    verdict = ("unstable" if "reversed" in statuses
               else "not_resolvable" if "attenuated" in statuses else "stable")
    words = ", ".join(a.replace("_", " ") for a in axes)
    if verdict == "stable":
        reading = (f"the exposure estimate keeps the same direction and stays distinguishable from "
                   f"no effect under every pool-or-stratify choice over {{{words}}}; the conclusion "
                   f"does not depend on these pooling commitments")
    elif verdict == "not_resolvable":
        reading = (f"under some pool-or-stratify choices over {{{words}}} the interval comes to include "
                   f"no effect: the direction holds throughout, but whether the effect is resolved "
                   f"depends on the pooling commitments")
    else:
        reading = (f"the exposure estimate changes sign under some pool-or-stratify choice over "
                   f"{{{words}}}; the conclusion depends on these pooling commitments and does not "
                   f"hold across the lattice")
    return {"axes": axes, "variables": var_of, "nodes": nodes, "verdict": verdict, "reading": reading}
