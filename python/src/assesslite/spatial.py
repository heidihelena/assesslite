"""Spatial attack (AssessLite core spec v0.3, spec/spatial.md).

Attacks the spatial_translation invariance (the mechanism is the same across the
field) by leave-one-spatial-block-out: grid the coordinate space into k x k blocks
from quantile bins and refit with each block removed. Kept identical to the R engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .estimator import fit_estimate
from .stability import build_test_result

_COLS = ["label", "estimate", "se", "ci_low", "ci_high", "n"]


def _bins(v: np.ndarray, k: int) -> np.ndarray:
    edges = np.unique(np.quantile(v[~np.isnan(v)], np.linspace(0, 1, k + 1)))
    if len(edges) < 2:
        return np.ones(len(v), dtype=float)
    b = np.digitize(v, edges[1:-1], right=False).astype(float)
    b[np.isnan(v)] = np.nan
    return b


def spatial_blocks(x: np.ndarray, y: np.ndarray, k: int):
    bx, by = _bins(x, k), _bins(y, k)
    out = []
    for a, b in zip(bx, by):
        out.append(None if (np.isnan(a) or np.isnan(b)) else f"{int(a)}_{int(b)}")
    return out


def test_spatial_holdout(assessment, k: int = 3) -> dict:
    coords = assessment.structure.get("coords")
    if not coords:
        raise ValueError("spatial_holdout needs declared coordinates; pass coords=(x, y) "
                         "to StructuralAudit()")
    d = assessment.data
    block = spatial_blocks(d[coords[0]].to_numpy(dtype=float),
                           d[coords[1]].to_numpy(dtype=float), k)
    block = pd.Series(block, index=d.index)
    rows, n_failed = [], 0
    for b in sorted(x for x in block.dropna().unique()):
        keep = block.isna() | (block != b)
        fit = fit_estimate(assessment.analysis, d[keep.values])
        if fit is None:
            n_failed += 1
            continue
        rows.append({"label": f"without spatial block {b}", "estimate": fit["value"],
                     "se": fit["se"], "ci_low": fit["ci_low"], "ci_high": fit["ci_high"],
                     "n": fit["n"]})
    variants = pd.DataFrame(rows, columns=_COLS)
    return build_test_result(assessment.estimate, "spatial_holdout", "spatial_translation",
                             variants, n_failed)
