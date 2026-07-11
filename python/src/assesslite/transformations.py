"""Transformation attacks (AssessLite core spec v0.1, spec/transformations/transformations.md).
Each returns a test-result dict via build_test_result(). Kept identical to the R engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .estimator import fit_estimate
from .stability import build_test_result

_COLS = ["label", "estimate", "se", "ci_low", "ci_high", "n"]


def _variant_row(label: str, fit: dict) -> dict:
    return {"label": label, "estimate": fit["value"], "se": fit["se"],
            "ci_low": fit["ci_low"], "ci_high": fit["ci_high"], "n": fit["n"]}


def _collect(rows: list) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=_COLS) if rows else pd.DataFrame(columns=_COLS)


def target_invariance(assessment, test: str) -> str:
    cluster = assessment.structure["cluster"]
    return {
        "unit_permutation": "unit_permutation" if cluster is None else "unit_permutation_within_cluster",
        "cluster_holdout": "cluster_exchangeability",
        "temporal_split": "temporal_translation",
        "subgroup_stability": "subgroup_transport",
        "confounding_sensitivity": "unobserved_confounding",
        "graph_check": "causal_graph",
        "adjustment_check": "adjustment_sufficiency",
    }[test]


def test_unit_permutation(assessment, rng: np.random.Generator, n_perm: int = 5) -> dict:
    cluster = assessment.structure["cluster"]
    invariance = "unit_permutation" if cluster is None else "unit_permutation_within_cluster"
    d = assessment.data
    rows, n_failed = [], 0
    for i in range(n_perm):
        idx = rng.permutation(d.index.to_numpy()) if cluster is None else _perm_within(d, cluster, rng)
        fit = fit_estimate(assessment.analysis, d.loc[idx])
        if fit is None:
            n_failed += 1
        else:
            rows.append(_variant_row(f"permutation {i + 1}", fit))
    return build_test_result(assessment.estimate, "unit_permutation", invariance,
                             _collect(rows), n_failed, deterministic=True)


def _perm_within(d: pd.DataFrame, cluster: str, rng: np.random.Generator) -> np.ndarray:
    parts = []
    for _, sub in d.groupby(cluster, sort=True):
        parts.append(rng.permutation(sub.index.to_numpy()))
    return np.concatenate(parts)


def test_cluster_holdout(assessment) -> dict:
    cluster = assessment.structure["cluster"]
    if cluster is None:
        raise ValueError("cluster_holdout needs a declared cluster variable")
    d = assessment.data
    rows, n_failed = [], 0
    for cl in sorted(d[cluster].astype(str).unique()):
        fit = fit_estimate(assessment.analysis, d[d[cluster].astype(str) != cl])
        if fit is None:
            n_failed += 1
        else:
            rows.append(_variant_row(f"without {cluster} = {cl}", fit))
    return build_test_result(assessment.estimate, "cluster_holdout", "cluster_exchangeability",
                             _collect(rows), n_failed)


def test_temporal_split(assessment) -> dict:
    timevar = assessment.structure["time"]
    if timevar is None:
        raise ValueError("temporal_split needs a declared time variable")
    d = assessment.data
    tv = d[timevar]
    vals = np.sort(pd.unique(tv.dropna()))
    if len(vals) < 2:
        raise ValueError("temporal_split needs at least two distinct time values")
    groups = []
    if len(vals) <= 3:
        for v in vals:
            groups.append((f"{timevar} = {v}", tv == v))
    else:
        med = np.median(tv.dropna())
        early = tv <= med
        if early.sum() < 10 or (~early).sum() < 10:
            early = tv.rank(method="first") <= d.shape[0] / 2
        groups.append((f"{timevar} early ({tv[early].min()}-{tv[early].max()})", early))
        groups.append((f"{timevar} late ({tv[~early].min()}-{tv[~early].max()})", ~early))
    rows, n_failed = [], 0
    for label, keep in groups:
        fit = fit_estimate(assessment.analysis, d[keep.fillna(False)])
        if fit is None:
            n_failed += 1
        else:
            rows.append(_variant_row(label, fit))
    return build_test_result(assessment.estimate, "temporal_split", "temporal_translation",
                             _collect(rows), n_failed)


def test_subgroup_stability(assessment) -> dict:
    vars_ = assessment.structure["subgroups"]
    if not vars_:
        raise ValueError("subgroup_stability needs declared subgroup variables")
    d = assessment.data
    rows, n_failed = [], 0
    for v in vars_:
        for lev in sorted(d[v].astype(str).unique()):
            keep = d[v].astype(str) == lev
            sub_analysis = dict(assessment.analysis)
            # a subgroup variable cannot also adjust within its own stratum
            sub_analysis["covariates"] = [c for c in assessment.analysis["covariates"] if c != v]
            fit = fit_estimate(sub_analysis, d[keep])
            if fit is None:
                n_failed += 1
            else:
                rows.append(_variant_row(f"{v} = {lev}", fit))
    return build_test_result(assessment.estimate, "subgroup_stability", "subgroup_transport",
                             _collect(rows), n_failed)
