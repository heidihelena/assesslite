"""Positivity attack (AssessLite core spec v0.3, spec/positivity.md).

Positivity: every unit could plausibly have either exposure level given its covariates.
Fit a propensity score P(exposure = 1 | covariates), trim units near propensity 0 or 1
(weak overlap) at increasing thresholds, and refit. A resolved trimming shift is
unstable; substantial weak overlap makes positivity not resolvable; good overlap with no
shift is stable. Kept identical to the R engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .estimator import _design_matrix, _fit_glm, fit_estimate
from .stability import build_test_result

_COLS = ["label", "estimate", "se", "ci_low", "ci_high", "n"]


def _propensity(data: pd.DataFrame, exposure: str, covariates: list):
    used = [exposure] + covariates
    cc = data[used].dropna()
    X, _ = _design_matrix(cc, covariates[0], covariates[1:], intercept=True)
    y = cc[exposure].to_numpy(dtype=float)
    try:
        beta, _ = _fit_glm(X, y, "glm_binomial")
    except (np.linalg.LinAlgError, ValueError, FloatingPointError):
        return None
    ps_cc = 1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30, 30)))
    ps = np.full(len(data), np.nan)
    ps[cc.index.to_numpy()] = ps_cc
    return ps


def test_positivity(assessment, alphas=(0.01, 0.02, 0.05, 0.10)) -> dict:
    a = assessment.analysis
    d = assessment.data
    x = d[a["exposure"]]
    if not (pd.api.types.is_numeric_dtype(x) and set(pd.unique(x.dropna())).issubset({0, 1})):
        raise ValueError("positivity_check needs a binary 0/1 exposure")
    if not a["covariates"]:
        raise ValueError("positivity_check needs covariates (overlap is defined in covariate space)")

    ps = _propensity(d, a["exposure"], list(a["covariates"]))
    if ps is None:
        return build_test_result(assessment.estimate, "positivity_check", "positivity",
                                 pd.DataFrame(columns=_COLS), 0)

    rows, n_failed = [], 0
    for al in alphas:
        keep = (~np.isnan(ps)) & (ps >= al) & (ps <= 1 - al)
        trimmed = int(np.sum(~np.isnan(ps)) - np.sum(keep))
        fit = fit_estimate(a, d[keep])
        if fit is None:
            n_failed += 1
            continue
        rows.append({"label": f"trim propensity outside [{al:.2f}, {1-al:.2f}] ({trimmed} units)",
                     "estimate": fit["value"], "se": fit["se"], "ci_low": fit["ci_low"],
                     "ci_high": fit["ci_high"], "n": fit["n"]})
    variants = pd.DataFrame(rows, columns=_COLS)
    res = build_test_result(assessment.estimate, "positivity_check", "positivity", variants, n_failed)

    n_ps = int(np.sum(~np.isnan(ps)))
    n_extreme = int(np.sum((~np.isnan(ps)) & ((ps < 0.05) | (ps > 0.95))))
    frac = n_extreme / n_ps if n_ps > 0 else float("nan")
    res["overlap"] = {"frac_extreme": frac, "n_extreme": n_extreme, "n": n_ps}
    if res["verdict"] != "unstable" and np.isfinite(frac) and frac >= 0.10:
        res["verdict"] = "not_resolvable"
        res["reading"] = (f"{100*frac:.1f}% of units have propensity below 0.05 or above 0.95 (the "
                          f"weak-overlap region): positivity is strained -- many units have a "
                          f"near-deterministic exposure, so the pooled estimate extrapolates. Trimming "
                          f"those units did not resolve a shift, so whether the conclusion depends on "
                          f"them is not resolvable at this n")
    else:
        res["reading"] = res["reading"] + (f" ({100*frac:.1f}% of units are in the weak-overlap "
                                           f"region, propensity < 0.05 or > 0.95)")
    return res
