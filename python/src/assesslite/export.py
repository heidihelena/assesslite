"""Audit export: the complete reasoning path as one dict/JSON object conforming to
spec/schema/audit.schema.json. Byte-compatible in structure with the R engine's output.
"""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone

import pandas as pd

__version__ = "0.4.0"


def _fingerprint(data: pd.DataFrame) -> dict:
    payload = data.to_csv(index=False).encode("utf-8")
    return {"n_rows": int(data.shape[0]), "n_cols": int(data.shape[1]),
            "md5": hashlib.md5(payload).hexdigest()}


def audit_as_list(assessment) -> dict:
    if assessment.decision is None:
        raise RuntimeError("run decide() before exporting; an audit without a decision is not complete")

    tests = []
    for t in assessment.tests.values():
        v = t["variants"]
        obj = {
            "test": t["test"], "invariance": t["invariance"], "verdict": t["verdict"],
            "variants": [
                {"label": r["label"], "estimate": float(r["estimate"]),
                 "se": None if pd.isna(r["se"]) else float(r["se"]),
                 "ci_low": None if pd.isna(r["ci_low"]) else float(r["ci_low"]),
                 "ci_high": None if pd.isna(r["ci_high"]) else float(r["ci_high"]),
                 "n": int(r["n"])}
                for _, r in v.iterrows()
            ],
            "n_failed_refits": int(t["n_failed"]),
            "reading": t["reading"],
        }
        if t.get("metrics") is not None:
            obj["metrics"] = t["metrics"]
        if t.get("sensitivity") is not None:
            obj["sensitivity"] = t["sensitivity"]
        if t.get("implications") is not None:
            obj["implications"] = t["implications"]
        if t.get("adjustment") is not None:
            obj["adjustment"] = t["adjustment"]
        if t.get("spillover") is not None:
            obj["spillover"] = t["spillover"]
        if t.get("overlap") is not None:
            obj["overlap"] = t["overlap"]
        if t.get("scenarios") is not None:
            obj["scenarios"] = t["scenarios"]
        if t.get("autocorrelation") is not None:
            obj["autocorrelation"] = t["autocorrelation"]
        tests.append(obj)

    a = assessment.analysis
    audit = {
        "spec_version": "0.1",
        "analysis": {
            "unit": a["unit"], "outcome": a["outcome"], "exposure": a["exposure"],
            "covariates": list(a["covariates"]), "estimand": a["estimand"],
            "estimator": a["estimator"], "scale": a["scale"],
        },
        "structure": {
            "cluster": assessment.structure["cluster"],
            "time": assessment.structure["time"],
            "subgroups": list(assessment.structure["subgroups"]),
            "coords": (list(assessment.structure["coords"])
                       if assessment.structure.get("coords") else None),
            "unit_id": assessment.structure.get("unit_id"),
            "n_edges": assessment.structure.get("n_edges"),
        },
        "ledger": [
            {"invariance": l["invariance"], "status": l["status"], "rationale": l["rationale"],
             "licenses": l["licenses"], "tested": l["tested"], "verdict": l["verdict"]}
            for l in assessment.ledger
        ],
        "estimate": assessment.estimate,
        "tests": tests,
        "decision": assessment.decision,
        "provenance": {
            "created": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
            "engine": "assesslite-python",
            "engine_version": __version__,
            "platform": f"Python {platform.python_version()}",
            "spec_version": "0.1",
            "data_fingerprint": _fingerprint(assessment.data),
        },
    }
    if assessment.lattice is not None:
        audit["lattice"] = assessment.lattice
    return audit


def export_audit(assessment, path: str | None = None) -> dict:
    """Return the durable audit record as a dict; write it as JSON if a path is given.

    audit = assessment.export_audit()            # in-memory record
    assessment.export_audit("audit.json")        # also writes to disk
    """
    audit = audit_as_list(assessment)
    if path is not None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(audit, fh, indent=2, ensure_ascii=False)
    return audit
