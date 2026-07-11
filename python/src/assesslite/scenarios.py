"""Confounding scenario array (AssessLite core spec v0.3, spec/scenarios.md).

A deterministic bias-analysis array (Lin, Psaty & Kronmal 1998; VanderWeele & Arah 2011):
for a grid of unmeasured-confounder scenarios, shift the estimate toward the null by the
implied confounding bias and record where the conclusion tips past a target (the null, or a
declared decision threshold). The estimator-failure map complementing the single-number
E-value. Kept identical to the R engine.
"""
from __future__ import annotations

import math


def bias_factor(rr_uy: float, p0: float, delta: float) -> float:
    p1 = min(1.0, max(0.0, p0 + delta))
    return (1 + (rr_uy - 1) * p1) / (1 + (rr_uy - 1) * p0)


def test_confounding_scenarios(assessment, confounder_prevalence: float = 0.2, tip_ratio=None,
                               rr_uy_grid=(1.5, 2, 3, 4), delta_grid=(0.1, 0.2, 0.3, 0.4),
                               plausible_rr_uy: float = 2, plausible_delta: float = 0.2) -> dict:
    est = assessment.estimate
    estimator = assessment.analysis["estimator"]
    if estimator not in ("coxph", "glm_binomial"):
        raise ValueError("confounding_scenarios (bias analysis) is defined for ratio-scale "
                         f"estimators only (coxph, glm_binomial); not for '{estimator}' on a "
                         f"{assessment.analysis['scale']}")

    obs = est["value"]
    s = 0.0 if obs == 0 else (1.0 if obs > 0 else -1.0)
    target = 0.0 if tip_ratio is None else math.log(tip_ratio)
    includes_target = est["ci_low"] <= target <= est["ci_high"]

    cells, min_tip = [], None
    for rr in rr_uy_grid:
        for dl in delta_grid:
            bf = bias_factor(rr, confounder_prevalence, dl)
            adj = obs - s * math.log(bf)
            tipped = adj < target if s >= 0 else adj > target
            cells.append({"rr_uy": rr, "delta": dl, "bias_factor": round(bf, 3),
                          "adjusted_estimate": round(adj, 4), "tips": tipped})
            if tipped and rr <= plausible_rr_uy and dl <= plausible_delta and \
                    (min_tip is None or rr * dl < min_tip["rr_uy"] * min_tip["delta"]):
                min_tip = {"rr_uy": rr, "delta": dl}

    plausible_tip = any(c["tips"] and c["rr_uy"] <= plausible_rr_uy and c["delta"] <= plausible_delta
                        for c in cells)
    verdict = ("not_resolvable" if includes_target
               else "unstable" if plausible_tip else "stable")

    measure = "hazard ratio" if estimator == "coxph" else "odds ratio"
    tgt = "no effect" if tip_ratio is None else f"a {measure} of {tip_ratio:.2f}"
    caveat = (f"(bias analysis on the risk-ratio scale under the rare-outcome approximation "
              f"for the {measure})")
    if verdict == "not_resolvable":
        reading = (f"the interval already includes {tgt} on the ratio scale, so the confounding "
                   f"needed to reach it is not defined; the effect itself is not established beyond "
                   f"the target")
    elif verdict == "unstable":
        reading = (f"an unmeasured confounder within the plausible bound (outcome risk ratio <= "
                   f"{plausible_rr_uy:.1f}, exposure prevalence difference <= {plausible_delta:.2f}, at "
                   f"prevalence {confounder_prevalence:.2f}) would move the estimate past {tgt} -- the "
                   f"smallest such is risk ratio {min_tip['rr_uy']:.1f} with prevalence difference "
                   f"{min_tip['delta']:.2f}; the conclusion does not hold up against plausible "
                   f"confounding {caveat}")
    else:
        reading = (f"no unmeasured confounder within the plausible bound (outcome risk ratio <= "
                   f"{plausible_rr_uy:.1f}, prevalence difference <= {plausible_delta:.2f}) moves the "
                   f"estimate past {tgt}; only stronger-than-plausible confounding would tip the "
                   f"conclusion {caveat}")

    return {
        "test": "confounding_scenarios", "invariance": "unobserved_confounding",
        "verdict": verdict, "metrics": None,
        "scenarios": {"target": tip_ratio, "confounder_prevalence": confounder_prevalence,
                      "plausible_rr_uy": plausible_rr_uy, "plausible_delta": plausible_delta,
                      "minimal_tipping": min_tip, "cells": cells},
        "variants": _empty(), "n_failed": 0, "reading": reading,
    }


def _empty():
    import pandas as pd
    return pd.DataFrame(columns=["label", "estimate", "se", "ci_low", "ci_high", "n"])
