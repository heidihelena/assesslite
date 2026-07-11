"""Stability metrics and the three-way verdict rule (AssessLite core spec v0.1,
spec/stability/metrics.md). Verdicts are deterministic given the metrics, so any
audit file can be re-read back to its verdicts. Kept identical to the R engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def stability_metrics(est0: float, se0: float, ci0_low: float, ci0_high: float,
                      variants: pd.DataFrame) -> dict:
    se = variants["se"].to_numpy(dtype=float)
    est = variants["estimate"].to_numpy(dtype=float)
    lo = variants["ci_low"].to_numpy(dtype=float)
    hi = variants["ci_high"].to_numpy(dtype=float)

    # se of the difference: var(est_j - est_0) ~ se_j^2 - se_0^2 for a variant the
    # pooled estimate contains (see spec/stability/metrics.md)
    se_diff = np.where((~np.isnan(se)) & (se > se0), np.sqrt(np.clip(se ** 2 - se0 ** 2, 0, None)), se0)
    shift_z = np.abs(est - est0) / se_diff

    flip = (np.sign(est) != np.sign(est0)) & (np.sign(est0) != 0)
    excl_null = (~np.isnan(lo)) & ((lo > 0) | (hi < 0))
    full_excl_null = (ci0_low > 0) or (ci0_high < 0)

    return {
        "max_shift_z": float(np.nanmax(shift_z)),
        "sign_flips_resolved": int(np.nansum(flip & excl_null)),
        "sign_flips_unresolved": int(np.nansum(flip & ~excl_null)),
        "mds": float(1.96 * np.nanmedian(se)),
        "null_crossings": int(np.nansum(~excl_null if full_excl_null else excl_null)),
    }


def verdict_from_metrics(m: dict, est0: float, se0: float) -> str:
    if m["sign_flips_resolved"] >= 1 or m["max_shift_z"] > 2:
        return "unstable"
    if np.isfinite(m["mds"]) and m["mds"] > max(2 * se0, abs(est0)):
        return "not_resolvable"
    return "stable"


def _empty_variants() -> pd.DataFrame:
    return pd.DataFrame(columns=["label", "estimate", "se", "ci_low", "ci_high", "n"])


def build_test_result(estimate: dict, test: str, invariance: str, variants: pd.DataFrame,
                      n_failed: int = 0, deterministic: bool = False) -> dict:
    e = estimate
    if variants.shape[0] == 0:
        return {
            "test": test, "invariance": invariance, "verdict": "not_resolvable",
            "metrics": {"max_shift_z": None, "sign_flips_resolved": 0,
                        "sign_flips_unresolved": 0, "mds": None, "null_crossings": 0},
            "variants": variants, "n_failed": n_failed,
            "reading": (f"no variant model could be fitted; the attack on {invariance} "
                        "is not resolvable with this data"),
        }

    if deterministic:
        tol = 1e-8
        max_dev = float(np.max(np.abs(variants["estimate"].to_numpy(dtype=float) - e["value"])))
        verdict = "unstable" if max_dev > tol else "stable"
        reading = ("estimates are identical under permutation, as they must be; the "
                   "estimator treats unit order symmetrically") if verdict == "stable" else (
            f"estimates moved by up to {max_dev:.2e} under permutation of unit order; "
            "this points to an implementation or data problem, not a scientific finding")
        metrics = {"max_shift_z": max_dev / e["se"], "sign_flips_resolved": 0,
                   "sign_flips_unresolved": 0, "mds": None, "null_crossings": 0}
        return {"test": test, "invariance": invariance, "verdict": verdict,
                "metrics": metrics, "variants": variants, "n_failed": n_failed,
                "reading": reading}

    m = stability_metrics(e["value"], e["se"], e["ci_low"], e["ci_high"], variants)
    verdict = verdict_from_metrics(m, e["value"], e["se"])
    inv = invariance.replace("_", " ")
    if verdict == "stable":
        reading = (f"the largest variant shift was {m['max_shift_z']:.1f} standard errors of "
                   f"the difference, within sampling noise, and no resolved sign change occurred; "
                   f"the attack could have detected a shift of about {m['mds']:.2f}, so the claim "
                   f"of {inv} holds up under this test")
    elif verdict == "unstable":
        extra = (f" and {m['sign_flips_resolved']} variant(s) showed a resolved sign change"
                 if m["sign_flips_resolved"] > 0 else "")
        reading = (f"the estimate moved by up to {m['max_shift_z']:.1f} standard errors of the "
                   f"difference{extra}; {inv} does not hold up under this attack, and the pooling "
                   f"or transport it licenses loses its basis")
    else:
        reading = (f"variant intervals are too wide to distinguish stability from instability: "
                   f"the smallest detectable shift (about {m['mds']:.2f}) exceeds both the estimate "
                   f"({abs(e['value']):.2f}) and twice its standard error; this attack is not "
                   f"resolvable at this n")
    return {"test": test, "invariance": invariance, "verdict": verdict, "metrics": m,
            "variants": variants, "n_failed": n_failed, "reading": reading}
