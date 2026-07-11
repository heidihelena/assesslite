"""Worked example: does guideline adherence relate to survival, and which
structural assumptions does that conclusion stand on?

All data below are simulated. No registry or patient data appear here. Mirrors the
R worked example (inst/examples/worked-example.R).
"""
import os

import numpy as np
import pandas as pd

from assesslite import StructuralAudit

# --- simulate a multicentre cohort -------------------------------------------
rng = np.random.default_rng(42)
n_hosp = 12
hospitals = [f"H{h:02d}" for h in range(1, n_hosp + 1)]
hosp_effect = rng.normal(0, 0.10, n_hosp)

frames = []
for h in range(n_hosp):
    n = rng.integers(120, 261)
    age = np.round(rng.normal(68, 9, n))
    sex = rng.binomial(1, 0.42, n)
    stage = rng.choice(["I", "II", "III", "IV"], n, p=[0.20, 0.20, 0.30, 0.30])
    stage_i = np.array([["I", "II", "III", "IV"].index(s) for s in stage])
    year = rng.integers(2016, 2026, n)
    p_adh = 1 / (1 + np.exp(-(1.2 - 0.03 * (age - 68) - 0.45 * stage_i)))
    adherence = rng.binomial(1, p_adh)
    lp = 0.03 * (age - 68) + 0.25 * sex + 0.55 * stage_i - 0.35 * adherence + hosp_effect[h]
    t_event = rng.exponential(1 / (0.08 * np.exp(lp)))
    t_censor = rng.uniform(1, 6, n)
    frames.append(pd.DataFrame({
        "hospital": hospitals[h], "age": age, "sex": sex,
        "stage": pd.Categorical(stage, categories=["I", "II", "III", "IV"]),
        "diagnosis_year": year, "adherence": adherence,
        "time": np.minimum(t_event, t_censor),
        "status": (t_event <= t_censor).astype(int),
    }))
sim = pd.concat(frames, ignore_index=True)

# --- open the assessment: declare the observational world --------------------
a = StructuralAudit(
    data=sim,
    outcome=("time", "status"),
    exposure="adherence",
    covariates=["age", "sex", "stage"],
    cluster="hospital",
    time="diagnosis_year",
    subgroups=["stage"],
    unit="patient",
    estimand="conditional hazard ratio for guideline adherence, adjusted for age, sex, stage",
)

# --- the invariance ledger: what is claimed, why, and what it buys -----------
a.assume("unit_permutation_within_cluster",
         rationale="patient ordering within a hospital carries no causal information",
         licenses="pooling patients within hospital into one likelihood")
a.assume("cluster_exchangeability",
         rationale="hospitals follow the same national guideline; assumed provisionally so it can be attacked",
         licenses="one pooled effect across hospitals; transport to a hospital outside the sample")
a.assume("temporal_translation",
         rationale="no major guideline revision inside the 2016-2025 window",
         licenses="pooling all diagnosis years; applying the estimate forward")
a.assume("subgroup_transport",
         rationale="adherence is expected to act through the same pathways at every stage",
         licenses="one pooled effect rather than stage-specific effects")

# --- attack, decide, export, report ------------------------------------------
a.test(["unit_permutation", "cluster_holdout", "temporal_split", "subgroup_stability"], seed=7)
a.decide(abstain_if={"estimate_sign_changes": True, "effect_crosses_threshold": None})
print(a)

out_dir = os.environ.get("AUDIT_OUT", ".")
a.export_audit(os.path.join(out_dir, "worked-example-audit.json"))
a.render_report(os.path.join(out_dir, "worked-example-report.html"))
print(f"\naudit written to {os.path.join(out_dir, 'worked-example-audit.json')}")
print(f"report written to {os.path.join(out_dir, 'worked-example-report.html')}")
