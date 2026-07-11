"""Network interference attack (AssessLite core spec v0.3, spec/network.md).

Attacks the network_relabelling invariance by testing whether the outcome depends on
neighbours' exposure. A resolved neighbour-exposure effect is interference: who is
adjacent to whom matters, so relabelling the network changes the mechanism (SUTVA
fails). Kept identical to the R engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .estimator import fit_estimate

_COLS = ["label", "estimate", "se", "ci_low", "ci_high", "n"]


def neighbor_exposure(ids, xvec: dict, edges: pd.DataFrame, exposure_map: str = "mean") -> dict:
    """Neighbour-exposure summary per unit (units present in the data); NaN if no
    neighbours. Maps: "mean" (mean neighbour exposure), "any" (1 if any neighbour
    exposed), "sum" (number/total of exposed neighbours -- a dose)."""
    if exposure_map not in ("mean", "any", "sum"):
        raise ValueError("exposure_map must be one of: mean, any, sum")
    a = edges.iloc[:, 0].astype(str).to_numpy()
    b = edges.iloc[:, 1].astype(str).to_numpy()
    frm = np.concatenate([a, b])
    to = np.concatenate([b, a])  # undirected
    present = set(ids)
    ne = {u: [] for u in ids}
    for f, t in zip(frm, to):
        if f in present and t in present:
            ne[f].append(xvec[t])
    fun = {"mean": lambda v: float(np.mean(v)),
           "any": lambda v: float(any(x > 0 for x in v)),
           "sum": lambda v: float(np.sum(v))}[exposure_map]
    return {u: (fun(v) if v else np.nan) for u, v in ne.items()}


def test_interference(assessment, exposure_map: str = "mean") -> dict:
    net = assessment.network
    if net is None:
        raise ValueError("interference_check needs a network; pass unit_id and edges to "
                         "StructuralAudit()")
    d = assessment.data
    ids = d[net["unit_id"]].astype(str).tolist()
    exposure = assessment.analysis["exposure"]
    xvec = dict(zip(ids, d[exposure].to_numpy()))
    ne_map = neighbor_exposure(ids, xvec, net["edges"], exposure_map)
    ne = np.array([ne_map[u] for u in ids], dtype=float)
    n_with_nb = int(np.sum(~np.isnan(ne)))
    fill = float(np.nanmean(ne)) if n_with_nb > 0 else 0.0
    ne[np.isnan(ne)] = fill

    d2 = d.copy()
    d2["neighbor_exposure"] = ne
    analysis2 = dict(assessment.analysis)
    analysis2["covariates"] = list(assessment.analysis["covariates"]) + ["neighbor_exposure"]
    fit_x = fit_estimate(analysis2, d2)
    fit_nb = fit_estimate(analysis2, d2, coef_of="neighbor_exposure")
    empty = pd.DataFrame(columns=_COLS)

    def mk(verdict, reading, sp):
        sp["exposure_map"] = exposure_map
        return {"test": "interference_check", "invariance": "network_relabelling",
                "verdict": verdict, "metrics": None, "spillover": sp,
                "variants": empty, "n_failed": 0, "reading": reading}

    if fit_nb is None or fit_x is None:
        return mk("not_resolvable",
                  "the neighbour-exposure model could not be fitted; interference is not "
                  "resolvable with this data",
                  {"neighbor_exposure_coef": None, "ci_low": None, "ci_high": None,
                   "exposure_estimate": assessment.estimate["value"],
                   "exposure_estimate_adjusted": None, "n_with_neighbors": n_with_nb})

    excl_null = fit_nb["ci_low"] > 0 or fit_nb["ci_high"] < 0
    half = 1.96 * fit_nb["se"]
    main_eff = abs(assessment.estimate["value"])
    verdict = ("unstable" if excl_null
               else "not_resolvable" if half > max(main_eff, 0.1) else "stable")

    sp = {"neighbor_exposure_coef": fit_nb["value"], "ci_low": fit_nb["ci_low"],
          "ci_high": fit_nb["ci_high"], "exposure_estimate": assessment.estimate["value"],
          "exposure_estimate_adjusted": fit_x["value"], "n_with_neighbors": n_with_nb}

    if verdict == "unstable":
        reading = (f"the outcome depends on neighbours' exposure (neighbour-exposure effect "
                   f"{fit_nb['value']:.3f} [{fit_nb['ci_low']:.3f}, {fit_nb['ci_high']:.3f}], "
                   f"distinguishable from zero): interference is present, so relabelling the network "
                   f"changes the mechanism and SUTVA does not hold. The exposure estimate is "
                   f"{assessment.estimate['value']:.3f} ignoring neighbours vs {fit_x['value']:.3f} "
                   f"accounting for them")
    elif verdict == "stable":
        reading = (f"no detectable dependence on neighbours' exposure (neighbour-exposure effect "
                   f"{fit_nb['value']:.3f} [{fit_nb['ci_low']:.3f}, {fit_nb['ci_high']:.3f}], not "
                   f"distinguishable from zero and smaller than the exposure effect); the mechanism "
                   f"holds up under network relabelling at this n")
    else:
        reading = (f"the neighbour-exposure effect could not be resolved at this n (interval "
                   f"half-width {half:.3f} exceeds the exposure effect {main_eff:.3f}); interference "
                   f"can neither be shown nor ruled out")
    return mk(verdict, reading, sp)
