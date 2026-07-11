"""Decision layer (AssessLite core spec v0.1, spec/abstention/rules.md).
An abstention is a result, not a failure of the tool. Kept identical to the R engine.
"""
from __future__ import annotations

import numpy as np


def decide(assessment, abstain_if: dict | None = None) -> dict:
    if abstain_if is None:
        abstain_if = {"estimate_sign_changes": True, "effect_crosses_threshold": None}
    e = assessment.estimate
    assumed = [l for l in assessment.ledger if l["status"] == "assumed"]

    load_bearing = [l["invariance"] for l in assumed if l["tested"] and l["verdict"] == "stable"]
    unstable_inv = [l["invariance"] for l in assumed if l["verdict"] == "unstable"]
    exposed = [l["invariance"] for l in assumed if (not l["tested"]) or l["verdict"] == "not_resolvable"]

    status = None
    rationale = None
    broken_by = None
    capped_conditional = False

    # base rule 1: resolved instability on an assumed invariance
    if unstable_inv:
        status = "abstain"
        for t in assessment.tests.values():
            if t["invariance"] in unstable_inv:
                broken_by = t["test"]
                break
        rationale = (f"the assumed invariance {unstable_inv[0].replace('_', ' ')} did not hold up "
                     f"under the {broken_by} attack; the pooling it licenses has no basis, so no "
                     f"pooled conclusion is reported")

    # user rule: resolved sign change anywhere
    if status is None and abstain_if.get("estimate_sign_changes"):
        for t in assessment.tests.values():
            v = t["variants"]
            if v.shape[0] == 0:
                continue
            est = v["estimate"].to_numpy(dtype=float)
            lo = v["ci_low"].to_numpy(dtype=float)
            hi = v["ci_high"].to_numpy(dtype=float)
            flip = (np.sign(est) != np.sign(e["value"])) & (np.sign(e["value"]) != 0)
            resolved = (~np.isnan(lo)) & ((lo > 0) | (hi < 0))
            if np.any(flip & resolved):
                status = "abstain"
                broken_by = t["test"]
                rationale = (f"under the {t['test']} attack at least one variant shows a resolved "
                             f"sign change; the direction of the effect depends on a structural "
                             f"choice, so no direction is reported")
                break

    # user rule: crossing a declared decision threshold
    thr = abstain_if.get("effect_crosses_threshold")
    if status is None and thr is not None:
        for t in assessment.tests.values():
            v = t["variants"]
            if v.shape[0] == 0:
                continue
            est = v["estimate"].to_numpy(dtype=float)
            lo = v["ci_low"].to_numpy(dtype=float)
            hi = v["ci_high"].to_numpy(dtype=float)
            opposite = (e["value"] - thr) * (est - thr) < 0
            resolved = (~np.isnan(lo)) & ((lo > thr) | (hi < thr))
            if np.any(opposite & resolved):
                status = "abstain"
                broken_by = t["test"]
                rationale = (f"a variant under the {t['test']} attack falls on the other side of the "
                             f"declared threshold ({thr}) and its interval excludes it; the threshold "
                             f"verdict is not stable")
                break
            if np.any(opposite & ~resolved):
                capped_conditional = True

    # base rules 2 and 3
    if status is None:
        if exposed or capped_conditional:
            status = "conditional"
            parts = []
            if exposed:
                parts.append("the conclusion stands conditional on: "
                             + "; ".join(x.replace("_", " ") for x in exposed)
                             + " (untested or not resolvable at this n)")
            if capped_conditional:
                parts.append(f"at least one variant straddles the declared threshold ({thr}) without "
                             f"resolving it; a threshold gate on an interval that includes the line "
                             f"cannot pass")
            rationale = "; additionally, ".join(parts)
        else:
            status = "proceed"
            rationale = ("every assumed invariance with an available attack was attacked and came "
                         "back stable: " + "; ".join(x.replace("_", " ") for x in load_bearing)
                         + "; within the declared structural alternatives the conclusion holds still")

    return {
        "status": status, "rationale": rationale,
        "load_bearing": load_bearing, "exposed_surface": exposed,
        "broken_by": broken_by,
        "abstention_rules": {
            "estimate_sign_changes": bool(abstain_if.get("estimate_sign_changes")),
            "effect_crosses_threshold": thr,
        },
    }
