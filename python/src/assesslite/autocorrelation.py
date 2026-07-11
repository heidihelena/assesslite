"""Spatial autocorrelation attack (AssessLite core spec v0.4, spec/spatial.md).

Moran's I on the outcome-model residuals over a row-standardised k-nearest-neighbour
weight matrix, with moments under the normality assumption (Cliff & Ord) so the test
is deterministic given the data. Attacks the spatial_independence invariance. Kept
identical to the R engine.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .estimator import model_residuals

_COLS = ["label", "estimate", "se", "ci_low", "ci_high", "n"]


def knn_neighbours(x: np.ndarray, y: np.ndarray, k: int) -> np.ndarray:
    n = len(x)
    k = min(k, n - 1)
    nb = np.zeros((n, k), dtype=int)
    for i in range(n):
        d2 = (x - x[i]) ** 2 + (y - y[i]) ** 2
        d2[i] = np.inf
        nb[i] = np.argsort(d2, kind="stable")[:k]
    return nb


def moran_i(r: np.ndarray, nb: np.ndarray):
    n = len(r)
    k = nb.shape[1]
    z = r - r.mean()
    zlag = z[nb].mean(axis=1)
    I = float(np.sum(z * zlag) / np.sum(z ** 2))       # S0 = n for row-standardised W
    w = 1.0 / k
    S0 = float(n)
    nbsets = [set(row) for row in nb]
    recip = np.zeros_like(nb, dtype=bool)
    for i in range(n):
        for c in range(k):
            recip[i, c] = i in nbsets[nb[i, c]]
    # ordered double-sum of (w_ij + w_ji)^2, iterated over edges i->j; the mirrored
    # (j,i) term is only missing for non-reciprocal edges, where it equals w^2
    ordered_sum = float(np.sum((w + w * recip) ** 2) + np.sum((~recip) * w ** 2))
    S1 = 0.5 * ordered_sum
    in_deg = np.bincount(nb.ravel(), minlength=n)
    S2 = float(np.sum((1 + in_deg * w) ** 2))
    EI = -1.0 / (n - 1)
    EI2 = (n ** 2 * S1 - n * S2 + 3 * S0 ** 2) / ((n ** 2 - 1) * S0 ** 2)
    V = EI2 - EI ** 2
    return I, EI, math.sqrt(V)


def test_spatial_autocorrelation(assessment, k: int = 8, i_floor: float = 0.1) -> dict:
    coords = assessment.structure.get("coords")
    if not coords:
        raise ValueError("spatial_autocorrelation needs declared coordinates; pass "
                         "coords=(x, y) to StructuralAudit()")
    d = assessment.data
    r, idx = model_residuals(assessment.analysis, d)
    empty = pd.DataFrame(columns=_COLS)

    def mk(verdict, reading, ac):
        return {"test": "spatial_autocorrelation", "invariance": "spatial_independence",
                "verdict": verdict, "metrics": None, "autocorrelation": ac,
                "variants": empty, "n_failed": 0, "reading": reading}

    rtype = "martingale" if assessment.analysis["estimator"] == "coxph" else "response"
    if r is None:
        return mk("not_resolvable",
                  "the outcome model could not be fitted, so residual spatial autocorrelation "
                  "is not resolvable",
                  {"moran_i": None, "expected": None, "se": None, "z": None, "p_value": None,
                   "k": k, "n": None, "residual_type": None})

    x = d[coords[0]].to_numpy(dtype=float)[idx]
    y = d[coords[1]].to_numpy(dtype=float)[idx]
    keep = ~(np.isnan(x) | np.isnan(y))
    r, x, y = r[keep], x[keep], y[keep]
    n = len(r)
    if n < 30:
        return mk("not_resolvable",
                  f"only {n} units have residuals and coordinates; spatial independence is "
                  f"not resolvable",
                  {"moran_i": None, "expected": None, "se": None, "z": None, "p_value": None,
                   "k": k, "n": n, "residual_type": rtype})

    nb = knn_neighbours(x, y, k)
    I, EI, se = moran_i(r, nb)
    z = (I - EI) / se
    p = math.erfc(abs(z) / math.sqrt(2))
    mdi = 1.96 * se

    verdict = ("unstable" if (p < 0.05 and abs(I) >= i_floor)
               else "not_resolvable" if mdi > i_floor else "stable")
    ac = {"moran_i": round(I, 4), "expected": round(EI, 4), "se": round(se, 4),
          "z": round(z, 3), "p_value": round(p, 4), "k": int(nb.shape[1]), "n": n,
          "residual_type": rtype}
    if verdict == "unstable":
        reading = (f"the outcome-model residuals are spatially autocorrelated (Moran's I {I:.3f} "
                   f"over {nb.shape[1]}-nearest-neighbour weights, p = {p:.2g}): nearby units share "
                   f"unmodelled structure, the effective sample size is smaller than n = {n}, and "
                   f"intervals that treat units as independent overstate precision ({rtype} "
                   f"residuals; normality-based test)")
    elif verdict == "stable":
        reading = (f"no resolved spatial autocorrelation in the outcome-model residuals (Moran's I "
                   f"{I:.3f}, p = {p:.2g}; the test could resolve I of about {mdi:.3f} at this n); "
                   f"treating units as spatially independent holds up ({rtype} residuals)")
    else:
        reading = (f"the test could only resolve Moran's I of about {mdi:.3f} at this n and "
                   f"configuration, above the {i_floor:.2f} floor; spatial independence can "
                   f"neither be shown nor ruled out")
    return mk(verdict, reading, ac)
