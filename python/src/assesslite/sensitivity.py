"""Sensitivity attacks (AssessLite core spec v0.2, spec/stability/sensitivity.md).

A sensitivity attack asks how strong an unobserved violation would have to be to
overturn the conclusion. It produces no variant refits, but carries a three-way
verdict in the same vocabulary as every transformation attack. Kept identical to
the R engine.
"""
from __future__ import annotations

import math

import pandas as pd

_COLS = ["label", "estimate", "se", "ci_low", "ci_high", "n"]


def evalue_from_ratio(r: float) -> float:
    """E-value of a ratio (VanderWeele & Ding, 2017): the minimum strength of
    association, on the risk-ratio scale, that an unmeasured confounder would need
    with both exposure and outcome to explain the association away."""
    r = 1.0 / r if r < 1 else r
    return r + math.sqrt(r * (r - 1.0))


def test_confounding_sensitivity(assessment, benchmark: float = 1.25) -> dict:
    est = assessment.estimate
    estimator = assessment.analysis["estimator"]
    if estimator not in ("coxph", "glm_binomial"):
        raise ValueError(
            "confounding_sensitivity (E-value) is defined for ratio-scale estimators only "
            f"(coxph, glm_binomial); not for '{estimator}' on a {assessment.analysis['scale']}")

    rr = math.exp(est["value"])
    ll = math.exp(est["ci_low"])
    ul = math.exp(est["ci_high"])
    e_point = evalue_from_ratio(rr)
    includes_null = ll <= 1 <= ul
    e_ci = 1.0 if includes_null else (evalue_from_ratio(ll) if rr > 1 else evalue_from_ratio(ul))

    verdict = "not_resolvable" if includes_null else ("unstable" if e_ci <= benchmark else "stable")
    measure = "hazard ratio" if estimator == "coxph" else "odds ratio"
    caveat = (f"(E-value on the risk-ratio scale under the rare-outcome approximation "
              f"for the {measure})")
    if verdict == "not_resolvable":
        reading = ("the confidence interval already includes no effect on the ratio scale, so the "
                   "unmeasured confounding needed to explain the result away is not defined "
                   "(E-value for the interval = 1); this attack is not resolvable — the effect "
                   "itself is not established")
    elif verdict == "unstable":
        reading = (f"an unmeasured confounder associated with both exposure and outcome by a risk "
                   f"ratio of about {e_ci:.2f} would move the interval to include no effect; that is "
                   f"no stronger than the declared plausible confounding ({benchmark:.2f}), so "
                   f"no-unmeasured-confounding does not hold up {caveat}")
    else:
        reading = (f"explaining the interval away would require unmeasured confounding of at least "
                   f"{e_ci:.2f} on the risk-ratio scale, stronger than the declared plausible "
                   f"benchmark ({benchmark:.2f}); the conclusion is robust to confounding at that "
                   f"benchmark (E-value for the point estimate {e_point:.2f}) {caveat}")

    return {
        "test": "confounding_sensitivity", "invariance": "unobserved_confounding",
        "verdict": verdict, "metrics": None,
        "sensitivity": {"e_value_point": e_point, "e_value_ci": e_ci, "rr_point": rr,
                        "rr_ci_low": ll, "rr_ci_high": ul, "benchmark": benchmark},
        "variants": pd.DataFrame(columns=_COLS), "n_failed": 0, "reading": reading,
    }
